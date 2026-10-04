from __future__ import annotations

import hashlib
import json
import logging
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from uuid import UUID

from app.domain import (
    ActionRun,
    ApprovalTokenType,
    ExecutionStatus,
    GovernanceReceipt,
    GovernanceStatus,
    PolicyType,
    RegisteredAction,
    Workspace,
    WorkspaceApiKey,
)
from app.hashing import (
    hash_api_key,
    hash_approval_token,
    hash_rate_limit_key,
    hash_workspace_key,
)
from app.policy import evaluate_policy
from app.quotas import (
    FREE_PLAN_LIMITS,
    current_month_window,
    day_window_start,
    limits_for_plan,
    minute_window_start,
)
from app.repository import (
    GovernanceRepository,
    IdempotencyPayloadMismatchError,
    PublicDecisionOutcome,
)


class UnauthorizedError(PermissionError):
    """Raised when auth validation fails for a workspace."""


class ActionRunNotFoundError(LookupError):
    """Raised when action run is not found in the workspace."""


class ActionRunConflictError(RuntimeError):
    """Raised when an execution report conflicts with run state."""


class IdempotencyConflictError(RuntimeError):
    """Raised when an idempotency key is reused with a different payload."""


class WorkspaceNotFoundError(LookupError):
    """Raised when a workspace cannot be found in the authorized scope."""


class WorkspaceValidationError(ValueError):
    """Raised when dashboard workspace creation input is invalid."""


class ApiKeyValidationError(ValueError):
    """Raised when dashboard API key creation input is invalid."""


class ApiKeyNotFoundError(LookupError):
    """Raised when a dashboard API key cannot be found in authorized scope."""


class ActionRegistrationValidationError(ValueError):
    """Raised when dashboard action registration input is invalid."""


class ActionRegistrationConflictError(RuntimeError):
    """Raised when dashboard action registration conflicts with existing data."""


class QuotaExceededError(RuntimeError):
    """Raised when a free beta quota rejects a request."""

    def __init__(
        self,
        *,
        error: str,
        message: str,
        limit: int | None = None,
        status_code: int = 403,
        limit_field: str = "limit",
    ):
        super().__init__(message)
        self.error = error
        self.message = message
        self.limit = limit
        self.status_code = status_code
        self.limit_field = limit_field

    def response_body(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "error": self.error,
            "message": self.message,
        }
        if self.limit is not None:
            body[self.limit_field] = self.limit
        return body


class RateLimitExceededError(QuotaExceededError):
    """Raised when a durable rate limit rejects a request."""


class PayloadLimitExceededError(QuotaExceededError):
    """Raised when an SDK intercept payload exceeds launch limits."""


class PublicDecisionTokenInvalidError(LookupError):
    """Raised when an approve/reject/block token is unknown."""


class PublicDecisionTokenExpiredError(RuntimeError):
    """Raised when an approve/reject/block token has expired."""


class PublicDecisionTokenUsedError(RuntimeError):
    """Raised when an approve/reject/block token was already used."""


@dataclass(frozen=True)
class PendingApprovalLinks:
    workspace_id: UUID
    workspace_name: str
    workspace_client_name: str | None
    action_run_id: UUID
    approval_emails: list[str]
    action: str
    governance_reason: str
    payload_summary: str
    approve_url: str
    reject_url: str
    block_url: str
    expires_at: datetime
    expires_in_text: str


class ApprovalLinkNotifier(Protocol):
    def notify_pending_approval(self, links: PendingApprovalLinks) -> None: ...


class DevLogApprovalLinkNotifier:
    def __init__(self, enabled: bool = True):
        self._enabled = enabled
        self._logger = logging.getLogger("daai.approvals")

    def notify_pending_approval(self, links: PendingApprovalLinks) -> None:
        if not self._enabled:
            return
        if not links.approval_emails:
            self._logger.warning(
                "pending approval has no configured approval emails: workspace_id=%s workspace=%s action_run_id=%s action=%s expires_in=%s approve_url=%s reject_url=%s block_url=%s",
                links.workspace_id,
                links.workspace_name,
                links.action_run_id,
                links.action,
                links.expires_in_text,
                links.approve_url,
                links.reject_url,
                links.block_url,
            )
            return

        self._logger.warning(
            "pending approval link generated: workspace_id=%s workspace=%s action_run_id=%s action=%s to=%s reason=%s payload=%s expires_in=%s approve_url=%s reject_url=%s block_url=%s expires_at=%s",
            links.workspace_id,
            links.workspace_name,
            links.action_run_id,
            links.action,
            ",".join(links.approval_emails),
            links.governance_reason,
            links.payload_summary,
            links.expires_in_text,
            links.approve_url,
            links.reject_url,
            links.block_url,
            links.expires_at.isoformat(),
        )


ACTION_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
RISK_LEVELS = {"low", "medium", "high", "critical"}
ACTION_REGISTRATION_POLICY_TYPES = {
    PolicyType.LOG_ONLY.value,
    PolicyType.ALWAYS_REQUIRE_APPROVAL.value,
    PolicyType.ALWAYS_ALLOW.value,
    PolicyType.REQUIRE_APPROVAL_ABOVE_AMOUNT.value,
    PolicyType.ALWAYS_BLOCK.value,
    PolicyType.REQUIRE_APPROVAL_WHEN_EXTERNAL_RECIPIENT.value,
    PolicyType.REQUIRE_APPROVAL_WHEN_NEW_RECIPIENT.value,
    PolicyType.REQUIRE_APPROVAL_WHEN_NOT_REVERSIBLE.value,
    PolicyType.REQUIRE_APPROVAL_WHEN_DESTRUCTIVE.value,
}
APPROVAL_POLICY_TYPES = {
    PolicyType.ALWAYS_REQUIRE_APPROVAL.value,
    PolicyType.REQUIRE_APPROVAL_ABOVE_AMOUNT.value,
    PolicyType.REQUIRE_APPROVAL_WHEN_EXTERNAL_RECIPIENT.value,
    PolicyType.REQUIRE_APPROVAL_WHEN_NEW_RECIPIENT.value,
    PolicyType.REQUIRE_APPROVAL_WHEN_NOT_REVERSIBLE.value,
    PolicyType.REQUIRE_APPROVAL_WHEN_DESTRUCTIVE.value,
}


@dataclass
class InterceptResult:
    action_run_id: UUID
    governance_status: GovernanceStatus
    execution_status: ExecutionStatus
    governance_reason: str
    executable: bool
    idempotent_replay: bool
    receipt: GovernanceReceipt | None


@dataclass
class ActionRunStatusResult:
    action_run_id: UUID
    action: str
    governance_status: GovernanceStatus
    execution_status: ExecutionStatus
    governance_reason: str
    executable: bool
    receipt: GovernanceReceipt | None
    created_at: Any
    decided_at: Any


@dataclass
class PublicDecisionResult:
    action_run_id: UUID
    governance_status: GovernanceStatus
    execution_status: ExecutionStatus
    governance_reason: str
    executable: bool
    receipt: GovernanceReceipt


@dataclass
class ExecutionReportResult:
    action_run_id: UUID
    execution_status: ExecutionStatus
    execution_error: str | None
    execution_reported_at: Any
    idempotent_replay: bool


@dataclass
class DashboardRunSummaryResult:
    action_run_id: UUID
    action: str
    governance_status: GovernanceStatus
    execution_status: ExecutionStatus
    governance_reason: str
    executable: bool
    payload: dict[str, Any]
    created_at: Any
    decided_at: Any
    receipt: GovernanceReceipt | None


@dataclass
class DashboardActionRunPageResult:
    items: list[DashboardRunSummaryResult]
    page: int
    page_size: int
    total: int
    total_pages: int


@dataclass
class DashboardWorkspaceMetricsResult:
    total_runs: int
    pending_approval: int
    approved: int
    rejected: int
    blocked: int
    allowed: int
    executed: int
    failed: int


@dataclass
class UsageBucketResult:
    used: int
    limit: int


@dataclass
class DashboardUsageResult:
    plan: str
    client_workspaces: UsageBucketResult
    registered_actions: UsageBucketResult
    action_runs_this_month: UsageBucketResult
    approval_emails_this_month: UsageBucketResult


@dataclass
class DashboardWorkspaceApprovalSettingsResult:
    workspace_id: UUID
    approval_emails: list[str]
    approval_link_ttl_minutes: int


@dataclass
class DashboardRegisteredActionResult:
    action: RegisteredAction
    approver_email: str | None


@dataclass
class DashboardPendingApprovalResult:
    action_run_id: UUID
    action: str
    governance_reason: str
    payload_preview: str
    created_at: Any
    decision_expires_at: Any


@dataclass
class DashboardRunDetailResult:
    action_run_id: UUID
    action: str
    governance_status: GovernanceStatus
    execution_status: ExecutionStatus
    governance_reason: str
    executable: bool
    payload: dict[str, Any]
    policy_snapshot: dict[str, Any]
    execution_result: dict[str, Any]
    execution_error: str | None
    execution_reported_at: Any
    created_at: Any
    decided_at: Any
    receipt: GovernanceReceipt | None


@dataclass
class DashboardWorkspaceCreateResult:
    workspace: Workspace
    workspace_key: str
    workspace_key_is_one_time: bool


@dataclass
class DashboardWorkspaceDeleteResult:
    workspace_id: UUID
    workspace_name: str
    deleted: bool


@dataclass
class DashboardApiKeyCreateResult:
    api_key: WorkspaceApiKey
    raw_api_key: str
    raw_api_key_is_one_time: bool


@dataclass
class DashboardWorkspaceKeyInfoResult:
    workspace: Workspace
    key_identifier: str
    full_key_available: bool


@dataclass
class DashboardWorkspaceKeyRegenerateResult:
    workspace: Workspace
    key_identifier: str
    workspace_key: str
    workspace_key_is_one_time: bool


@dataclass(frozen=True)
class AuthenticatedSdkRequest:
    workspace_id: UUID
    api_key_hash: str


class GovernanceService:
    def __init__(
        self,
        repository: GovernanceRepository,
        api_key_pepper: str,
        workspace_key_pepper: str,
        approval_token_pepper: str,
        approval_token_ttl_seconds: int,
        public_base_url: str,
        dashboard_base_url: str | None = None,
        approval_link_notifier: ApprovalLinkNotifier | None = None,
    ):
        self._repository = repository
        self._api_key_pepper = api_key_pepper
        self._workspace_key_pepper = workspace_key_pepper
        self._approval_token_pepper = approval_token_pepper
        self._approval_token_ttl_seconds = approval_token_ttl_seconds
        self._public_base_url = public_base_url.rstrip("/")
        self._dashboard_base_url = (
            dashboard_base_url.rstrip("/")
            if dashboard_base_url
            else self._public_base_url
        )
        self._approval_link_notifier = approval_link_notifier

    def intercept(
        self,
        workspace_key: str,
        authorization_header: str,
        action: str,
        payload: dict[str, Any],
        idempotency_key: str | None,
        reasoning: str | None = None,
        source: dict[str, Any] | None = None,
    ) -> InterceptResult:
        self._enforce_intercept_payload_limits(
            payload=payload,
            reasoning=reasoning,
            source=source,
        )
        authenticated = self._authenticate_sdk_request(
            workspace_key=workspace_key,
            authorization_header=authorization_header,
        )
        workspace_id = authenticated.workspace_id
        self._enforce_intercept_rate_limits(api_key_hash=authenticated.api_key_hash)

        idempotency_payload_hash = (
            _hash_canonical_payload(payload) if idempotency_key else None
        )

        if idempotency_key:
            existing = self._repository.get_action_run_by_idempotency(
                workspace_id=workspace_id,
                action_name=action,
                idempotency_key=idempotency_key,
            )
            if existing is not None:
                existing_payload_hash = (
                    existing.idempotency_payload_hash
                    or _hash_canonical_payload(existing.payload)
                )
                if existing_payload_hash != idempotency_payload_hash:
                    raise IdempotencyConflictError(
                        "This idempotency key was already used with a different payload."
                    )

                receipt = self._repository.get_governance_receipt(
                    workspace_id=workspace_id,
                    action_run_id=existing.id,
                )
                return InterceptResult(
                    action_run_id=existing.id,
                    governance_status=existing.governance_status,
                    execution_status=existing.execution_status,
                    governance_reason=existing.governance_reason,
                    executable=_is_executable(existing.governance_status),
                    idempotent_replay=True,
                    receipt=receipt,
                )

        owner_id = self._repository.get_workspace_owner_id(workspace_id=workspace_id)
        if owner_id is not None:
            owner_plan = self._repository.get_owner_plan(user_id=owner_id)
            owner_limits = limits_for_plan(owner_plan)
            month_start, next_month_start = current_month_window()
            monthly_run_count = self._repository.count_action_runs_for_owner_in_month(
                owner_user_id=owner_id,
                month_start=month_start,
                next_month_start=next_month_start,
            )
            if monthly_run_count >= owner_limits.max_action_runs_per_month:
                raise QuotaExceededError(
                    error="free_plan_monthly_action_run_limit_reached",
                    message=(
                        "Free beta includes 1,000 action-run audit records per month."
                    ),
                    limit=owner_limits.max_action_runs_per_month,
                    status_code=403,
                )

        registered_action = self._repository.get_registered_action(
            workspace_id=workspace_id,
            action_name=action,
        )

        if registered_action is None or not registered_action.is_active:
            governance_status = GovernanceStatus.BLOCKED
            execution_status = ExecutionStatus.NOT_EXECUTED
            governance_reason = (
                "unknown_action" if registered_action is None else "inactive_action"
            )
            policy_snapshot = {
                "policy_type": governance_reason,
                "policy_config": {},
            }
            policy_type = governance_reason
            registered_action_id = None
        else:
            decision = evaluate_policy(
                policy_type=registered_action.policy_type,
                policy_config=registered_action.policy_config,
                payload=payload,
            )
            governance_status = decision.governance_status
            governance_reason = decision.governance_reason
            policy_snapshot = decision.policy_snapshot
            policy_type = registered_action.policy_type
            registered_action_id = registered_action.id

            if governance_status == GovernanceStatus.ALLOWED:
                execution_status = ExecutionStatus.AWAITING_EXECUTION_REPORT
            else:
                execution_status = ExecutionStatus.NOT_EXECUTED

        try:
            action_run = self._repository.create_action_run(
                workspace_id=workspace_id,
                action_name=action,
                registered_action_id=registered_action_id,
                governance_status=governance_status,
                execution_status=execution_status,
                governance_reason=governance_reason,
                payload=payload,
                policy_snapshot=policy_snapshot,
                idempotency_key=idempotency_key,
                idempotency_payload_hash=idempotency_payload_hash,
            )
        except IdempotencyPayloadMismatchError as exc:
            raise IdempotencyConflictError(
                "This idempotency key was already used with a different payload."
            ) from exc

        receipt = None
        if governance_status in (GovernanceStatus.ALLOWED, GovernanceStatus.BLOCKED):
            receipt = self._repository.create_governance_receipt(
                workspace_id=workspace_id,
                action_run_id=action_run.id,
                outcome=governance_status,
                reason=governance_reason,
                policy_type=policy_type,
                policy_snapshot=policy_snapshot,
            )
        elif governance_status == GovernanceStatus.PENDING_APPROVAL:
            action_run, receipt = self._prepare_pending_approval(
                workspace_id=workspace_id,
                action_run=action_run,
            )
            governance_status = action_run.governance_status
            execution_status = action_run.execution_status
            governance_reason = action_run.governance_reason

        return InterceptResult(
            action_run_id=action_run.id,
            governance_status=governance_status,
            execution_status=execution_status,
            governance_reason=governance_reason,
            executable=_is_executable(governance_status),
            idempotent_replay=False,
            receipt=receipt,
        )

    def get_action_run_status(
        self,
        workspace_key: str,
        authorization_header: str,
        action_run_id: UUID,
    ) -> ActionRunStatusResult:
        workspace_id = self._authenticate(
            workspace_key=workspace_key,
            authorization_header=authorization_header,
        )

        action_run = self._repository.get_action_run(
            workspace_id=workspace_id,
            action_run_id=action_run_id,
        )
        if action_run is None:
            raise ActionRunNotFoundError("action run not found")

        receipt = self._repository.get_governance_receipt(
            workspace_id=workspace_id,
            action_run_id=action_run_id,
        )

        return ActionRunStatusResult(
            action_run_id=action_run.id,
            action=action_run.action_name,
            governance_status=action_run.governance_status,
            execution_status=action_run.execution_status,
            governance_reason=action_run.governance_reason,
            executable=_is_executable(action_run.governance_status),
            receipt=receipt,
            created_at=action_run.created_at,
            decided_at=action_run.decided_at,
        )

    def list_dashboard_workspaces(
        self,
        dashboard_user_id: UUID,
        dashboard_user_email: str | None = None,
        dev_auto_link_seeded_workspace: bool = False,
        dev_seeded_workspace_id: UUID | None = None,
    ) -> list[Workspace]:
        self._repository.upsert_profile(
            user_id=dashboard_user_id,
            email=dashboard_user_email,
        )
        workspaces = self._repository.list_workspaces_for_user(user_id=dashboard_user_id)
        if (
            not workspaces
            and dev_auto_link_seeded_workspace
            and dev_seeded_workspace_id is not None
        ):
            self._repository.ensure_workspace_membership(
                workspace_id=dev_seeded_workspace_id,
                user_id=dashboard_user_id,
                role="owner",
            )
            workspaces = self._repository.list_workspaces_for_user(
                user_id=dashboard_user_id
            )
        return workspaces

    def create_dashboard_workspace(
        self,
        dashboard_user_id: UUID,
        workspace_name: str,
        client_name: str,
        dashboard_user_email: str | None = None,
    ) -> DashboardWorkspaceCreateResult:
        normalized_workspace_name = workspace_name.strip()
        normalized_client_name = client_name.strip()
        if not normalized_workspace_name:
            raise WorkspaceValidationError("workspace_name is required")
        if not normalized_client_name:
            raise WorkspaceValidationError("client_name is required")

        self._repository.upsert_profile(
            user_id=dashboard_user_id,
            email=dashboard_user_email,
        )

        plan = self._repository.get_owner_plan(user_id=dashboard_user_id)
        limits = limits_for_plan(plan)
        workspace_key = _generate_workspace_key()
        workspace = self._repository.create_workspace_for_owner(
            owner_user_id=dashboard_user_id,
            name=normalized_workspace_name,
            client_name=normalized_client_name,
            workspace_key_hash=hash_workspace_key(
                workspace_key=workspace_key,
                pepper=self._workspace_key_pepper,
            ),
            active_workspace_limit=limits.max_client_workspaces_per_owner,
            status="active",
        )
        if workspace is None:
            raise QuotaExceededError(
                error="free_plan_workspace_limit_reached",
                message="Free beta allows up to 2 active client workspaces.",
                limit=limits.max_client_workspaces_per_owner,
                status_code=403,
            )

        return DashboardWorkspaceCreateResult(
            workspace=workspace,
            workspace_key=workspace_key,
            workspace_key_is_one_time=True,
        )

    def get_dashboard_workspace(
        self,
        dashboard_user_id: UUID,
        workspace_id: UUID,
        dashboard_user_email: str | None = None,
        dev_auto_link_seeded_workspace: bool = False,
        dev_seeded_workspace_id: UUID | None = None,
    ) -> Workspace:
        _ = self.list_dashboard_workspaces(
            dashboard_user_id=dashboard_user_id,
            dashboard_user_email=dashboard_user_email,
            dev_auto_link_seeded_workspace=dev_auto_link_seeded_workspace,
            dev_seeded_workspace_id=dev_seeded_workspace_id,
        )
        has_access = self._repository.user_has_workspace_access(
            user_id=dashboard_user_id,
            workspace_id=workspace_id,
        )
        if not has_access:
            raise WorkspaceNotFoundError("workspace not found")

        workspace = self._repository.get_workspace(workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError("workspace not found")
        return workspace

    def delete_dashboard_workspace(
        self,
        dashboard_user_id: UUID,
        workspace_id: UUID,
        workspace_name_confirmation: str,
        dashboard_user_email: str | None = None,
        dev_auto_link_seeded_workspace: bool = False,
        dev_seeded_workspace_id: UUID | None = None,
    ) -> DashboardWorkspaceDeleteResult:
        workspace = self.get_dashboard_workspace(
            dashboard_user_id=dashboard_user_id,
            workspace_id=workspace_id,
            dashboard_user_email=dashboard_user_email,
            dev_auto_link_seeded_workspace=dev_auto_link_seeded_workspace,
            dev_seeded_workspace_id=dev_seeded_workspace_id,
        )

        if workspace_name_confirmation != workspace.name:
            raise WorkspaceValidationError(
                "Type the workspace name exactly to confirm deletion."
            )

        deleted = self._repository.delete_workspace_for_owner(
            owner_user_id=dashboard_user_id,
            workspace_id=workspace_id,
        )
        if deleted is None:
            raise WorkspaceNotFoundError("workspace not found")

        return DashboardWorkspaceDeleteResult(
            workspace_id=deleted.id,
            workspace_name=deleted.name,
            deleted=True,
        )

    def list_dashboard_registered_actions(
        self,
        dashboard_user_id: UUID,
        workspace_id: UUID,
        dashboard_user_email: str | None = None,
        dev_auto_link_seeded_workspace: bool = False,
        dev_seeded_workspace_id: UUID | None = None,
    ) -> list[RegisteredAction]:
        _ = self.get_dashboard_workspace(
            dashboard_user_id=dashboard_user_id,
            workspace_id=workspace_id,
            dashboard_user_email=dashboard_user_email,
            dev_auto_link_seeded_workspace=dev_auto_link_seeded_workspace,
            dev_seeded_workspace_id=dev_seeded_workspace_id,
        )
        return self._repository.list_registered_actions(workspace_id=workspace_id)

    def create_dashboard_registered_action(
        self,
        dashboard_user_id: UUID,
        workspace_id: UUID,
        action_name: str,
        title: str,
        description: str,
        risk_level: str,
        policy_type: str,
        threshold_amount: float | None,
        approver_email: str | None,
        explanation: str = "",
        approval_triggers: list[str] | None = None,
        risk_factors: list[str] | None = None,
        client_facing_summary: str = "",
        receipt_summary_template: str = "",
        policy_source: str = "manual",
        setup_answers: dict[str, Any] | None = None,
        policy_suggestion_snapshot: dict[str, Any] | None = None,
        dashboard_user_email: str | None = None,
        dev_auto_link_seeded_workspace: bool = False,
        dev_seeded_workspace_id: UUID | None = None,
    ) -> DashboardRegisteredActionResult:
        workspace = self.get_dashboard_workspace(
            dashboard_user_id=dashboard_user_id,
            workspace_id=workspace_id,
            dashboard_user_email=dashboard_user_email,
            dev_auto_link_seeded_workspace=dev_auto_link_seeded_workspace,
            dev_seeded_workspace_id=dev_seeded_workspace_id,
        )

        normalized_action_name = action_name.strip()
        normalized_title = title.strip()
        normalized_description = description.strip()
        normalized_risk_level = risk_level.strip().lower()
        normalized_policy_type = policy_type.strip().lower()
        normalized_approver_email = (
            approver_email.strip().lower() if approver_email else None
        )
        normalized_policy_source = policy_source.strip().lower()

        if not ACTION_NAME_PATTERN.match(normalized_action_name):
            raise ActionRegistrationValidationError(
                "action_name must start with a lowercase letter and contain only lowercase letters, numbers, and underscores"
            )
        if not normalized_title:
            raise ActionRegistrationValidationError("title is required")
        if normalized_risk_level not in RISK_LEVELS:
            raise ActionRegistrationValidationError(
                "risk_level must be one of low, medium, high, critical"
            )
        if normalized_policy_type not in ACTION_REGISTRATION_POLICY_TYPES:
            raise ActionRegistrationValidationError(
                "policy_type must be a supported deterministic policy type"
            )
        if normalized_policy_source not in {"manual", "llm_suggested_confirmed"}:
            raise ActionRegistrationValidationError(
                "policy_source must be one of manual, llm_suggested_confirmed"
            )
        if (
            normalized_policy_type == PolicyType.REQUIRE_APPROVAL_ABOVE_AMOUNT.value
            and threshold_amount is None
        ):
            raise ActionRegistrationValidationError(
                "threshold_amount is required for require_approval_above_amount"
            )
        if threshold_amount is not None and threshold_amount <= 0:
            raise ActionRegistrationValidationError("threshold_amount must be positive")

        if self._repository.get_registered_action(
            workspace_id=workspace_id,
            action_name=normalized_action_name,
        ):
            raise ActionRegistrationConflictError(
                "action_name already exists in this workspace"
            )

        approval_emails = list(workspace.approval_emails or [])
        if normalized_policy_type in APPROVAL_POLICY_TYPES:
            if not approval_emails and not normalized_approver_email:
                raise ActionRegistrationValidationError(
                    "approver_email is required for approval policies unless the workspace already has an approver"
                )
            if normalized_approver_email and normalized_approver_email not in approval_emails:
                if len(approval_emails) >= 2:
                    raise ActionRegistrationValidationError(
                        "workspace already has the maximum number of approval emails"
                    )
                approval_emails.append(normalized_approver_email)
                updated_workspace = self._repository.update_workspace_approval_settings(
                    workspace_id=workspace_id,
                    approval_emails=approval_emails,
                    approval_link_ttl_minutes=int(
                        workspace.approval_link_ttl_minutes or 15
                    ),
                )
                if updated_workspace is None:
                    raise WorkspaceNotFoundError("workspace not found")
                workspace = updated_workspace
        approver_for_response = next(iter(workspace.approval_emails or []), None)

        policy_config: dict[str, Any] = {
            "policy_source": normalized_policy_source,
            "risk_level": normalized_risk_level,
        }
        if normalized_policy_type == PolicyType.REQUIRE_APPROVAL_ABOVE_AMOUNT.value:
            policy_config["threshold"] = threshold_amount
            policy_config["amount_field"] = "amount"
        if explanation.strip():
            policy_config["explanation"] = explanation.strip()
        if approval_triggers:
            policy_config["approval_triggers"] = list(approval_triggers)
        if risk_factors:
            policy_config["risk_factors"] = list(risk_factors)
        if client_facing_summary.strip():
            policy_config["client_facing_summary"] = client_facing_summary.strip()
        if receipt_summary_template.strip():
            policy_config["receipt_summary_template"] = receipt_summary_template.strip()
        if setup_answers:
            policy_config["setup_answers"] = setup_answers
        if policy_suggestion_snapshot:
            policy_config["policy_suggestion_snapshot"] = policy_suggestion_snapshot

        owner_id = self._repository.get_workspace_owner_id(workspace_id=workspace_id)
        plan = self._repository.get_owner_plan(user_id=owner_id) if owner_id else "free"
        limits = limits_for_plan(plan)
        created_result = self._repository.create_registered_action_with_limit(
            workspace_id=workspace_id,
            action_name=normalized_action_name,
            title=normalized_title,
            description=normalized_description,
            risk_level=normalized_risk_level,
            is_active=True,
            policy_type=normalized_policy_type,
            policy_config=policy_config,
            active_action_limit=limits.max_active_actions_per_workspace,
        )
        if created_result.limit_reached:
            raise QuotaExceededError(
                error="free_plan_action_limit_reached",
                message=(
                    "Free beta allows up to 3 active registered actions per workspace."
                ),
                limit=limits.max_active_actions_per_workspace,
                status_code=403,
            )
        if created_result.conflict or created_result.action is None:
            raise ActionRegistrationConflictError(
                "action_name already exists in this workspace"
            )

        return DashboardRegisteredActionResult(
            action=created_result.action,
            approver_email=approver_for_response,
        )

    def get_dashboard_workspace_metrics(
        self,
        dashboard_user_id: UUID,
        workspace_id: UUID,
        dashboard_user_email: str | None = None,
        dev_auto_link_seeded_workspace: bool = False,
        dev_seeded_workspace_id: UUID | None = None,
    ) -> DashboardWorkspaceMetricsResult:
        _ = self.get_dashboard_workspace(
            dashboard_user_id=dashboard_user_id,
            workspace_id=workspace_id,
            dashboard_user_email=dashboard_user_email,
            dev_auto_link_seeded_workspace=dev_auto_link_seeded_workspace,
            dev_seeded_workspace_id=dev_seeded_workspace_id,
        )

        metrics = self._repository.get_dashboard_run_metrics(workspace_id=workspace_id)
        return DashboardWorkspaceMetricsResult(
            total_runs=metrics.total_runs,
            pending_approval=metrics.pending_approval,
            approved=metrics.approved,
            rejected=metrics.rejected,
            blocked=metrics.blocked,
            allowed=metrics.allowed,
            executed=metrics.executed,
            failed=metrics.failed,
        )

    def get_dashboard_usage(
        self,
        dashboard_user_id: UUID,
        workspace_id: UUID | None = None,
        dashboard_user_email: str | None = None,
        dev_auto_link_seeded_workspace: bool = False,
        dev_seeded_workspace_id: UUID | None = None,
    ) -> DashboardUsageResult:
        self._repository.upsert_profile(
            user_id=dashboard_user_id,
            email=dashboard_user_email,
        )
        if workspace_id is not None:
            _ = self.get_dashboard_workspace(
                dashboard_user_id=dashboard_user_id,
                workspace_id=workspace_id,
                dashboard_user_email=dashboard_user_email,
                dev_auto_link_seeded_workspace=dev_auto_link_seeded_workspace,
                dev_seeded_workspace_id=dev_seeded_workspace_id,
            )
            active_actions = self._repository.count_active_registered_actions(
                workspace_id=workspace_id,
            )
        else:
            active_actions = 0

        plan = self._repository.get_owner_plan(user_id=dashboard_user_id)
        limits = limits_for_plan(plan)
        month_start, next_month_start = current_month_window()
        return DashboardUsageResult(
            plan=plan,
            client_workspaces=UsageBucketResult(
                used=self._repository.count_active_workspaces_for_owner(
                    user_id=dashboard_user_id,
                ),
                limit=limits.max_client_workspaces_per_owner,
            ),
            registered_actions=UsageBucketResult(
                used=active_actions,
                limit=limits.max_active_actions_per_workspace,
            ),
            action_runs_this_month=UsageBucketResult(
                used=self._repository.count_action_runs_for_owner_in_month(
                    owner_user_id=dashboard_user_id,
                    month_start=month_start,
                    next_month_start=next_month_start,
                ),
                limit=limits.max_action_runs_per_month,
            ),
            approval_emails_this_month=UsageBucketResult(
                used=self._repository.count_approval_emails_for_owner_in_month(
                    owner_user_id=dashboard_user_id,
                    month_start=month_start,
                    next_month_start=next_month_start,
                ),
                limit=limits.max_approval_emails_per_month,
            ),
        )

    def get_dashboard_workspace_approval_settings(
        self,
        dashboard_user_id: UUID,
        workspace_id: UUID,
        dashboard_user_email: str | None = None,
        dev_auto_link_seeded_workspace: bool = False,
        dev_seeded_workspace_id: UUID | None = None,
    ) -> DashboardWorkspaceApprovalSettingsResult:
        workspace = self.get_dashboard_workspace(
            dashboard_user_id=dashboard_user_id,
            workspace_id=workspace_id,
            dashboard_user_email=dashboard_user_email,
            dev_auto_link_seeded_workspace=dev_auto_link_seeded_workspace,
            dev_seeded_workspace_id=dev_seeded_workspace_id,
        )

        return DashboardWorkspaceApprovalSettingsResult(
            workspace_id=workspace.id,
            approval_emails=list(workspace.approval_emails or []),
            approval_link_ttl_minutes=int(workspace.approval_link_ttl_minutes or 15),
        )

    def update_dashboard_workspace_approval_settings(
        self,
        dashboard_user_id: UUID,
        workspace_id: UUID,
        approval_emails: list[str],
        approval_link_ttl_minutes: int,
        dashboard_user_email: str | None = None,
        dev_auto_link_seeded_workspace: bool = False,
        dev_seeded_workspace_id: UUID | None = None,
    ) -> DashboardWorkspaceApprovalSettingsResult:
        _ = self.get_dashboard_workspace(
            dashboard_user_id=dashboard_user_id,
            workspace_id=workspace_id,
            dashboard_user_email=dashboard_user_email,
            dev_auto_link_seeded_workspace=dev_auto_link_seeded_workspace,
            dev_seeded_workspace_id=dev_seeded_workspace_id,
        )

        if len(approval_emails) > 2:
            raise WorkspaceValidationError("at most 2 approval emails are allowed")
        if approval_link_ttl_minutes < 5 or approval_link_ttl_minutes > 1440:
            raise WorkspaceValidationError(
                "approval_link_ttl_minutes must be between 5 and 1440"
            )

        updated = self._repository.update_workspace_approval_settings(
            workspace_id=workspace_id,
            approval_emails=approval_emails,
            approval_link_ttl_minutes=approval_link_ttl_minutes,
        )
        if updated is None:
            raise WorkspaceNotFoundError("workspace not found")

        return DashboardWorkspaceApprovalSettingsResult(
            workspace_id=updated.id,
            approval_emails=list(updated.approval_emails or []),
            approval_link_ttl_minutes=int(updated.approval_link_ttl_minutes or 15),
        )

    def list_dashboard_pending_approvals(
        self,
        dashboard_user_id: UUID,
        workspace_id: UUID,
        dashboard_user_email: str | None = None,
        dev_auto_link_seeded_workspace: bool = False,
        dev_seeded_workspace_id: UUID | None = None,
        limit: int = 25,
    ) -> list[DashboardPendingApprovalResult]:
        _ = self.get_dashboard_workspace(
            dashboard_user_id=dashboard_user_id,
            workspace_id=workspace_id,
            dashboard_user_email=dashboard_user_email,
            dev_auto_link_seeded_workspace=dev_auto_link_seeded_workspace,
            dev_seeded_workspace_id=dev_seeded_workspace_id,
        )
        pending_runs = self._repository.list_pending_approvals(
            workspace_id=workspace_id,
            limit=max(1, min(limit, 100)),
        )

        return [
            DashboardPendingApprovalResult(
                action_run_id=item.action_run.id,
                action=item.action_run.action_name,
                governance_reason=item.action_run.governance_reason,
                payload_preview=_payload_summary(item.action_run.payload),
                created_at=item.action_run.created_at,
                decision_expires_at=item.decision_expires_at,
            )
            for item in pending_runs
        ]

    def list_dashboard_action_runs(
        self,
        dashboard_user_id: UUID,
        workspace_id: UUID,
        dashboard_user_email: str | None = None,
        dev_auto_link_seeded_workspace: bool = False,
        dev_seeded_workspace_id: UUID | None = None,
        page: int = 1,
        page_size: int = 25,
        search: str | None = None,
        governance_status: GovernanceStatus | None = None,
        execution_status: ExecutionStatus | None = None,
    ) -> DashboardActionRunPageResult:
        _ = self.get_dashboard_workspace(
            dashboard_user_id=dashboard_user_id,
            workspace_id=workspace_id,
            dashboard_user_email=dashboard_user_email,
            dev_auto_link_seeded_workspace=dev_auto_link_seeded_workspace,
            dev_seeded_workspace_id=dev_seeded_workspace_id,
        )

        safe_page = max(1, page)
        safe_page_size = min(100, max(1, page_size))
        normalized_search = (search or "").strip() or None

        page_result = self._repository.list_action_runs_paginated(
            workspace_id=workspace_id,
            page=safe_page,
            page_size=safe_page_size,
            search=normalized_search,
            governance_status=governance_status,
            execution_status=execution_status,
        )

        summaries: list[DashboardRunSummaryResult] = []
        for run in page_result.items:
            receipt = self._repository.get_governance_receipt(
                workspace_id=workspace_id,
                action_run_id=run.id,
            )
            summaries.append(
                DashboardRunSummaryResult(
                    action_run_id=run.id,
                    action=run.action_name,
                    governance_status=run.governance_status,
                    execution_status=run.execution_status,
                    governance_reason=run.governance_reason,
                    executable=_is_executable(run.governance_status),
                    payload=run.payload,
                    created_at=run.created_at,
                    decided_at=run.decided_at,
                    receipt=receipt,
                )
            )

        total_pages = (page_result.total + safe_page_size - 1) // safe_page_size
        if total_pages == 0:
            total_pages = 1

        return DashboardActionRunPageResult(
            items=summaries,
            page=safe_page,
            page_size=safe_page_size,
            total=page_result.total,
            total_pages=total_pages,
        )

    def get_dashboard_action_run(
        self,
        dashboard_user_id: UUID,
        workspace_id: UUID,
        action_run_id: UUID,
        dashboard_user_email: str | None = None,
        dev_auto_link_seeded_workspace: bool = False,
        dev_seeded_workspace_id: UUID | None = None,
    ) -> DashboardRunDetailResult:
        _ = self.get_dashboard_workspace(
            dashboard_user_id=dashboard_user_id,
            workspace_id=workspace_id,
            dashboard_user_email=dashboard_user_email,
            dev_auto_link_seeded_workspace=dev_auto_link_seeded_workspace,
            dev_seeded_workspace_id=dev_seeded_workspace_id,
        )
        run = self._repository.get_action_run(
            workspace_id=workspace_id,
            action_run_id=action_run_id,
        )
        if run is None:
            raise ActionRunNotFoundError("action run not found")

        receipt = self._repository.get_governance_receipt(
            workspace_id=workspace_id,
            action_run_id=action_run_id,
        )
        return DashboardRunDetailResult(
            action_run_id=run.id,
            action=run.action_name,
            governance_status=run.governance_status,
            execution_status=run.execution_status,
            governance_reason=run.governance_reason,
            executable=_is_executable(run.governance_status),
            payload=run.payload,
            policy_snapshot=run.policy_snapshot,
            execution_result=run.execution_result,
            execution_error=run.execution_error,
            execution_reported_at=run.execution_reported_at,
            created_at=run.created_at,
            decided_at=run.decided_at,
            receipt=receipt,
        )

    def list_dashboard_api_keys(
        self,
        dashboard_user_id: UUID,
        dashboard_user_email: str | None = None,
        dev_auto_link_seeded_workspace: bool = False,
        dev_seeded_workspace_id: UUID | None = None,
    ) -> list[WorkspaceApiKey]:
        _ = self.list_dashboard_workspaces(
            dashboard_user_id=dashboard_user_id,
            dashboard_user_email=dashboard_user_email,
            dev_auto_link_seeded_workspace=dev_auto_link_seeded_workspace,
            dev_seeded_workspace_id=dev_seeded_workspace_id,
        )
        return self._repository.list_workspace_api_keys_for_user(
            user_id=dashboard_user_id
        )

    def create_dashboard_api_key(
        self,
        dashboard_user_id: UUID,
        workspace_id: UUID,
        name: str,
        dashboard_user_email: str | None = None,
        dev_auto_link_seeded_workspace: bool = False,
        dev_seeded_workspace_id: UUID | None = None,
    ) -> DashboardApiKeyCreateResult:
        normalized_name = name.strip()
        if not normalized_name:
            raise ApiKeyValidationError("name is required")

        _ = self.get_dashboard_workspace(
            dashboard_user_id=dashboard_user_id,
            workspace_id=workspace_id,
            dashboard_user_email=dashboard_user_email,
            dev_auto_link_seeded_workspace=dev_auto_link_seeded_workspace,
            dev_seeded_workspace_id=dev_seeded_workspace_id,
        )

        raw_api_key = _generate_api_key()
        created_api_key = self._repository.create_workspace_api_key(
            workspace_id=workspace_id,
            key_hash=hash_api_key(
                api_key=raw_api_key,
                pepper=self._api_key_pepper,
            ),
            key_prefix=_api_key_prefix(raw_api_key),
            name=normalized_name,
            created_by=dashboard_user_id,
        )

        return DashboardApiKeyCreateResult(
            api_key=created_api_key,
            raw_api_key=raw_api_key,
            raw_api_key_is_one_time=True,
        )

    def revoke_dashboard_api_key(
        self,
        dashboard_user_id: UUID,
        api_key_id: UUID,
        dashboard_user_email: str | None = None,
        dev_auto_link_seeded_workspace: bool = False,
        dev_seeded_workspace_id: UUID | None = None,
    ) -> WorkspaceApiKey:
        api_keys = self.list_dashboard_api_keys(
            dashboard_user_id=dashboard_user_id,
            dashboard_user_email=dashboard_user_email,
            dev_auto_link_seeded_workspace=dev_auto_link_seeded_workspace,
            dev_seeded_workspace_id=dev_seeded_workspace_id,
        )

        target = next((api_key for api_key in api_keys if api_key.id == api_key_id), None)
        if target is None:
            raise ApiKeyNotFoundError("api key not found")

        revoked = self._repository.revoke_workspace_api_key(
            workspace_id=target.workspace_id,
            api_key_id=api_key_id,
        )
        if revoked is None:
            raise ApiKeyNotFoundError("api key not found")
        return revoked

    def get_dashboard_workspace_key_info(
        self,
        dashboard_user_id: UUID,
        workspace_id: UUID,
        dashboard_user_email: str | None = None,
        dev_auto_link_seeded_workspace: bool = False,
        dev_seeded_workspace_id: UUID | None = None,
    ) -> DashboardWorkspaceKeyInfoResult:
        workspace = self.get_dashboard_workspace(
            dashboard_user_id=dashboard_user_id,
            workspace_id=workspace_id,
            dashboard_user_email=dashboard_user_email,
            dev_auto_link_seeded_workspace=dev_auto_link_seeded_workspace,
            dev_seeded_workspace_id=dev_seeded_workspace_id,
        )
        workspace_key_hash = self._repository.get_workspace_key_hash(workspace_id=workspace_id)
        if workspace_key_hash is None:
            raise WorkspaceNotFoundError("workspace not found")

        return DashboardWorkspaceKeyInfoResult(
            workspace=workspace,
            key_identifier=_workspace_key_identifier_from_hash(workspace_key_hash),
            full_key_available=False,
        )

    def regenerate_dashboard_workspace_key(
        self,
        dashboard_user_id: UUID,
        workspace_id: UUID,
        dashboard_user_email: str | None = None,
        dev_auto_link_seeded_workspace: bool = False,
        dev_seeded_workspace_id: UUID | None = None,
    ) -> DashboardWorkspaceKeyRegenerateResult:
        workspace = self.get_dashboard_workspace(
            dashboard_user_id=dashboard_user_id,
            workspace_id=workspace_id,
            dashboard_user_email=dashboard_user_email,
            dev_auto_link_seeded_workspace=dev_auto_link_seeded_workspace,
            dev_seeded_workspace_id=dev_seeded_workspace_id,
        )
        workspace_key = _generate_workspace_key()
        workspace_key_hash = hash_workspace_key(
            workspace_key=workspace_key,
            pepper=self._workspace_key_pepper,
        )
        updated_hash = self._repository.update_workspace_key_hash(
            workspace_id=workspace_id,
            workspace_key_hash=workspace_key_hash,
        )
        if updated_hash is None:
            raise WorkspaceNotFoundError("workspace not found")

        return DashboardWorkspaceKeyRegenerateResult(
            workspace=workspace,
            key_identifier=_workspace_key_identifier_from_hash(updated_hash),
            workspace_key=workspace_key,
            workspace_key_is_one_time=True,
        )

    def approve_action_run(
        self,
        token: str,
        request_ip: str | None = None,
    ) -> PublicDecisionResult:
        return self._decide_action_run_by_token(
            token=token,
            token_type=ApprovalTokenType.APPROVE,
            target_status=GovernanceStatus.APPROVED,
            governance_reason="approved_by_human",
            request_ip=request_ip,
        )

    def reject_action_run(
        self,
        token: str,
        request_ip: str | None = None,
    ) -> PublicDecisionResult:
        return self._decide_action_run_by_token(
            token=token,
            token_type=ApprovalTokenType.REJECT,
            target_status=GovernanceStatus.REJECTED,
            governance_reason="rejected_by_human",
            request_ip=request_ip,
        )

    def block_action_run(
        self,
        token: str,
        request_ip: str | None = None,
    ) -> PublicDecisionResult:
        return self._decide_action_run_by_token(
            token=token,
            token_type=ApprovalTokenType.BLOCK,
            target_status=GovernanceStatus.BLOCKED,
            governance_reason="manually_blocked_by_approver",
            request_ip=request_ip,
        )

    def approve_dashboard_action_run(
        self,
        dashboard_user_id: UUID,
        action_run_id: UUID,
        dashboard_user_email: str | None = None,
        dev_auto_link_seeded_workspace: bool = False,
        dev_seeded_workspace_id: UUID | None = None,
    ) -> PublicDecisionResult:
        return self._decide_action_run_from_dashboard(
            dashboard_user_id=dashboard_user_id,
            action_run_id=action_run_id,
            target_status=GovernanceStatus.APPROVED,
            governance_reason="approved_by_human",
            dashboard_user_email=dashboard_user_email,
            dev_auto_link_seeded_workspace=dev_auto_link_seeded_workspace,
            dev_seeded_workspace_id=dev_seeded_workspace_id,
        )

    def reject_dashboard_action_run(
        self,
        dashboard_user_id: UUID,
        action_run_id: UUID,
        dashboard_user_email: str | None = None,
        dev_auto_link_seeded_workspace: bool = False,
        dev_seeded_workspace_id: UUID | None = None,
    ) -> PublicDecisionResult:
        return self._decide_action_run_from_dashboard(
            dashboard_user_id=dashboard_user_id,
            action_run_id=action_run_id,
            target_status=GovernanceStatus.REJECTED,
            governance_reason="rejected_by_human",
            dashboard_user_email=dashboard_user_email,
            dev_auto_link_seeded_workspace=dev_auto_link_seeded_workspace,
            dev_seeded_workspace_id=dev_seeded_workspace_id,
        )

    def block_dashboard_action_run(
        self,
        dashboard_user_id: UUID,
        action_run_id: UUID,
        dashboard_user_email: str | None = None,
        dev_auto_link_seeded_workspace: bool = False,
        dev_seeded_workspace_id: UUID | None = None,
    ) -> PublicDecisionResult:
        return self._decide_action_run_from_dashboard(
            dashboard_user_id=dashboard_user_id,
            action_run_id=action_run_id,
            target_status=GovernanceStatus.BLOCKED,
            governance_reason="manually_blocked_by_approver",
            dashboard_user_email=dashboard_user_email,
            dev_auto_link_seeded_workspace=dev_auto_link_seeded_workspace,
            dev_seeded_workspace_id=dev_seeded_workspace_id,
        )

    def report_executed(
        self,
        workspace_key: str,
        authorization_header: str,
        action_run_id: UUID,
        execution_result: dict[str, Any],
    ) -> ExecutionReportResult:
        workspace_id = self._authenticate(
            workspace_key=workspace_key,
            authorization_header=authorization_header,
        )

        update_result = self._repository.report_executed(
            workspace_id=workspace_id,
            action_run_id=action_run_id,
            execution_result=execution_result,
        )
        action_run = update_result.action_run
        if action_run is None:
            raise ActionRunNotFoundError("action run not found")

        if update_result.updated:
            return ExecutionReportResult(
                action_run_id=action_run.id,
                execution_status=action_run.execution_status,
                execution_error=action_run.execution_error,
                execution_reported_at=action_run.execution_reported_at,
                idempotent_replay=False,
            )

        self._assert_reportable(action_run.governance_status)

        if action_run.execution_status == ExecutionStatus.EXECUTED:
            if (
                action_run.execution_error is None
                and action_run.execution_result == execution_result
            ):
                return ExecutionReportResult(
                    action_run_id=action_run.id,
                    execution_status=action_run.execution_status,
                    execution_error=action_run.execution_error,
                    execution_reported_at=action_run.execution_reported_at,
                    idempotent_replay=True,
                )
            raise ActionRunConflictError(
                "execution already reported as executed with a different execution_result"
            )

        if action_run.execution_status == ExecutionStatus.FAILED:
            raise ActionRunConflictError(
                "execution already reported as failed for this action run"
            )

        raise ActionRunConflictError(
            "execution report is only allowed from awaiting_execution_report status"
        )

    def report_failed(
        self,
        workspace_key: str,
        authorization_header: str,
        action_run_id: UUID,
        execution_error: str,
        execution_result: dict[str, Any],
    ) -> ExecutionReportResult:
        workspace_id = self._authenticate(
            workspace_key=workspace_key,
            authorization_header=authorization_header,
        )

        update_result = self._repository.report_failed(
            workspace_id=workspace_id,
            action_run_id=action_run_id,
            execution_error=execution_error,
            execution_result=execution_result,
        )
        action_run = update_result.action_run
        if action_run is None:
            raise ActionRunNotFoundError("action run not found")

        if update_result.updated:
            return ExecutionReportResult(
                action_run_id=action_run.id,
                execution_status=action_run.execution_status,
                execution_error=action_run.execution_error,
                execution_reported_at=action_run.execution_reported_at,
                idempotent_replay=False,
            )

        self._assert_reportable(action_run.governance_status)

        if action_run.execution_status == ExecutionStatus.FAILED:
            if (
                action_run.execution_error == execution_error
                and action_run.execution_result == execution_result
            ):
                return ExecutionReportResult(
                    action_run_id=action_run.id,
                    execution_status=action_run.execution_status,
                    execution_error=action_run.execution_error,
                    execution_reported_at=action_run.execution_reported_at,
                    idempotent_replay=True,
                )
            raise ActionRunConflictError(
                "execution already reported as failed with different failure details"
            )

        if action_run.execution_status == ExecutionStatus.EXECUTED:
            raise ActionRunConflictError(
                "execution already reported as executed for this action run"
            )

        raise ActionRunConflictError(
            "execution report is only allowed from awaiting_execution_report status"
        )

    def _decide_action_run_by_token(
        self,
        token: str,
        token_type: ApprovalTokenType,
        target_status: GovernanceStatus,
        governance_reason: str,
        request_ip: str | None = None,
    ) -> PublicDecisionResult:
        self._enforce_public_token_rate_limit(request_ip=request_ip)
        token_hash = hash_approval_token(
            token=token,
            pepper=self._approval_token_pepper,
        )

        decision_result = self._repository.apply_public_decision(
            token_hash=token_hash,
            token_type=token_type,
            target_status=target_status,
            governance_reason=governance_reason,
        )

        if decision_result.outcome == PublicDecisionOutcome.INVALID_TOKEN:
            raise PublicDecisionTokenInvalidError("invalid approval token")
        if decision_result.outcome == PublicDecisionOutcome.EXPIRED_TOKEN:
            raise PublicDecisionTokenExpiredError("approval token has expired")
        if decision_result.outcome == PublicDecisionOutcome.USED_TOKEN:
            raise PublicDecisionTokenUsedError("approval token has already been used")

        action_run = decision_result.action_run
        if action_run is None:
            raise RuntimeError("repository returned applied decision without action run")

        policy_type = _policy_type_from_snapshot(action_run.policy_snapshot)
        receipt = self._repository.create_governance_receipt(
            workspace_id=action_run.workspace_id,
            action_run_id=action_run.id,
            outcome=target_status,
            reason=governance_reason,
            policy_type=policy_type,
            policy_snapshot=action_run.policy_snapshot,
        )

        return PublicDecisionResult(
            action_run_id=action_run.id,
            governance_status=action_run.governance_status,
            execution_status=action_run.execution_status,
            governance_reason=action_run.governance_reason,
            executable=_is_executable(action_run.governance_status),
            receipt=receipt,
        )

    def _decide_action_run_from_dashboard(
        self,
        dashboard_user_id: UUID,
        action_run_id: UUID,
        target_status: GovernanceStatus,
        governance_reason: str,
        dashboard_user_email: str | None = None,
        dev_auto_link_seeded_workspace: bool = False,
        dev_seeded_workspace_id: UUID | None = None,
    ) -> PublicDecisionResult:
        action_run = self._repository.get_action_run_by_id(action_run_id=action_run_id)
        if action_run is None:
            raise ActionRunNotFoundError("action run not found")

        _ = self.get_dashboard_workspace(
            dashboard_user_id=dashboard_user_id,
            workspace_id=action_run.workspace_id,
            dashboard_user_email=dashboard_user_email,
            dev_auto_link_seeded_workspace=dev_auto_link_seeded_workspace,
            dev_seeded_workspace_id=dev_seeded_workspace_id,
        )

        update_result = self._repository.apply_dashboard_decision(
            workspace_id=action_run.workspace_id,
            action_run_id=action_run.id,
            target_status=target_status,
            governance_reason=governance_reason,
        )
        if update_result.action_run is None:
            raise ActionRunNotFoundError("action run not found")
        if not update_result.updated:
            raise ActionRunConflictError("action run is already finalized")

        decided = update_result.action_run
        policy_type = _policy_type_from_snapshot(decided.policy_snapshot)
        receipt = self._repository.create_governance_receipt(
            workspace_id=decided.workspace_id,
            action_run_id=decided.id,
            outcome=target_status,
            reason=governance_reason,
            policy_type=policy_type,
            policy_snapshot=decided.policy_snapshot,
        )

        return PublicDecisionResult(
            action_run_id=decided.id,
            governance_status=decided.governance_status,
            execution_status=decided.execution_status,
            governance_reason=decided.governance_reason,
            executable=_is_executable(decided.governance_status),
            receipt=receipt,
        )

    def _authenticate(self, workspace_key: str, authorization_header: str) -> UUID:
        return self._authenticate_sdk_request(
            workspace_key=workspace_key,
            authorization_header=authorization_header,
        ).workspace_id

    def _authenticate_sdk_request(
        self,
        workspace_key: str,
        authorization_header: str,
    ) -> AuthenticatedSdkRequest:
        workspace_id = self._resolve_workspace_id(workspace_key)
        api_key = self._extract_bearer_token(authorization_header)
        api_key_hash = hash_api_key(api_key=api_key, pepper=self._api_key_pepper)
        self._assert_api_key_hash(workspace_id=workspace_id, api_key_hash=api_key_hash)
        return AuthenticatedSdkRequest(
            workspace_id=workspace_id,
            api_key_hash=api_key_hash,
        )

    def _resolve_workspace_id(self, workspace_key: str) -> UUID:
        if not workspace_key:
            raise UnauthorizedError("missing workspace key")

        workspace_key_hash = hash_workspace_key(
            workspace_key=workspace_key,
            pepper=self._workspace_key_pepper,
        )
        workspace_id = self._repository.get_workspace_id_by_workspace_key_hash(
            workspace_key_hash
        )
        if workspace_id is None:
            raise UnauthorizedError("invalid workspace key")
        return workspace_id

    def _assert_api_key(self, workspace_id: UUID, api_key: str) -> None:
        key_hash = hash_api_key(api_key=api_key, pepper=self._api_key_pepper)
        self._assert_api_key_hash(workspace_id=workspace_id, api_key_hash=key_hash)

    def _assert_api_key_hash(self, workspace_id: UUID, api_key_hash: str) -> None:
        is_valid = self._repository.verify_workspace_api_key(
            workspace_id=workspace_id,
            key_hash=api_key_hash,
        )
        if not is_valid:
            raise UnauthorizedError("invalid workspace api key")

    def _extract_bearer_token(self, authorization_header: str) -> str:
        if not authorization_header:
            raise UnauthorizedError("missing authorization header")

        prefix = "Bearer "
        if not authorization_header.startswith(prefix):
            raise UnauthorizedError("invalid authorization header format")

        token = authorization_header[len(prefix) :].strip()
        if not token:
            raise UnauthorizedError("missing bearer token")

        return token

    def _assert_reportable(self, governance_status: GovernanceStatus) -> None:
        if governance_status not in (
            GovernanceStatus.ALLOWED,
            GovernanceStatus.APPROVED,
        ):
            raise ActionRunConflictError(
                "execution reporting is not allowed for this governance status"
            )

    def _enforce_intercept_rate_limits(self, api_key_hash: str) -> None:
        minute_count = self._repository.increment_rate_limit_counter(
            key_type="api_key",
            key_value_hash=api_key_hash,
            endpoint="/v1/sdk/intercept",
            window_start=minute_window_start(),
            window_seconds=60,
        )
        if minute_count > FREE_PLAN_LIMITS.max_intercept_requests_per_minute_per_api_key:
            raise RateLimitExceededError(
                error="intercept_rate_limit_exceeded",
                message="Free beta allows up to 30 intercept requests per minute per API key.",
                limit=FREE_PLAN_LIMITS.max_intercept_requests_per_minute_per_api_key,
                status_code=429,
            )

        day_count = self._repository.increment_rate_limit_counter(
            key_type="api_key",
            key_value_hash=api_key_hash,
            endpoint="/v1/sdk/intercept",
            window_start=day_window_start(),
            window_seconds=86_400,
        )
        if day_count > FREE_PLAN_LIMITS.max_intercept_requests_per_day_per_api_key:
            raise RateLimitExceededError(
                error="intercept_daily_rate_limit_exceeded",
                message="Free beta allows up to 500 intercept requests per day per API key.",
                limit=FREE_PLAN_LIMITS.max_intercept_requests_per_day_per_api_key,
                status_code=429,
            )

    def _enforce_public_token_rate_limit(self, request_ip: str | None) -> None:
        key_material = (request_ip or "unknown").strip() or "unknown"
        key_hash = hash_rate_limit_key(
            value=key_material,
            pepper=self._approval_token_pepper,
        )
        count = self._repository.increment_rate_limit_counter(
            key_type="ip",
            key_value_hash=key_hash,
            endpoint="/v1/public/approval-token",
            window_start=minute_window_start(),
            window_seconds=60,
        )
        if count > FREE_PLAN_LIMITS.max_public_approval_token_attempts_per_minute_per_ip:
            raise RateLimitExceededError(
                error="public_approval_rate_limit_exceeded",
                message="Too many approval link attempts. Try again shortly.",
                limit=FREE_PLAN_LIMITS.max_public_approval_token_attempts_per_minute_per_ip,
                status_code=429,
            )

    def _enforce_intercept_payload_limits(
        self,
        payload: dict[str, Any],
        reasoning: str | None,
        source: dict[str, Any] | None,
    ) -> None:
        try:
            payload_bytes = len(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                    allow_nan=False,
                ).encode("utf-8")
            )
        except (TypeError, ValueError) as exc:
            raise PayloadLimitExceededError(
                error="invalid_payload",
                message="Action input payload must be JSON serializable.",
                status_code=422,
            ) from exc

        if payload_bytes > FREE_PLAN_LIMITS.max_input_payload_size_bytes:
            raise PayloadLimitExceededError(
                error="payload_too_large",
                message="Free beta action input payloads are limited to 16KB.",
                limit=FREE_PLAN_LIMITS.max_input_payload_size_bytes,
                status_code=413,
                limit_field="limit_bytes",
            )

        payload_reasoning = payload.get("reasoning")
        reasoning_value = reasoning if reasoning is not None else payload_reasoning
        if isinstance(reasoning_value, str) and (
            len(reasoning_value) > FREE_PLAN_LIMITS.max_reasoning_size_chars
        ):
            raise PayloadLimitExceededError(
                error="reasoning_too_large",
                message="Free beta action reasoning is limited to 2,000 characters.",
                limit=FREE_PLAN_LIMITS.max_reasoning_size_chars,
                status_code=422,
                limit_field="limit_chars",
            )

        source_value = source if source is not None else payload.get("source")
        source_ref: Any = None
        if isinstance(source_value, dict):
            source_ref = source_value.get("ref")
        if isinstance(source_ref, str) and (
            len(source_ref) > FREE_PLAN_LIMITS.max_source_ref_size_chars
        ):
            raise PayloadLimitExceededError(
                error="source_ref_too_large",
                message="Free beta source.ref values are limited to 500 characters.",
                limit=FREE_PLAN_LIMITS.max_source_ref_size_chars,
                status_code=422,
                limit_field="limit_chars",
            )

    def _prepare_pending_approval(
        self,
        workspace_id: UUID,
        action_run: ActionRun,
    ) -> tuple[ActionRun, GovernanceReceipt | None]:
        owner_id = self._repository.get_workspace_owner_id(workspace_id=workspace_id)
        workspace = self._repository.get_workspace(workspace_id=workspace_id)
        approval_email_count = len(workspace.approval_emails or []) if workspace else 0
        if owner_id is not None and approval_email_count > 0:
            plan = self._repository.get_owner_plan(user_id=owner_id)
            limits = limits_for_plan(plan)
            month_start, next_month_start = current_month_window()
            reserved = self._repository.reserve_approval_email_quota(
                owner_user_id=owner_id,
                workspace_id=workspace_id,
                action_run_id=action_run.id,
                email_count=approval_email_count,
                month_start=month_start,
                next_month_start=next_month_start,
                monthly_limit=limits.max_approval_emails_per_month,
            )
            if not reserved:
                reason = (
                    "Approval email was not sent because the free beta monthly "
                    "approval email limit has been reached."
                )
                update_result = self._repository.apply_dashboard_decision(
                    workspace_id=workspace_id,
                    action_run_id=action_run.id,
                    target_status=GovernanceStatus.BLOCKED,
                    governance_reason=reason,
                )
                blocked_run = update_result.action_run or action_run
                policy_type = _policy_type_from_snapshot(blocked_run.policy_snapshot)
                receipt = self._repository.create_governance_receipt(
                    workspace_id=workspace_id,
                    action_run_id=blocked_run.id,
                    outcome=GovernanceStatus.BLOCKED,
                    reason=reason,
                    policy_type=policy_type,
                    policy_snapshot=blocked_run.policy_snapshot,
                )
                return blocked_run, receipt

        self._maybe_create_approval_tokens(
            workspace_id=workspace_id,
            action_run=action_run,
        )
        return action_run, None

    def _maybe_create_approval_tokens(
        self,
        workspace_id: UUID,
        action_run: ActionRun,
    ) -> None:
        workspace = self._repository.get_workspace(workspace_id=workspace_id)
        if workspace is None:
            return

        ttl_minutes = _resolve_approval_ttl_minutes(
            approval_link_ttl_minutes=workspace.approval_link_ttl_minutes,
            fallback_seconds=self._approval_token_ttl_seconds,
        )

        approve_token = secrets.token_urlsafe(32)
        reject_token = secrets.token_urlsafe(32)
        block_token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)

        created = self._repository.create_action_decision_tokens(
            workspace_id=workspace_id,
            action_run_id=action_run.id,
            approve_token_hash=hash_approval_token(
                token=approve_token,
                pepper=self._approval_token_pepper,
            ),
            reject_token_hash=hash_approval_token(
                token=reject_token,
                pepper=self._approval_token_pepper,
            ),
            block_token_hash=hash_approval_token(
                token=block_token,
                pepper=self._approval_token_pepper,
            ),
            expires_at=expires_at,
        )
        if not created or self._approval_link_notifier is None:
            return

        self._approval_link_notifier.notify_pending_approval(
            PendingApprovalLinks(
                workspace_id=workspace_id,
                workspace_name=workspace.name,
                workspace_client_name=workspace.client_name,
                action_run_id=action_run.id,
                approval_emails=list(workspace.approval_emails or []),
                action=action_run.action_name,
                governance_reason=action_run.governance_reason,
                payload_summary=_payload_summary(action_run.payload),
                approve_url=f"{self._dashboard_base_url}/approve/{approve_token}",
                reject_url=f"{self._dashboard_base_url}/reject/{reject_token}",
                block_url=f"{self._dashboard_base_url}/block/{block_token}",
                expires_at=expires_at,
                expires_in_text=_format_ttl_minutes(ttl_minutes),
            )
        )


def _payload_summary(payload: dict[str, Any]) -> str:
    if not payload:
        return "no payload"
    try:
        compact = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    except TypeError:
        compact = str(payload)
    if len(compact) <= 220:
        return compact
    return f"{compact[:217]}..."


def _hash_canonical_payload(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _resolve_approval_ttl_minutes(
    approval_link_ttl_minutes: int | None,
    fallback_seconds: int,
) -> int:
    if approval_link_ttl_minutes is not None and 5 <= approval_link_ttl_minutes <= 1440:
        return int(approval_link_ttl_minutes)
    fallback_minutes = max(1, fallback_seconds // 60)
    return max(5, min(fallback_minutes, 1440))


def _format_ttl_minutes(ttl_minutes: int) -> str:
    if ttl_minutes == 60:
        return "1 hour"
    if ttl_minutes % 60 == 0:
        hours = ttl_minutes // 60
        return f"{hours} hours"
    if ttl_minutes == 1:
        return "1 minute"
    return f"{ttl_minutes} minutes"


def _is_executable(governance_status: GovernanceStatus) -> bool:
    return governance_status in (
        GovernanceStatus.ALLOWED,
        GovernanceStatus.APPROVED,
    )


def _generate_api_key() -> str:
    return f"daai_sk_{secrets.token_urlsafe(32)}"


def _generate_workspace_key() -> str:
    return f"daai_wk_{secrets.token_urlsafe(24)}"


def _api_key_prefix(raw_api_key: str) -> str:
    return raw_api_key[:12]


def _workspace_key_identifier_from_hash(workspace_key_hash: str) -> str:
    if len(workspace_key_hash) < 8:
        return "daai_wk_********"
    return f"daai_wk_{workspace_key_hash[:4]}********{workspace_key_hash[-4:]}"


def _policy_type_from_snapshot(policy_snapshot: dict[str, Any]) -> str:
    policy_type = policy_snapshot.get("policy_type")
    if isinstance(policy_type, str) and policy_type:
        return policy_type
    return "unknown_action"
