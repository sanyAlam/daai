from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from typing import Any, Optional
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.approval_email import (
    ApprovalEmailNotifier,
    LogApprovalEmailProvider,
    ResendApprovalEmailProvider,
)
from app.config import Settings, get_settings
from app.dashboard_auth import (
    DashboardAuthError,
    DashboardPrincipal,
    inspect_unverified_token,
    verify_supabase_access_token,
)
from app.domain import ExecutionStatus, GovernanceStatus
from app.policy import PolicyEvaluationError
from app.policy_suggestion import (
    OpenAIPolicySuggester,
    PolicySuggester,
    fallback_policy_suggestion,
)
from app.quotas import current_month_window
from app.repository import GovernanceRepository, PostgresGovernanceRepository
from app.schemas import (
    ActionRunStatusResponse,
    AdminActionRunResponse,
    AdminOverviewResponse,
    AdminUserResponse,
    AdminWorkspaceResponse,
    CreateDashboardActionRequest,
    CreateDashboardApiKeyRequest,
    CreateDashboardApiKeyResponse,
    CreateDashboardWorkspaceRequest,
    CreateDashboardWorkspaceResponse,
    DashboardApiKeyResponse,
    DashboardActionResponse,
    DashboardActionPolicyResponse,
    DashboardActionRunListResponse,
    DashboardActionRunDetailResponse,
    DashboardActionRunListItemResponse,
    DashboardWorkspaceMetricsResponse,
    DashboardUsageResponse,
    DashboardWorkspaceApprovalSettingsRequest,
    DashboardWorkspaceApprovalSettingsResponse,
    DashboardPendingApprovalListItemResponse,
    DashboardActionDecisionResponse,
    DashboardWorkspaceKeyInfoResponse,
    DashboardWorkspaceResponse,
    DeleteDashboardWorkspaceRequest,
    DeleteDashboardWorkspaceResponse,
    ExecutionReportResponse,
    GovernanceReceiptResponse,
    InterceptRequest,
    InterceptResponse,
    PolicySuggestionResponse,
    PublicDecisionResponse,
    RegenerateDashboardWorkspaceKeyResponse,
    ReportExecutedRequest,
    ReportFailedRequest,
    SuggestActionPolicyRequest,
)
from app.service import (
    ActionRunConflictError,
    ActionRunNotFoundError,
    ActionRegistrationConflictError,
    ActionRegistrationValidationError,
    ApiKeyNotFoundError,
    ApiKeyValidationError,
    ApprovalLinkNotifier,
    DevLogApprovalLinkNotifier,
    GovernanceService,
    IdempotencyConflictError,
    PayloadLimitExceededError,
    PublicDecisionTokenExpiredError,
    PublicDecisionTokenInvalidError,
    PublicDecisionTokenUsedError,
    QuotaExceededError,
    RateLimitExceededError,
    UnauthorizedError,
    WorkspaceValidationError,
    WorkspaceNotFoundError,
)

logger = logging.getLogger("daai.dashboard")


class MissingRepository:
    def open(self) -> None:
        return None

    def close(self) -> None:
        return None

    def __getattr__(self, _: str) -> Any:
        raise RuntimeError(
            "DAAI_DATABASE_URL must be set to use the default app repository"
        )


def build_default_approval_notifier(settings: Settings) -> ApprovalLinkNotifier:
    provider_name = (settings.approval_email_provider or "log").strip().lower()

    if provider_name == "resend":
        if settings.resend_api_key:
            return ApprovalEmailNotifier(
                provider=ResendApprovalEmailProvider(
                    api_key=settings.resend_api_key,
                    from_email=settings.approval_email_from,
                )
            )
        logger.warning(
            "approval_email_provider is resend but DAAI_RESEND_API_KEY is missing; falling back to dev log notifier"
        )

    if not settings.dev_approval_link_logging_enabled:
        return DevLogApprovalLinkNotifier(enabled=False)

    if provider_name == "log":
        return ApprovalEmailNotifier(provider=LogApprovalEmailProvider())

    return DevLogApprovalLinkNotifier(
        enabled=settings.dev_approval_link_logging_enabled
    )


def parse_cors_origins(origins: str | None) -> list[str]:
    if not origins:
        return []
    return [origin.strip() for origin in origins.split(",") if origin.strip()]


def parse_admin_emails(admin_emails: str | None) -> set[str]:
    if not admin_emails:
        return set()
    return {
        email.strip().lower()
        for email in admin_emails.split(",")
        if email.strip()
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    repository = app.state.repository
    if hasattr(repository, "open"):
        repository.open()
    try:
        yield
    finally:
        if hasattr(repository, "close"):
            repository.close()


def create_app(
    repository: GovernanceRepository | None = None,
    settings: Settings | None = None,
    approval_link_notifier: ApprovalLinkNotifier | None = None,
    policy_suggester: PolicySuggester | None = None,
) -> FastAPI:
    app = FastAPI(title="DAAI Governance API", version="0.1.0", lifespan=lifespan)

    resolved_settings = settings or get_settings()
    cors_origins = parse_cors_origins(resolved_settings.cors_origins)
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    if repository is None:
        if resolved_settings.database_url:
            repository = PostgresGovernanceRepository(resolved_settings.database_url)
        else:
            repository = MissingRepository()

    if approval_link_notifier is None:
        approval_link_notifier = build_default_approval_notifier(resolved_settings)
    if policy_suggester is None:
        policy_suggester = OpenAIPolicySuggester(
            api_key=resolved_settings.open_ai_api_key,
            model=resolved_settings.policy_model,
        )

    app.state.repository = repository
    app.state.settings = resolved_settings
    app.state.approval_link_notifier = approval_link_notifier
    app.state.policy_suggester = policy_suggester
    try:
        app.state.dev_seeded_workspace_id = UUID(
            resolved_settings.dev_seeded_workspace_id
        )
    except ValueError:
        app.state.dev_seeded_workspace_id = None

    def build_service() -> GovernanceService:
        return GovernanceService(
            repository=app.state.repository,
            api_key_pepper=app.state.settings.api_key_pepper,
            workspace_key_pepper=app.state.settings.workspace_key_pepper,
            approval_token_pepper=app.state.settings.approval_token_pepper,
            approval_token_ttl_seconds=app.state.settings.approval_token_ttl_seconds,
            public_base_url=app.state.settings.public_base_url,
            dashboard_base_url=app.state.settings.dashboard_base_url,
            approval_link_notifier=app.state.approval_link_notifier,
        )

    def authenticate_dashboard_principal(authorization: str) -> DashboardPrincipal:
        try:
            return verify_supabase_access_token(
                authorization_header=authorization,
                jwt_secret=app.state.settings.supabase_jwt_secret,
                supabase_url=app.state.settings.supabase_url,
            )
        except DashboardAuthError as exc:
            detail = str(exc)
            try:
                metadata = inspect_unverified_token(authorization)
            except DashboardAuthError:
                metadata = None

            logger.warning(
                "dashboard auth failure: detail=%s alg=%s iss=%s sub=%s",
                detail,
                metadata.algorithm if metadata else None,
                metadata.issuer if metadata else None,
                metadata.subject if metadata else None,
            )
            if detail == "dashboard auth is not configured":
                raise HTTPException(status_code=500, detail=detail) from exc
            raise HTTPException(status_code=401, detail=detail) from exc

    def authenticate_admin_principal(authorization: str) -> DashboardPrincipal:
        principal = authenticate_dashboard_principal(authorization)
        admin_emails = parse_admin_emails(app.state.settings.admin_emails)
        principal_email = (principal.email or "").strip().lower()
        if not principal_email or principal_email not in admin_emails:
            raise HTTPException(status_code=403, detail="admin access required")
        return principal

    def to_receipt_response(receipt: Any) -> GovernanceReceiptResponse | None:
        if receipt is None:
            return None
        return GovernanceReceiptResponse(
            id=receipt.id,
            outcome=receipt.outcome,
            reason=receipt.reason,
            policy_type=receipt.policy_type,
            policy_snapshot=receipt.policy_snapshot,
            created_at=receipt.created_at,
        )

    def quota_error_response(exc: QuotaExceededError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.response_body(),
        )

    def generic_public_token_error_response() -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={
                "error": "invalid_or_expired_token",
                "message": "This approval link is invalid, expired, or already used.",
            },
        )

    def request_ip(request: Request) -> str:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",", 1)[0].strip()
        if request.client is not None:
            return request.client.host
        return "unknown"

    def to_dashboard_usage_response(usage: Any) -> DashboardUsageResponse:
        return DashboardUsageResponse(
            plan=usage.plan,
            client_workspaces={
                "used": usage.client_workspaces.used,
                "limit": usage.client_workspaces.limit,
            },
            registered_actions={
                "used": usage.registered_actions.used,
                "limit": usage.registered_actions.limit,
            },
            action_runs_this_month={
                "used": usage.action_runs_this_month.used,
                "limit": usage.action_runs_this_month.limit,
            },
            approval_emails_this_month={
                "used": usage.approval_emails_this_month.used,
                "limit": usage.approval_emails_this_month.limit,
            },
        )

    def to_dashboard_api_key_response(api_key: Any) -> DashboardApiKeyResponse:
        status = "revoked" if api_key.revoked_at is not None else "active"
        return DashboardApiKeyResponse(
            id=api_key.id,
            name=api_key.name,
            workspace_id=api_key.workspace_id,
            workspace_name=api_key.workspace_name,
            workspace_client_name=api_key.workspace_client_name,
            key_prefix=api_key.key_prefix,
            created_at=api_key.created_at,
            created_by=api_key.created_by,
            last_used_at=api_key.last_used_at,
            status=status,
            revoked_at=api_key.revoked_at,
        )

    def to_dashboard_action_response(
        action: Any,
        approver_email: str | None = None,
    ) -> DashboardActionResponse:
        threshold_value = action.policy_config.get("threshold")
        threshold_amount = None
        if threshold_value is not None:
            try:
                threshold_amount = float(threshold_value)
            except (TypeError, ValueError):
                threshold_amount = None
        return DashboardActionResponse(
            id=action.id,
            workspace_id=action.workspace_id,
            action_name=action.action_name,
            title=action.title,
            description=action.description,
            risk_level=action.risk_level,
            is_active=action.is_active,
            policy_type=action.policy_type,
            policy_config=action.policy_config,
            policy=DashboardActionPolicyResponse(
                rule_type=action.policy_type,
                threshold_amount=threshold_amount,
            ),
            approver_email=approver_email,
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/admin/overview", response_model=AdminOverviewResponse)
    def get_admin_overview(
        authorization: str = Header(alias="Authorization"),
    ) -> AdminOverviewResponse:
        authenticate_admin_principal(authorization)
        month_start, next_month_start = current_month_window()
        overview = app.state.repository.get_admin_overview(
            month_start=month_start,
            next_month_start=next_month_start,
        )
        return AdminOverviewResponse(
            total_users=overview.total_users,
            total_workspaces=overview.total_workspaces,
            total_registered_actions=overview.total_registered_actions,
            total_action_runs=overview.total_action_runs,
            pending_approvals=overview.pending_approvals,
            approved_actions=overview.approved_actions,
            blocked_actions=overview.blocked_actions,
            executed_actions=overview.executed_actions,
            failed_actions=overview.failed_actions,
            approval_emails_sent_this_month=overview.approval_emails_sent_this_month,
            activated_users=overview.activated_users,
        )

    @app.get("/v1/admin/users", response_model=list[AdminUserResponse])
    def list_admin_users(
        authorization: str = Header(alias="Authorization"),
        search: Optional[str] = Query(default=None),
        activated_only: bool = Query(default=False),
        sort: str = Query(default="newest", pattern="^(newest|last_activity)$"),
    ) -> list[AdminUserResponse]:
        authenticate_admin_principal(authorization)
        users = app.state.repository.list_admin_users(
            search=search,
            activated_only=activated_only,
            sort=sort,
        )
        return [
            AdminUserResponse(
                email=user.email,
                signed_up_at=user.signed_up_at,
                plan=user.plan,
                workspace_count=user.workspace_count,
                registered_action_count=user.registered_action_count,
                action_run_count=user.action_run_count,
                last_action_run_at=user.last_action_run_at,
                activated=user.activated,
            )
            for user in users
        ]

    @app.get("/v1/admin/workspaces", response_model=list[AdminWorkspaceResponse])
    def list_admin_workspaces(
        authorization: str = Header(alias="Authorization"),
        search: Optional[str] = Query(default=None),
    ) -> list[AdminWorkspaceResponse]:
        authenticate_admin_principal(authorization)
        month_start, next_month_start = current_month_window()
        workspaces = app.state.repository.list_admin_workspaces(
            month_start=month_start,
            next_month_start=next_month_start,
            search=search,
        )
        return [
            AdminWorkspaceResponse(
                workspace_id=workspace.workspace_id,
                workspace_name=workspace.workspace_name,
                client_name=workspace.client_name,
                owner_email=workspace.owner_email,
                plan=workspace.plan,
                registered_action_count=workspace.registered_action_count,
                action_runs_this_month=workspace.action_runs_this_month,
                approval_emails_this_month=workspace.approval_emails_this_month,
                last_action_run_at=workspace.last_action_run_at,
                created_at=workspace.created_at,
            )
            for workspace in workspaces
        ]

    @app.get(
        "/v1/admin/action-runs/recent",
        response_model=list[AdminActionRunResponse],
    )
    def list_admin_recent_action_runs(
        authorization: str = Header(alias="Authorization"),
        search: Optional[str] = Query(default=None),
        governance_status: Optional[GovernanceStatus] = Query(default=None),
        limit: int = Query(default=50, ge=1, le=50),
    ) -> list[AdminActionRunResponse]:
        authenticate_admin_principal(authorization)
        runs = app.state.repository.list_admin_recent_action_runs(
            limit=limit,
            search=search,
            governance_status=governance_status,
        )
        return [
            AdminActionRunResponse(
                action_run_id=run.action_run_id,
                created_at=run.created_at,
                workspace_id=run.workspace_id,
                workspace_name=run.workspace_name,
                owner_email=run.owner_email,
                action_name=run.action_name,
                actor=run.actor,
                governance_status=run.governance_status,
                governance_reason=run.governance_reason,
                executable=run.governance_status
                in (GovernanceStatus.ALLOWED, GovernanceStatus.APPROVED),
                execution_status=run.execution_status,
            )
            for run in runs
        ]

    @app.post("/v1/sdk/intercept", response_model=InterceptResponse)
    def intercept(
        request: InterceptRequest,
        authorization: str = Header(alias="Authorization"),
        workspace_key: str = Header(alias="X-DAAI-Workspace-Key"),
    ) -> InterceptResponse:
        service = build_service()

        try:
            result = service.intercept(
                workspace_key=workspace_key,
                authorization_header=authorization,
                action=request.action,
                payload=request.payload,
                idempotency_key=request.idempotency_key,
                reasoning=request.reasoning,
                source=request.source,
            )
        except UnauthorizedError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except (PayloadLimitExceededError, RateLimitExceededError, QuotaExceededError) as exc:
            return quota_error_response(exc)
        except IdempotencyConflictError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "idempotency_conflict",
                    "message": str(exc),
                },
            ) from exc
        except PolicyEvaluationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return InterceptResponse(
            action_run_id=result.action_run_id,
            governance_status=result.governance_status,
            execution_status=result.execution_status,
            governance_reason=result.governance_reason,
            executable=result.executable,
            idempotent_replay=result.idempotent_replay,
            receipt=to_receipt_response(result.receipt),
        )

    @app.get(
        "/v1/sdk/action-runs/{action_run_id}/status",
        response_model=ActionRunStatusResponse,
    )
    def get_action_run(
        action_run_id: UUID,
        authorization: str = Header(alias="Authorization"),
        workspace_key: str = Header(alias="X-DAAI-Workspace-Key"),
    ) -> ActionRunStatusResponse:
        service = build_service()

        try:
            result = service.get_action_run_status(
                workspace_key=workspace_key,
                authorization_header=authorization,
                action_run_id=action_run_id,
            )
        except UnauthorizedError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except ActionRunNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        return ActionRunStatusResponse(
            action_run_id=result.action_run_id,
            action=result.action,
            governance_status=result.governance_status,
            execution_status=result.execution_status,
            governance_reason=result.governance_reason,
            executable=result.executable,
            receipt=to_receipt_response(result.receipt),
            created_at=result.created_at,
            decided_at=result.decided_at,
        )

    @app.get(
        "/v1/dashboard/workspaces",
        response_model=list[DashboardWorkspaceResponse],
    )
    def list_dashboard_workspaces(
        authorization: str = Header(alias="Authorization"),
    ) -> list[DashboardWorkspaceResponse]:
        service = build_service()
        principal = authenticate_dashboard_principal(authorization)

        workspaces = service.list_dashboard_workspaces(
            dashboard_user_id=principal.user_id,
            dashboard_user_email=principal.email,
            dev_auto_link_seeded_workspace=app.state.settings.dev_auto_link_seeded_workspace,
            dev_seeded_workspace_id=app.state.dev_seeded_workspace_id,
        )

        return [
            DashboardWorkspaceResponse(
                id=workspace.id,
                name=workspace.name,
                created_at=workspace.created_at,
                client_name=workspace.client_name,
                status=workspace.status,
            )
            for workspace in workspaces
        ]

    @app.post(
        "/v1/dashboard/workspaces",
        response_model=CreateDashboardWorkspaceResponse,
    )
    def create_dashboard_workspace(
        request: CreateDashboardWorkspaceRequest,
        authorization: str = Header(alias="Authorization"),
    ) -> CreateDashboardWorkspaceResponse:
        service = build_service()
        principal = authenticate_dashboard_principal(authorization)

        try:
            created = service.create_dashboard_workspace(
                dashboard_user_id=principal.user_id,
                workspace_name=request.workspace_name,
                client_name=request.client_name,
                dashboard_user_email=principal.email,
            )
        except QuotaExceededError as exc:
            return quota_error_response(exc)
        except WorkspaceValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return CreateDashboardWorkspaceResponse(
            id=created.workspace.id,
            name=created.workspace.name,
            client_name=created.workspace.client_name or request.client_name,
            status=created.workspace.status,
            workspace_key=created.workspace_key,
            workspace_key_is_one_time=created.workspace_key_is_one_time,
            created_at=created.workspace.created_at,
        )

    @app.get(
        "/v1/dashboard/workspaces/{workspace_id}",
        response_model=DashboardWorkspaceResponse,
    )
    def get_dashboard_workspace(
        workspace_id: UUID,
        authorization: str = Header(alias="Authorization"),
    ) -> DashboardWorkspaceResponse:
        service = build_service()
        principal = authenticate_dashboard_principal(authorization)

        try:
            workspace = service.get_dashboard_workspace(
                dashboard_user_id=principal.user_id,
                workspace_id=workspace_id,
                dashboard_user_email=principal.email,
                dev_auto_link_seeded_workspace=app.state.settings.dev_auto_link_seeded_workspace,
                dev_seeded_workspace_id=app.state.dev_seeded_workspace_id,
            )
        except WorkspaceNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        return DashboardWorkspaceResponse(
            id=workspace.id,
            name=workspace.name,
            created_at=workspace.created_at,
            client_name=workspace.client_name,
            status=workspace.status,
        )

    @app.delete(
        "/v1/dashboard/workspaces/{workspace_id}",
        response_model=DeleteDashboardWorkspaceResponse,
    )
    def delete_dashboard_workspace(
        workspace_id: UUID,
        request: DeleteDashboardWorkspaceRequest,
        authorization: str = Header(alias="Authorization"),
    ) -> DeleteDashboardWorkspaceResponse:
        service = build_service()
        principal = authenticate_dashboard_principal(authorization)

        try:
            deleted = service.delete_dashboard_workspace(
                dashboard_user_id=principal.user_id,
                workspace_id=workspace_id,
                workspace_name_confirmation=request.workspace_name_confirmation,
                dashboard_user_email=principal.email,
                dev_auto_link_seeded_workspace=app.state.settings.dev_auto_link_seeded_workspace,
                dev_seeded_workspace_id=app.state.dev_seeded_workspace_id,
            )
        except WorkspaceNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except WorkspaceValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return DeleteDashboardWorkspaceResponse(
            id=deleted.workspace_id,
            name=deleted.workspace_name,
            deleted=deleted.deleted,
        )

    @app.get(
        "/v1/dashboard/api-keys",
        response_model=list[DashboardApiKeyResponse],
    )
    def list_dashboard_api_keys(
        authorization: str = Header(alias="Authorization"),
    ) -> list[DashboardApiKeyResponse]:
        service = build_service()
        principal = authenticate_dashboard_principal(authorization)
        api_keys = service.list_dashboard_api_keys(
            dashboard_user_id=principal.user_id,
            dashboard_user_email=principal.email,
            dev_auto_link_seeded_workspace=app.state.settings.dev_auto_link_seeded_workspace,
            dev_seeded_workspace_id=app.state.dev_seeded_workspace_id,
        )
        return [to_dashboard_api_key_response(api_key) for api_key in api_keys]

    @app.post(
        "/v1/dashboard/api-keys",
        response_model=CreateDashboardApiKeyResponse,
    )
    def create_dashboard_api_key(
        request: CreateDashboardApiKeyRequest,
        authorization: str = Header(alias="Authorization"),
    ) -> CreateDashboardApiKeyResponse:
        service = build_service()
        principal = authenticate_dashboard_principal(authorization)
        try:
            created = service.create_dashboard_api_key(
                dashboard_user_id=principal.user_id,
                workspace_id=request.workspace_id,
                name=request.name,
                dashboard_user_email=principal.email,
                dev_auto_link_seeded_workspace=app.state.settings.dev_auto_link_seeded_workspace,
                dev_seeded_workspace_id=app.state.dev_seeded_workspace_id,
            )
        except WorkspaceNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ApiKeyValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        api_key = created.api_key
        status = "revoked" if api_key.revoked_at is not None else "active"
        return CreateDashboardApiKeyResponse(
            id=api_key.id,
            name=api_key.name,
            workspace_id=api_key.workspace_id,
            workspace_name=api_key.workspace_name,
            workspace_client_name=api_key.workspace_client_name,
            key_prefix=api_key.key_prefix,
            created_at=api_key.created_at,
            created_by=api_key.created_by,
            last_used_at=api_key.last_used_at,
            status=status,
            revoked_at=api_key.revoked_at,
            raw_api_key=created.raw_api_key,
            raw_api_key_is_one_time=created.raw_api_key_is_one_time,
        )

    @app.post(
        "/v1/dashboard/api-keys/{api_key_id}/revoke",
        response_model=DashboardApiKeyResponse,
    )
    def revoke_dashboard_api_key(
        api_key_id: UUID,
        authorization: str = Header(alias="Authorization"),
    ) -> DashboardApiKeyResponse:
        service = build_service()
        principal = authenticate_dashboard_principal(authorization)
        try:
            revoked = service.revoke_dashboard_api_key(
                dashboard_user_id=principal.user_id,
                api_key_id=api_key_id,
                dashboard_user_email=principal.email,
                dev_auto_link_seeded_workspace=app.state.settings.dev_auto_link_seeded_workspace,
                dev_seeded_workspace_id=app.state.dev_seeded_workspace_id,
            )
        except ApiKeyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        return to_dashboard_api_key_response(revoked)

    @app.get(
        "/v1/dashboard/workspaces/{workspace_id}/key-info",
        response_model=DashboardWorkspaceKeyInfoResponse,
    )
    def get_dashboard_workspace_key_info(
        workspace_id: UUID,
        authorization: str = Header(alias="Authorization"),
    ) -> DashboardWorkspaceKeyInfoResponse:
        service = build_service()
        principal = authenticate_dashboard_principal(authorization)
        try:
            key_info = service.get_dashboard_workspace_key_info(
                dashboard_user_id=principal.user_id,
                workspace_id=workspace_id,
                dashboard_user_email=principal.email,
                dev_auto_link_seeded_workspace=app.state.settings.dev_auto_link_seeded_workspace,
                dev_seeded_workspace_id=app.state.dev_seeded_workspace_id,
            )
        except WorkspaceNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        return DashboardWorkspaceKeyInfoResponse(
            workspace_id=key_info.workspace.id,
            workspace_name=key_info.workspace.name,
            workspace_client_name=key_info.workspace.client_name,
            key_identifier=key_info.key_identifier,
            full_key_available=key_info.full_key_available,
            workspace_key_is_one_time=True,
        )

    @app.post(
        "/v1/dashboard/workspaces/{workspace_id}/regenerate-key",
        response_model=RegenerateDashboardWorkspaceKeyResponse,
    )
    def regenerate_dashboard_workspace_key(
        workspace_id: UUID,
        authorization: str = Header(alias="Authorization"),
    ) -> RegenerateDashboardWorkspaceKeyResponse:
        service = build_service()
        principal = authenticate_dashboard_principal(authorization)
        try:
            rotated = service.regenerate_dashboard_workspace_key(
                dashboard_user_id=principal.user_id,
                workspace_id=workspace_id,
                dashboard_user_email=principal.email,
                dev_auto_link_seeded_workspace=app.state.settings.dev_auto_link_seeded_workspace,
                dev_seeded_workspace_id=app.state.dev_seeded_workspace_id,
            )
        except WorkspaceNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        return RegenerateDashboardWorkspaceKeyResponse(
            workspace_id=rotated.workspace.id,
            workspace_name=rotated.workspace.name,
            workspace_client_name=rotated.workspace.client_name,
            key_identifier=rotated.key_identifier,
            full_key_available=True,
            workspace_key_is_one_time=rotated.workspace_key_is_one_time,
            workspace_key=rotated.workspace_key,
        )

    @app.get(
        "/v1/dashboard/workspaces/{workspace_id}/actions",
        response_model=list[DashboardActionResponse],
    )
    def list_dashboard_workspace_actions(
        workspace_id: UUID,
        authorization: str = Header(alias="Authorization"),
    ) -> list[DashboardActionResponse]:
        service = build_service()
        principal = authenticate_dashboard_principal(authorization)

        try:
            actions = service.list_dashboard_registered_actions(
                dashboard_user_id=principal.user_id,
                workspace_id=workspace_id,
                dashboard_user_email=principal.email,
                dev_auto_link_seeded_workspace=app.state.settings.dev_auto_link_seeded_workspace,
                dev_seeded_workspace_id=app.state.dev_seeded_workspace_id,
            )
        except WorkspaceNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        approval_settings = service.get_dashboard_workspace_approval_settings(
            dashboard_user_id=principal.user_id,
            workspace_id=workspace_id,
            dashboard_user_email=principal.email,
            dev_auto_link_seeded_workspace=app.state.settings.dev_auto_link_seeded_workspace,
            dev_seeded_workspace_id=app.state.dev_seeded_workspace_id,
        )
        approver_email = next(iter(approval_settings.approval_emails), None)
        return [
            to_dashboard_action_response(
                action=action,
                approver_email=approver_email,
            )
            for action in actions
        ]

    @app.post(
        "/v1/workspaces/{workspace_id}/actions/suggest-policy",
        response_model=PolicySuggestionResponse,
    )
    def suggest_workspace_action_policy(
        workspace_id: UUID,
        request: SuggestActionPolicyRequest,
        authorization: str = Header(alias="Authorization"),
    ) -> PolicySuggestionResponse:
        service = build_service()
        principal = authenticate_dashboard_principal(authorization)

        try:
            service.get_dashboard_workspace(
                dashboard_user_id=principal.user_id,
                workspace_id=workspace_id,
                dashboard_user_email=principal.email,
                dev_auto_link_seeded_workspace=app.state.settings.dev_auto_link_seeded_workspace,
                dev_seeded_workspace_id=app.state.dev_seeded_workspace_id,
            )
        except WorkspaceNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        try:
            return app.state.policy_suggester.suggest(request)
        except Exception:
            logger.warning(
                "policy suggester raised outside its fallback path",
                exc_info=True,
            )
            return fallback_policy_suggestion()

    @app.post(
        "/v1/dashboard/workspaces/{workspace_id}/actions",
        response_model=DashboardActionResponse,
    )
    def create_dashboard_workspace_action(
        workspace_id: UUID,
        request: CreateDashboardActionRequest,
        authorization: str = Header(alias="Authorization"),
    ) -> DashboardActionResponse:
        service = build_service()
        principal = authenticate_dashboard_principal(authorization)

        try:
            result = service.create_dashboard_registered_action(
                dashboard_user_id=principal.user_id,
                workspace_id=workspace_id,
                action_name=request.action_name,
                title=request.title,
                description=request.description,
                risk_level=request.risk_level,
                policy_type=request.policy_type,
                threshold_amount=request.threshold_amount,
                approver_email=request.approver_email,
                explanation=request.explanation,
                approval_triggers=request.approval_triggers,
                risk_factors=request.risk_factors,
                client_facing_summary=request.client_facing_summary,
                receipt_summary_template=request.receipt_summary_template,
                policy_source=request.policy_source,
                setup_answers=request.setup_answers,
                policy_suggestion_snapshot=request.policy_suggestion_snapshot,
                dashboard_user_email=principal.email,
                dev_auto_link_seeded_workspace=app.state.settings.dev_auto_link_seeded_workspace,
                dev_seeded_workspace_id=app.state.dev_seeded_workspace_id,
            )
        except WorkspaceNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except QuotaExceededError as exc:
            return quota_error_response(exc)
        except ActionRegistrationValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except ActionRegistrationConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        return to_dashboard_action_response(
            action=result.action,
            approver_email=result.approver_email,
        )

    @app.get(
        "/v1/dashboard/workspaces/{workspace_id}/metrics",
        response_model=DashboardWorkspaceMetricsResponse,
    )
    def get_dashboard_workspace_metrics(
        workspace_id: UUID,
        authorization: str = Header(alias="Authorization"),
    ) -> DashboardWorkspaceMetricsResponse:
        service = build_service()
        principal = authenticate_dashboard_principal(authorization)

        try:
            metrics = service.get_dashboard_workspace_metrics(
                dashboard_user_id=principal.user_id,
                workspace_id=workspace_id,
                dashboard_user_email=principal.email,
                dev_auto_link_seeded_workspace=app.state.settings.dev_auto_link_seeded_workspace,
                dev_seeded_workspace_id=app.state.dev_seeded_workspace_id,
            )
        except WorkspaceNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        return DashboardWorkspaceMetricsResponse(
            total_runs=metrics.total_runs,
            pending_approval=metrics.pending_approval,
            approved=metrics.approved,
            rejected=metrics.rejected,
            blocked=metrics.blocked,
            allowed=metrics.allowed,
            executed=metrics.executed,
            failed=metrics.failed,
        )

    @app.get(
        "/v1/dashboard/usage",
        response_model=DashboardUsageResponse,
    )
    def get_dashboard_usage(
        authorization: str = Header(alias="Authorization"),
    ) -> DashboardUsageResponse:
        service = build_service()
        principal = authenticate_dashboard_principal(authorization)

        usage = service.get_dashboard_usage(
            dashboard_user_id=principal.user_id,
            dashboard_user_email=principal.email,
            dev_auto_link_seeded_workspace=app.state.settings.dev_auto_link_seeded_workspace,
            dev_seeded_workspace_id=app.state.dev_seeded_workspace_id,
        )
        return to_dashboard_usage_response(usage)

    @app.get(
        "/v1/dashboard/workspaces/{workspace_id}/usage",
        response_model=DashboardUsageResponse,
    )
    def get_dashboard_workspace_usage(
        workspace_id: UUID,
        authorization: str = Header(alias="Authorization"),
    ) -> DashboardUsageResponse:
        service = build_service()
        principal = authenticate_dashboard_principal(authorization)

        try:
            usage = service.get_dashboard_usage(
                dashboard_user_id=principal.user_id,
                workspace_id=workspace_id,
                dashboard_user_email=principal.email,
                dev_auto_link_seeded_workspace=app.state.settings.dev_auto_link_seeded_workspace,
                dev_seeded_workspace_id=app.state.dev_seeded_workspace_id,
            )
        except WorkspaceNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return to_dashboard_usage_response(usage)

    @app.get(
        "/v1/dashboard/workspaces/{workspace_id}/approval-settings",
        response_model=DashboardWorkspaceApprovalSettingsResponse,
    )
    def get_dashboard_workspace_approval_settings(
        workspace_id: UUID,
        authorization: str = Header(alias="Authorization"),
    ) -> DashboardWorkspaceApprovalSettingsResponse:
        service = build_service()
        principal = authenticate_dashboard_principal(authorization)

        try:
            settings_result = service.get_dashboard_workspace_approval_settings(
                dashboard_user_id=principal.user_id,
                workspace_id=workspace_id,
                dashboard_user_email=principal.email,
                dev_auto_link_seeded_workspace=app.state.settings.dev_auto_link_seeded_workspace,
                dev_seeded_workspace_id=app.state.dev_seeded_workspace_id,
            )
        except WorkspaceNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        return DashboardWorkspaceApprovalSettingsResponse(
            workspace_id=settings_result.workspace_id,
            approval_emails=settings_result.approval_emails,
            approval_link_ttl_minutes=settings_result.approval_link_ttl_minutes,
        )

    @app.post(
        "/v1/dashboard/workspaces/{workspace_id}/approval-settings",
        response_model=DashboardWorkspaceApprovalSettingsResponse,
    )
    def update_dashboard_workspace_approval_settings(
        workspace_id: UUID,
        request: DashboardWorkspaceApprovalSettingsRequest,
        authorization: str = Header(alias="Authorization"),
    ) -> DashboardWorkspaceApprovalSettingsResponse:
        service = build_service()
        principal = authenticate_dashboard_principal(authorization)

        try:
            settings_result = service.update_dashboard_workspace_approval_settings(
                dashboard_user_id=principal.user_id,
                workspace_id=workspace_id,
                approval_emails=request.approval_emails,
                approval_link_ttl_minutes=request.approval_link_ttl_minutes,
                dashboard_user_email=principal.email,
                dev_auto_link_seeded_workspace=app.state.settings.dev_auto_link_seeded_workspace,
                dev_seeded_workspace_id=app.state.dev_seeded_workspace_id,
            )
        except WorkspaceNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except WorkspaceValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return DashboardWorkspaceApprovalSettingsResponse(
            workspace_id=settings_result.workspace_id,
            approval_emails=settings_result.approval_emails,
            approval_link_ttl_minutes=settings_result.approval_link_ttl_minutes,
        )

    @app.get(
        "/v1/dashboard/workspaces/{workspace_id}/pending-approvals",
        response_model=list[DashboardPendingApprovalListItemResponse],
    )
    def list_dashboard_workspace_pending_approvals(
        workspace_id: UUID,
        authorization: str = Header(alias="Authorization"),
        limit: int = Query(default=25, ge=1, le=100),
    ) -> list[DashboardPendingApprovalListItemResponse]:
        service = build_service()
        principal = authenticate_dashboard_principal(authorization)

        try:
            pending_items = service.list_dashboard_pending_approvals(
                dashboard_user_id=principal.user_id,
                workspace_id=workspace_id,
                dashboard_user_email=principal.email,
                dev_auto_link_seeded_workspace=app.state.settings.dev_auto_link_seeded_workspace,
                dev_seeded_workspace_id=app.state.dev_seeded_workspace_id,
                limit=limit,
            )
        except WorkspaceNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        return [
            DashboardPendingApprovalListItemResponse(
                action_run_id=item.action_run_id,
                action=item.action,
                governance_reason=item.governance_reason,
                payload_preview=item.payload_preview,
                created_at=item.created_at,
                decision_expires_at=item.decision_expires_at,
            )
            for item in pending_items
        ]

    @app.post(
        "/v1/dashboard/action-runs/{action_run_id}/approve",
        response_model=DashboardActionDecisionResponse,
    )
    def approve_dashboard_action_run(
        action_run_id: UUID,
        authorization: str = Header(alias="Authorization"),
    ) -> DashboardActionDecisionResponse:
        service = build_service()
        principal = authenticate_dashboard_principal(authorization)

        try:
            result = service.approve_dashboard_action_run(
                dashboard_user_id=principal.user_id,
                action_run_id=action_run_id,
                dashboard_user_email=principal.email,
                dev_auto_link_seeded_workspace=app.state.settings.dev_auto_link_seeded_workspace,
                dev_seeded_workspace_id=app.state.dev_seeded_workspace_id,
            )
        except WorkspaceNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ActionRunNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ActionRunConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        return DashboardActionDecisionResponse(
            action_run_id=result.action_run_id,
            governance_status=result.governance_status,
            execution_status=result.execution_status,
            governance_reason=result.governance_reason,
            executable=result.executable,
            receipt=GovernanceReceiptResponse(
                id=result.receipt.id,
                outcome=result.receipt.outcome,
                reason=result.receipt.reason,
                policy_type=result.receipt.policy_type,
                policy_snapshot=result.receipt.policy_snapshot,
                created_at=result.receipt.created_at,
            ),
        )

    @app.post(
        "/v1/dashboard/action-runs/{action_run_id}/reject",
        response_model=DashboardActionDecisionResponse,
    )
    def reject_dashboard_action_run(
        action_run_id: UUID,
        authorization: str = Header(alias="Authorization"),
    ) -> DashboardActionDecisionResponse:
        service = build_service()
        principal = authenticate_dashboard_principal(authorization)

        try:
            result = service.reject_dashboard_action_run(
                dashboard_user_id=principal.user_id,
                action_run_id=action_run_id,
                dashboard_user_email=principal.email,
                dev_auto_link_seeded_workspace=app.state.settings.dev_auto_link_seeded_workspace,
                dev_seeded_workspace_id=app.state.dev_seeded_workspace_id,
            )
        except WorkspaceNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ActionRunNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ActionRunConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        return DashboardActionDecisionResponse(
            action_run_id=result.action_run_id,
            governance_status=result.governance_status,
            execution_status=result.execution_status,
            governance_reason=result.governance_reason,
            executable=result.executable,
            receipt=GovernanceReceiptResponse(
                id=result.receipt.id,
                outcome=result.receipt.outcome,
                reason=result.receipt.reason,
                policy_type=result.receipt.policy_type,
                policy_snapshot=result.receipt.policy_snapshot,
                created_at=result.receipt.created_at,
            ),
        )

    @app.post(
        "/v1/dashboard/action-runs/{action_run_id}/block",
        response_model=DashboardActionDecisionResponse,
    )
    def block_dashboard_action_run(
        action_run_id: UUID,
        authorization: str = Header(alias="Authorization"),
    ) -> DashboardActionDecisionResponse:
        service = build_service()
        principal = authenticate_dashboard_principal(authorization)

        try:
            result = service.block_dashboard_action_run(
                dashboard_user_id=principal.user_id,
                action_run_id=action_run_id,
                dashboard_user_email=principal.email,
                dev_auto_link_seeded_workspace=app.state.settings.dev_auto_link_seeded_workspace,
                dev_seeded_workspace_id=app.state.dev_seeded_workspace_id,
            )
        except WorkspaceNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ActionRunNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ActionRunConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        return DashboardActionDecisionResponse(
            action_run_id=result.action_run_id,
            governance_status=result.governance_status,
            execution_status=result.execution_status,
            governance_reason=result.governance_reason,
            executable=result.executable,
            receipt=GovernanceReceiptResponse(
                id=result.receipt.id,
                outcome=result.receipt.outcome,
                reason=result.receipt.reason,
                policy_type=result.receipt.policy_type,
                policy_snapshot=result.receipt.policy_snapshot,
                created_at=result.receipt.created_at,
            ),
        )

    @app.get(
        "/v1/dashboard/workspaces/{workspace_id}/runs",
        response_model=DashboardActionRunListResponse,
    )
    def list_dashboard_workspace_runs(
        workspace_id: UUID,
        authorization: str = Header(alias="Authorization"),
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=25, ge=1, le=100),
        search: Optional[str] = Query(default=None),
        governance_status: Optional[GovernanceStatus] = Query(default=None),
        execution_status: Optional[ExecutionStatus] = Query(default=None),
    ) -> DashboardActionRunListResponse:
        service = build_service()
        principal = authenticate_dashboard_principal(authorization)

        try:
            runs_page = service.list_dashboard_action_runs(
                dashboard_user_id=principal.user_id,
                workspace_id=workspace_id,
                dashboard_user_email=principal.email,
                dev_auto_link_seeded_workspace=app.state.settings.dev_auto_link_seeded_workspace,
                dev_seeded_workspace_id=app.state.dev_seeded_workspace_id,
                page=page,
                page_size=page_size,
                search=search,
                governance_status=governance_status,
                execution_status=execution_status,
            )
        except WorkspaceNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        return DashboardActionRunListResponse(
            items=[
                DashboardActionRunListItemResponse(
                    action_run_id=run.action_run_id,
                    action=run.action,
                    governance_status=run.governance_status,
                    execution_status=run.execution_status,
                    governance_reason=run.governance_reason,
                    executable=run.executable,
                    payload=run.payload,
                    created_at=run.created_at,
                    decided_at=run.decided_at,
                    receipt=to_receipt_response(run.receipt),
                )
                for run in runs_page.items
            ],
            page=runs_page.page,
            page_size=runs_page.page_size,
            total=runs_page.total,
            total_pages=runs_page.total_pages,
        )

    @app.get(
        "/v1/dashboard/workspaces/{workspace_id}/runs/{action_run_id}",
        response_model=DashboardActionRunDetailResponse,
    )
    def get_dashboard_workspace_run(
        workspace_id: UUID,
        action_run_id: UUID,
        authorization: str = Header(alias="Authorization"),
    ) -> DashboardActionRunDetailResponse:
        service = build_service()
        principal = authenticate_dashboard_principal(authorization)

        try:
            run = service.get_dashboard_action_run(
                dashboard_user_id=principal.user_id,
                workspace_id=workspace_id,
                action_run_id=action_run_id,
                dashboard_user_email=principal.email,
                dev_auto_link_seeded_workspace=app.state.settings.dev_auto_link_seeded_workspace,
                dev_seeded_workspace_id=app.state.dev_seeded_workspace_id,
            )
        except WorkspaceNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ActionRunNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        return DashboardActionRunDetailResponse(
            action_run_id=run.action_run_id,
            action=run.action,
            governance_status=run.governance_status,
            execution_status=run.execution_status,
            governance_reason=run.governance_reason,
            executable=run.executable,
            payload=run.payload,
            policy_snapshot=run.policy_snapshot,
            execution_result=run.execution_result,
            execution_error=run.execution_error,
            execution_reported_at=run.execution_reported_at,
            created_at=run.created_at,
            decided_at=run.decided_at,
            receipt=to_receipt_response(run.receipt),
        )

    @app.post(
        "/v1/sdk/action-runs/{action_run_id}/report-executed",
        response_model=ExecutionReportResponse,
    )
    def report_executed(
        action_run_id: UUID,
        request: ReportExecutedRequest,
        authorization: str = Header(alias="Authorization"),
        workspace_key: str = Header(alias="X-DAAI-Workspace-Key"),
    ) -> ExecutionReportResponse:
        service = build_service()

        try:
            result = service.report_executed(
                workspace_key=workspace_key,
                authorization_header=authorization,
                action_run_id=action_run_id,
                execution_result=request.execution_result,
            )
        except UnauthorizedError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except ActionRunNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ActionRunConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        return ExecutionReportResponse(
            action_run_id=result.action_run_id,
            execution_status=result.execution_status,
            execution_error=result.execution_error,
            execution_reported_at=result.execution_reported_at,
            idempotent_replay=result.idempotent_replay,
        )

    @app.post(
        "/v1/sdk/action-runs/{action_run_id}/report-failed",
        response_model=ExecutionReportResponse,
    )
    def report_failed(
        action_run_id: UUID,
        request: ReportFailedRequest,
        authorization: str = Header(alias="Authorization"),
        workspace_key: str = Header(alias="X-DAAI-Workspace-Key"),
    ) -> ExecutionReportResponse:
        service = build_service()

        try:
            result = service.report_failed(
                workspace_key=workspace_key,
                authorization_header=authorization,
                action_run_id=action_run_id,
                execution_error=request.execution_error,
                execution_result=request.execution_result,
            )
        except UnauthorizedError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except ActionRunNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ActionRunConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        return ExecutionReportResponse(
            action_run_id=result.action_run_id,
            execution_status=result.execution_status,
            execution_error=result.execution_error,
            execution_reported_at=result.execution_reported_at,
            idempotent_replay=result.idempotent_replay,
        )

    @app.post("/v1/public/approve/{token}", response_model=PublicDecisionResponse)
    def approve_action_run(token: str, request: Request) -> PublicDecisionResponse:
        service = build_service()
        try:
            result = service.approve_action_run(
                token=token,
                request_ip=request_ip(request),
            )
        except RateLimitExceededError as exc:
            return quota_error_response(exc)
        except (
            PublicDecisionTokenInvalidError,
            PublicDecisionTokenExpiredError,
            PublicDecisionTokenUsedError,
        ):
            return generic_public_token_error_response()

        return PublicDecisionResponse(
            action_run_id=result.action_run_id,
            governance_status=result.governance_status,
            execution_status=result.execution_status,
            governance_reason=result.governance_reason,
            executable=result.executable,
            receipt=GovernanceReceiptResponse(
                id=result.receipt.id,
                outcome=result.receipt.outcome,
                reason=result.receipt.reason,
                policy_type=result.receipt.policy_type,
                policy_snapshot=result.receipt.policy_snapshot,
                created_at=result.receipt.created_at,
            ),
        )

    @app.post("/v1/public/reject/{token}", response_model=PublicDecisionResponse)
    def reject_action_run(token: str, request: Request) -> PublicDecisionResponse:
        service = build_service()
        try:
            result = service.reject_action_run(
                token=token,
                request_ip=request_ip(request),
            )
        except RateLimitExceededError as exc:
            return quota_error_response(exc)
        except (
            PublicDecisionTokenInvalidError,
            PublicDecisionTokenExpiredError,
            PublicDecisionTokenUsedError,
        ):
            return generic_public_token_error_response()

        return PublicDecisionResponse(
            action_run_id=result.action_run_id,
            governance_status=result.governance_status,
            execution_status=result.execution_status,
            governance_reason=result.governance_reason,
            executable=result.executable,
            receipt=GovernanceReceiptResponse(
                id=result.receipt.id,
                outcome=result.receipt.outcome,
                reason=result.receipt.reason,
                policy_type=result.receipt.policy_type,
                policy_snapshot=result.receipt.policy_snapshot,
                created_at=result.receipt.created_at,
            ),
        )

    @app.post("/v1/public/block/{token}", response_model=PublicDecisionResponse)
    def block_action_run(token: str, request: Request) -> PublicDecisionResponse:
        service = build_service()
        try:
            result = service.block_action_run(
                token=token,
                request_ip=request_ip(request),
            )
        except RateLimitExceededError as exc:
            return quota_error_response(exc)
        except (
            PublicDecisionTokenInvalidError,
            PublicDecisionTokenExpiredError,
            PublicDecisionTokenUsedError,
        ):
            return generic_public_token_error_response()

        return PublicDecisionResponse(
            action_run_id=result.action_run_id,
            governance_status=result.governance_status,
            execution_status=result.execution_status,
            governance_reason=result.governance_reason,
            executable=result.executable,
            receipt=GovernanceReceiptResponse(
                id=result.receipt.id,
                outcome=result.receipt.outcome,
                reason=result.receipt.reason,
                policy_type=result.receipt.policy_type,
                policy_snapshot=result.receipt.policy_snapshot,
                created_at=result.receipt.created_at,
            ),
        )

    return app


app = create_app()
