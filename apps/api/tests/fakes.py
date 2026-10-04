from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from app.domain import (
    ActionRun,
    ApprovalTokenType,
    ExecutionStatus,
    GovernanceReceipt,
    GovernanceStatus,
    RegisteredAction,
    Workspace,
    WorkspaceApiKey,
)
from app.repository import (
    AdminActionRunSummary,
    AdminOverviewMetrics,
    AdminUserSummary,
    AdminWorkspaceSummary,
    DashboardDecisionUpdateResult,
    DashboardPendingApprovalRecord,
    DashboardRunMetrics,
    ExecutionReportUpdateResult,
    IdempotencyPayloadMismatchError,
    PaginatedActionRuns,
    PublicDecisionOutcome,
    PublicDecisionUpdateResult,
    RegisteredActionInsertResult,
)


@dataclass
class _DecisionTokenRecord:
    workspace_id: UUID
    action_run_id: UUID
    token_type: ApprovalTokenType
    expires_at: datetime
    used_at: datetime | None


@dataclass
class _WorkspaceApiKeyRecord:
    id: UUID
    workspace_id: UUID
    key_hash: str
    name: str
    key_prefix: str
    created_at: datetime
    created_by: UUID | None
    last_used_at: datetime | None
    revoked_at: datetime | None


@dataclass
class _ApprovalEmailEvent:
    owner_user_id: UUID
    workspace_id: UUID
    action_run_id: UUID
    email_count: int
    created_at: datetime


class InMemoryGovernanceRepository:
    def __init__(self) -> None:
        self._api_keys_by_id: dict[UUID, _WorkspaceApiKeyRecord] = {}
        self._api_key_index: dict[tuple[UUID, str], UUID] = {}
        self._workspace_keys: dict[str, UUID] = {}
        self._workspace_key_hash_by_workspace: dict[UUID, str] = {}
        self._workspaces: dict[UUID, Workspace] = {}
        self._profiles: dict[UUID, str | None] = {}
        self._workspace_memberships: dict[tuple[UUID, UUID], str] = {}
        self._registered_actions: dict[tuple[UUID, str], RegisteredAction] = {}
        self._action_runs: dict[UUID, ActionRun] = {}
        self._idempotency_index: dict[tuple[UUID, str, str], UUID] = {}
        self._receipts_by_run: dict[UUID, GovernanceReceipt] = {}
        self._decision_tokens_by_hash: dict[str, _DecisionTokenRecord] = {}
        self._decision_token_index: dict[tuple[UUID, UUID, ApprovalTokenType], str] = {}
        self._plans: dict[UUID, str] = {}
        self._profile_created_at: dict[UUID, datetime] = {}
        self._approval_email_events: list[_ApprovalEmailEvent] = []
        self._rate_limit_counters: dict[tuple[str, str, str, datetime, int], int] = {}

    def add_workspace_key_hash(
        self,
        workspace_id: UUID,
        workspace_key_hash: str,
        name: str = "Test Workspace",
    ) -> None:
        self._workspace_keys[workspace_key_hash] = workspace_id
        self._workspace_key_hash_by_workspace[workspace_id] = workspace_key_hash
        if workspace_id not in self._workspaces:
            self._workspaces[workspace_id] = Workspace(
                id=workspace_id,
                name=name,
                created_at=datetime.now(timezone.utc),
                approval_emails=[],
                approval_link_ttl_minutes=15,
            )

    def add_api_key_hash(self, workspace_id: UUID, key_hash: str) -> None:
        record = _WorkspaceApiKeyRecord(
            id=uuid4(),
            workspace_id=workspace_id,
            key_hash=key_hash,
            name="Seed API key",
            key_prefix="daai_sk_seed",
            created_at=datetime.now(timezone.utc),
            created_by=None,
            last_used_at=None,
            revoked_at=None,
        )
        self._api_keys_by_id[record.id] = record
        self._api_key_index[(workspace_id, key_hash)] = record.id

    def get_workspace_id_by_workspace_key_hash(self, workspace_key_hash: str) -> UUID | None:
        return self._workspace_keys.get(workspace_key_hash)

    def get_workspace(self, workspace_id: UUID) -> Workspace | None:
        return self._workspaces.get(workspace_id)

    def update_workspace_approval_settings(
        self,
        workspace_id: UUID,
        approval_emails: list[str],
        approval_link_ttl_minutes: int,
    ) -> Workspace | None:
        workspace = self._workspaces.get(workspace_id)
        if workspace is None:
            return None
        workspace.approval_emails = list(approval_emails)
        workspace.approval_link_ttl_minutes = approval_link_ttl_minutes
        return workspace

    def upsert_profile(self, user_id: UUID, email: str | None) -> None:
        if email is None and user_id in self._profiles:
            return
        self._profiles[user_id] = email
        self._plans.setdefault(user_id, "free")
        self._profile_created_at.setdefault(user_id, datetime.now(timezone.utc))

    def get_owner_plan(self, user_id: UUID) -> str:
        return self._plans.get(user_id, "free")

    def get_workspace_owner_id(self, workspace_id: UUID) -> UUID | None:
        owners = [
            user_id
            for (candidate_workspace_id, user_id), role in self._workspace_memberships.items()
            if candidate_workspace_id == workspace_id and role == "owner"
        ]
        return owners[0] if owners else None

    def list_workspaces_for_user(self, user_id: UUID) -> list[Workspace]:
        workspaces: list[Workspace] = []
        for (workspace_id, member_user_id), _role in self._workspace_memberships.items():
            if member_user_id != user_id:
                continue
            workspace = self._workspaces.get(workspace_id)
            if workspace is not None:
                workspaces.append(workspace)
        workspaces.sort(key=lambda workspace: workspace.created_at, reverse=True)
        return workspaces

    def count_active_workspaces_for_owner(self, user_id: UUID) -> int:
        return sum(
            1
            for (workspace_id, member_user_id), role in self._workspace_memberships.items()
            if (
                member_user_id == user_id
                and role == "owner"
                and self._workspaces.get(workspace_id) is not None
                and self._workspaces[workspace_id].status == "active"
            )
        )

    def user_has_workspace_access(self, user_id: UUID, workspace_id: UUID) -> bool:
        return (workspace_id, user_id) in self._workspace_memberships

    def ensure_workspace_membership(
        self,
        workspace_id: UUID,
        user_id: UUID,
        role: str = "owner",
    ) -> bool:
        if workspace_id not in self._workspaces:
            return False
        key = (workspace_id, user_id)
        if key in self._workspace_memberships:
            return False
        self._workspace_memberships[key] = role
        return True

    def create_workspace(
        self,
        name: str,
        client_name: str,
        workspace_key_hash: str,
        status: str = "active",
    ) -> Workspace:
        workspace_id = uuid4()
        workspace = Workspace(
            id=workspace_id,
            name=name,
            created_at=datetime.now(timezone.utc),
            client_name=client_name,
            status=status,
            approval_emails=[],
            approval_link_ttl_minutes=15,
        )
        self._workspaces[workspace_id] = workspace
        self._workspace_keys[workspace_key_hash] = workspace_id
        self._workspace_key_hash_by_workspace[workspace_id] = workspace_key_hash
        return workspace

    def create_workspace_for_owner(
        self,
        owner_user_id: UUID,
        name: str,
        client_name: str,
        workspace_key_hash: str,
        active_workspace_limit: int,
        status: str = "active",
    ) -> Workspace | None:
        if self.count_active_workspaces_for_owner(owner_user_id) >= active_workspace_limit:
            return None
        workspace = self.create_workspace(
            name=name,
            client_name=client_name,
            workspace_key_hash=workspace_key_hash,
            status=status,
        )
        self.ensure_workspace_membership(
            workspace_id=workspace.id,
            user_id=owner_user_id,
            role="owner",
        )
        return workspace

    def delete_workspace_for_owner(
        self,
        owner_user_id: UUID,
        workspace_id: UUID,
    ) -> Workspace | None:
        if self._workspace_memberships.get((workspace_id, owner_user_id)) != "owner":
            return None

        workspace = self._workspaces.pop(workspace_id, None)
        if workspace is None:
            return None

        old_hash = self._workspace_key_hash_by_workspace.pop(workspace_id, None)
        if old_hash is not None:
            self._workspace_keys.pop(old_hash, None)

        api_key_hashes = [
            record.key_hash
            for record in self._api_keys_by_id.values()
            if record.workspace_id == workspace_id
        ]
        for api_key_id, record in list(self._api_keys_by_id.items()):
            if record.workspace_id == workspace_id:
                self._api_keys_by_id.pop(api_key_id, None)
                self._api_key_index.pop((workspace_id, record.key_hash), None)

        for membership_key in list(self._workspace_memberships):
            if membership_key[0] == workspace_id:
                self._workspace_memberships.pop(membership_key, None)

        for action_key in list(self._registered_actions):
            if action_key[0] == workspace_id:
                self._registered_actions.pop(action_key, None)

        deleted_run_ids = [
            run_id
            for run_id, run in self._action_runs.items()
            if run.workspace_id == workspace_id
        ]
        for run_id in deleted_run_ids:
            self._action_runs.pop(run_id, None)
            self._receipts_by_run.pop(run_id, None)

        for idempotency_key, run_id in list(self._idempotency_index.items()):
            if idempotency_key[0] == workspace_id or run_id in deleted_run_ids:
                self._idempotency_index.pop(idempotency_key, None)

        for token_hash, token in list(self._decision_tokens_by_hash.items()):
            if token.workspace_id == workspace_id:
                self._decision_tokens_by_hash.pop(token_hash, None)

        for token_key in list(self._decision_token_index):
            if token_key[0] == workspace_id:
                self._decision_token_index.pop(token_key, None)

        self._approval_email_events = [
            event
            for event in self._approval_email_events
            if event.workspace_id != workspace_id
        ]

        for counter_key in list(self._rate_limit_counters):
            key_type, key_value_hash, endpoint, _window_start, _window_seconds = counter_key
            if (
                key_type == "api_key"
                and endpoint == "/v1/sdk/intercept"
                and key_value_hash in api_key_hashes
            ):
                self._rate_limit_counters.pop(counter_key, None)

        return workspace

    def add_registered_action(
        self,
        workspace_id: UUID,
        action_name: str,
        policy_type: str,
        policy_config: dict[str, Any] | None = None,
        title: str = "",
        description: str = "",
        risk_level: str = "medium",
        is_active: bool = True,
    ) -> RegisteredAction:
        action = RegisteredAction(
            id=uuid4(),
            workspace_id=workspace_id,
            action_name=action_name,
            policy_type=policy_type,
            policy_config=policy_config or {},
            title=title,
            description=description,
            risk_level=risk_level,
            is_active=is_active,
        )
        self._registered_actions[(workspace_id, action_name)] = action
        return action

    def verify_workspace_api_key(self, workspace_id: UUID, key_hash: str) -> bool:
        api_key_id = self._api_key_index.get((workspace_id, key_hash))
        if api_key_id is None:
            return False
        record = self._api_keys_by_id.get(api_key_id)
        if record is None or record.revoked_at is not None:
            return False
        record.last_used_at = datetime.now(timezone.utc)
        return True

    def list_workspace_api_keys_for_user(self, user_id: UUID) -> list[WorkspaceApiKey]:
        workspace_ids = {
            workspace_id
            for (workspace_id, member_user_id), _role in self._workspace_memberships.items()
            if member_user_id == user_id
        }
        api_keys = [
            self._to_workspace_api_key(record)
            for record in self._api_keys_by_id.values()
            if record.workspace_id in workspace_ids
        ]
        api_keys.sort(key=lambda api_key: api_key.created_at, reverse=True)
        return api_keys

    def create_workspace_api_key(
        self,
        workspace_id: UUID,
        key_hash: str,
        key_prefix: str,
        name: str,
        created_by: UUID,
    ) -> WorkspaceApiKey:
        record = _WorkspaceApiKeyRecord(
            id=uuid4(),
            workspace_id=workspace_id,
            key_hash=key_hash,
            name=name,
            key_prefix=key_prefix,
            created_at=datetime.now(timezone.utc),
            created_by=created_by,
            last_used_at=None,
            revoked_at=None,
        )
        self._api_keys_by_id[record.id] = record
        self._api_key_index[(workspace_id, key_hash)] = record.id
        return self._to_workspace_api_key(record)

    def get_workspace_api_key(
        self,
        workspace_id: UUID,
        api_key_id: UUID,
    ) -> WorkspaceApiKey | None:
        record = self._api_keys_by_id.get(api_key_id)
        if record is None or record.workspace_id != workspace_id:
            return None
        return self._to_workspace_api_key(record)

    def revoke_workspace_api_key(
        self,
        workspace_id: UUID,
        api_key_id: UUID,
    ) -> WorkspaceApiKey | None:
        record = self._api_keys_by_id.get(api_key_id)
        if record is None or record.workspace_id != workspace_id:
            return None
        if record.revoked_at is None:
            record.revoked_at = datetime.now(timezone.utc)
        return self._to_workspace_api_key(record)

    def get_workspace_key_hash(self, workspace_id: UUID) -> str | None:
        return self._workspace_key_hash_by_workspace.get(workspace_id)

    def update_workspace_key_hash(
        self,
        workspace_id: UUID,
        workspace_key_hash: str,
    ) -> str | None:
        if workspace_id not in self._workspaces:
            return None
        old_hash = self._workspace_key_hash_by_workspace.get(workspace_id)
        if old_hash is not None:
            self._workspace_keys.pop(old_hash, None)
        self._workspace_keys[workspace_key_hash] = workspace_id
        self._workspace_key_hash_by_workspace[workspace_id] = workspace_key_hash
        return workspace_key_hash

    def get_registered_action(self, workspace_id: UUID, action_name: str) -> RegisteredAction | None:
        return self._registered_actions.get((workspace_id, action_name))

    def list_registered_actions(self, workspace_id: UUID) -> list[RegisteredAction]:
        actions = [
            action
            for (candidate_workspace_id, _), action in self._registered_actions.items()
            if candidate_workspace_id == workspace_id
        ]
        actions.sort(key=lambda action: action.action_name)
        return actions

    def count_active_registered_actions(self, workspace_id: UUID) -> int:
        return sum(
            1
            for action in self.list_registered_actions(workspace_id)
            if action.is_active
        )

    def create_registered_action(
        self,
        workspace_id: UUID,
        action_name: str,
        title: str,
        description: str,
        risk_level: str,
        is_active: bool,
        policy_type: str,
        policy_config: dict[str, Any],
    ) -> RegisteredAction | None:
        if (workspace_id, action_name) in self._registered_actions:
            return None
        return self.add_registered_action(
            workspace_id=workspace_id,
            action_name=action_name,
            policy_type=policy_type,
            policy_config=policy_config,
            title=title,
            description=description,
            risk_level=risk_level,
            is_active=is_active,
        )

    def create_registered_action_with_limit(
        self,
        workspace_id: UUID,
        action_name: str,
        title: str,
        description: str,
        risk_level: str,
        is_active: bool,
        policy_type: str,
        policy_config: dict[str, Any],
        active_action_limit: int,
    ) -> RegisteredActionInsertResult:
        if is_active and self.count_active_registered_actions(workspace_id) >= active_action_limit:
            return RegisteredActionInsertResult(action=None, limit_reached=True)
        if (workspace_id, action_name) in self._registered_actions:
            return RegisteredActionInsertResult(action=None, conflict=True)
        return RegisteredActionInsertResult(
            action=self.add_registered_action(
                workspace_id=workspace_id,
                action_name=action_name,
                policy_type=policy_type,
                policy_config=policy_config,
                title=title,
                description=description,
                risk_level=risk_level,
                is_active=is_active,
            )
        )

    def get_action_run_by_idempotency(
        self,
        workspace_id: UUID,
        action_name: str,
        idempotency_key: str,
    ) -> ActionRun | None:
        run_id = self._idempotency_index.get((workspace_id, action_name, idempotency_key))
        if run_id is None:
            return None
        return self._action_runs[run_id]

    def create_action_run(
        self,
        workspace_id: UUID,
        action_name: str,
        registered_action_id: UUID | None,
        governance_status: GovernanceStatus,
        execution_status: ExecutionStatus,
        governance_reason: str,
        payload: dict[str, Any],
        policy_snapshot: dict[str, Any],
        idempotency_key: str | None,
        idempotency_payload_hash: str | None,
    ) -> ActionRun:
        if idempotency_key is not None:
            existing_id = self._idempotency_index.get(
                (workspace_id, action_name, idempotency_key)
            )
            if existing_id is not None:
                existing = self._action_runs[existing_id]
                if (
                    existing.idempotency_payload_hash is not None
                    and existing.idempotency_payload_hash != idempotency_payload_hash
                ) or (
                    existing.idempotency_payload_hash is None
                    and existing.payload != payload
                ):
                    raise IdempotencyPayloadMismatchError(
                        "idempotency key was already used with a different payload"
                    )
                return existing

        now = datetime.now(timezone.utc)
        run = ActionRun(
            id=uuid4(),
            workspace_id=workspace_id,
            action_name=action_name,
            governance_status=governance_status,
            execution_status=execution_status,
            governance_reason=governance_reason,
            payload=payload,
            policy_snapshot=policy_snapshot,
            idempotency_key=idempotency_key,
            idempotency_payload_hash=idempotency_payload_hash,
            execution_result={},
            execution_error=None,
            execution_reported_at=None,
            executed_at=None,
            failed_at=None,
            created_at=now,
            decided_at=now,
        )
        self._action_runs[run.id] = run

        if idempotency_key is not None:
            self._idempotency_index[(workspace_id, action_name, idempotency_key)] = run.id

        return run

    def count_action_runs_for_owner_in_month(
        self,
        owner_user_id: UUID,
        month_start: datetime,
        next_month_start: datetime,
    ) -> int:
        workspace_ids = {
            workspace_id
            for (workspace_id, user_id), role in self._workspace_memberships.items()
            if user_id == owner_user_id and role == "owner"
        }
        return sum(
            1
            for run in self._action_runs.values()
            if (
                run.workspace_id in workspace_ids
                and month_start <= run.created_at < next_month_start
            )
        )

    def count_approval_emails_for_owner_in_month(
        self,
        owner_user_id: UUID,
        month_start: datetime,
        next_month_start: datetime,
    ) -> int:
        return sum(
            event.email_count
            for event in self._approval_email_events
            if (
                event.owner_user_id == owner_user_id
                and month_start <= event.created_at < next_month_start
            )
        )

    def reserve_approval_email_quota(
        self,
        owner_user_id: UUID,
        workspace_id: UUID,
        action_run_id: UUID,
        email_count: int,
        month_start: datetime,
        next_month_start: datetime,
        monthly_limit: int,
    ) -> bool:
        if email_count <= 0:
            return True
        current_count = self.count_approval_emails_for_owner_in_month(
            owner_user_id=owner_user_id,
            month_start=month_start,
            next_month_start=next_month_start,
        )
        if current_count + email_count > monthly_limit:
            return False
        self._approval_email_events.append(
            _ApprovalEmailEvent(
                owner_user_id=owner_user_id,
                workspace_id=workspace_id,
                action_run_id=action_run_id,
                email_count=email_count,
                created_at=datetime.now(timezone.utc),
            )
        )
        return True

    def increment_rate_limit_counter(
        self,
        key_type: str,
        key_value_hash: str,
        endpoint: str,
        window_start: datetime,
        window_seconds: int,
    ) -> int:
        key = (key_type, key_value_hash, endpoint, window_start, window_seconds)
        next_count = self._rate_limit_counters.get(key, 0) + 1
        self._rate_limit_counters[key] = next_count
        return next_count

    def create_governance_receipt(
        self,
        workspace_id: UUID,
        action_run_id: UUID,
        outcome: GovernanceStatus,
        reason: str,
        policy_type: str,
        policy_snapshot: dict[str, Any],
    ) -> GovernanceReceipt:
        existing = self._receipts_by_run.get(action_run_id)
        if existing is not None:
            return existing

        receipt = GovernanceReceipt(
            id=uuid4(),
            workspace_id=workspace_id,
            action_run_id=action_run_id,
            outcome=outcome.value,
            reason=reason,
            policy_type=policy_type,
            policy_snapshot=policy_snapshot,
            created_at=datetime.now(timezone.utc),
        )
        self._receipts_by_run[action_run_id] = receipt
        return receipt

    def get_governance_receipt(
        self,
        workspace_id: UUID,
        action_run_id: UUID,
    ) -> GovernanceReceipt | None:
        receipt = self._receipts_by_run.get(action_run_id)
        if receipt is None:
            return None
        if receipt.workspace_id != workspace_id:
            return None
        return receipt

    def get_action_run(self, workspace_id: UUID, action_run_id: UUID) -> ActionRun | None:
        run = self._action_runs.get(action_run_id)
        if run is None:
            return None
        if run.workspace_id != workspace_id:
            return None
        return run

    def get_action_run_by_id(self, action_run_id: UUID) -> ActionRun | None:
        return self._action_runs.get(action_run_id)

    def list_action_runs(self, workspace_id: UUID, limit: int = 100) -> list[ActionRun]:
        runs = [
            run
            for run in self._action_runs.values()
            if run.workspace_id == workspace_id
        ]
        runs.sort(key=lambda run: run.created_at, reverse=True)
        return runs[:limit]

    def get_dashboard_run_metrics(self, workspace_id: UUID) -> DashboardRunMetrics:
        runs = [run for run in self._action_runs.values() if run.workspace_id == workspace_id]
        return DashboardRunMetrics(
            total_runs=len(runs),
            pending_approval=sum(
                1 for run in runs if run.governance_status == GovernanceStatus.PENDING_APPROVAL
            ),
            approved=sum(1 for run in runs if run.governance_status == GovernanceStatus.APPROVED),
            rejected=sum(1 for run in runs if run.governance_status == GovernanceStatus.REJECTED),
            blocked=sum(1 for run in runs if run.governance_status == GovernanceStatus.BLOCKED),
            allowed=sum(1 for run in runs if run.governance_status == GovernanceStatus.ALLOWED),
            executed=sum(1 for run in runs if run.execution_status == ExecutionStatus.EXECUTED),
            failed=sum(1 for run in runs if run.execution_status == ExecutionStatus.FAILED),
        )

    def list_action_runs_paginated(
        self,
        workspace_id: UUID,
        page: int,
        page_size: int,
        search: str | None = None,
        governance_status: GovernanceStatus | None = None,
        execution_status: ExecutionStatus | None = None,
    ) -> PaginatedActionRuns:
        runs = [run for run in self._action_runs.values() if run.workspace_id == workspace_id]

        if governance_status is not None:
            runs = [run for run in runs if run.governance_status == governance_status]

        if execution_status is not None:
            runs = [run for run in runs if run.execution_status == execution_status]

        if search:
            search_lower = search.lower()
            runs = [
                run
                for run in runs
                if (
                    search_lower in run.action_name.lower()
                    or search_lower in run.governance_reason.lower()
                    or search_lower in str(run.payload).lower()
                )
            ]

        runs.sort(key=lambda run: run.created_at, reverse=True)
        total = len(runs)
        offset = (page - 1) * page_size
        return PaginatedActionRuns(items=runs[offset : offset + page_size], total=total)

    def list_pending_approvals(
        self,
        workspace_id: UUID,
        limit: int = 25,
    ) -> list[DashboardPendingApprovalRecord]:
        runs = [
            run
            for run in self._action_runs.values()
            if (
                run.workspace_id == workspace_id
                and run.governance_status == GovernanceStatus.PENDING_APPROVAL
            )
        ]
        runs.sort(key=lambda run: run.created_at, reverse=True)
        records: list[DashboardPendingApprovalRecord] = []
        for run in runs[:limit]:
            token_expiries = [
                token.expires_at
                for token in self._decision_tokens_by_hash.values()
                if (
                    token.workspace_id == workspace_id
                    and token.action_run_id == run.id
                    and token.used_at is None
                )
            ]
            expires_at = min(token_expiries) if token_expiries else None
            records.append(
                DashboardPendingApprovalRecord(
                    action_run=run,
                    decision_expires_at=expires_at,
                )
            )
        return records

    def create_action_decision_tokens(
        self,
        workspace_id: UUID,
        action_run_id: UUID,
        approve_token_hash: str,
        reject_token_hash: str,
        block_token_hash: str,
        expires_at: datetime,
    ) -> bool:
        approve_key = (workspace_id, action_run_id, ApprovalTokenType.APPROVE)
        reject_key = (workspace_id, action_run_id, ApprovalTokenType.REJECT)
        block_key = (workspace_id, action_run_id, ApprovalTokenType.BLOCK)

        if (
            approve_key in self._decision_token_index
            or reject_key in self._decision_token_index
            or block_key in self._decision_token_index
            or approve_token_hash in self._decision_tokens_by_hash
            or reject_token_hash in self._decision_tokens_by_hash
            or block_token_hash in self._decision_tokens_by_hash
        ):
            return False

        self._decision_token_index[approve_key] = approve_token_hash
        self._decision_tokens_by_hash[approve_token_hash] = _DecisionTokenRecord(
            workspace_id=workspace_id,
            action_run_id=action_run_id,
            token_type=ApprovalTokenType.APPROVE,
            expires_at=expires_at,
            used_at=None,
        )

        self._decision_token_index[reject_key] = reject_token_hash
        self._decision_tokens_by_hash[reject_token_hash] = _DecisionTokenRecord(
            workspace_id=workspace_id,
            action_run_id=action_run_id,
            token_type=ApprovalTokenType.REJECT,
            expires_at=expires_at,
            used_at=None,
        )

        self._decision_token_index[block_key] = block_token_hash
        self._decision_tokens_by_hash[block_token_hash] = _DecisionTokenRecord(
            workspace_id=workspace_id,
            action_run_id=action_run_id,
            token_type=ApprovalTokenType.BLOCK,
            expires_at=expires_at,
            used_at=None,
        )
        return True

    def apply_public_decision(
        self,
        token_hash: str,
        token_type: ApprovalTokenType,
        target_status: GovernanceStatus,
        governance_reason: str,
    ) -> PublicDecisionUpdateResult:
        token = self._decision_tokens_by_hash.get(token_hash)
        if token is None or token.token_type != token_type:
            return PublicDecisionUpdateResult(
                action_run=None,
                outcome=PublicDecisionOutcome.INVALID_TOKEN,
            )

        if token.used_at is not None:
            return PublicDecisionUpdateResult(
                action_run=None,
                outcome=PublicDecisionOutcome.USED_TOKEN,
            )

        now = datetime.now(timezone.utc)
        if token.expires_at <= now:
            token.used_at = now
            return PublicDecisionUpdateResult(
                action_run=None,
                outcome=PublicDecisionOutcome.EXPIRED_TOKEN,
            )

        run = self.get_action_run(
            workspace_id=token.workspace_id,
            action_run_id=token.action_run_id,
        )
        if run is None or run.governance_status != GovernanceStatus.PENDING_APPROVAL:
            token.used_at = now
            return PublicDecisionUpdateResult(
                action_run=None,
                outcome=PublicDecisionOutcome.USED_TOKEN,
            )

        run.governance_status = target_status
        run.governance_reason = governance_reason
        run.decided_at = now
        if target_status == GovernanceStatus.APPROVED:
            run.execution_status = ExecutionStatus.AWAITING_EXECUTION_REPORT
        else:
            run.execution_status = ExecutionStatus.NOT_EXECUTED

        for candidate in self._decision_tokens_by_hash.values():
            if (
                candidate.workspace_id == token.workspace_id
                and candidate.action_run_id == token.action_run_id
                and candidate.used_at is None
            ):
                candidate.used_at = now

        return PublicDecisionUpdateResult(
            action_run=run,
            outcome=PublicDecisionOutcome.APPLIED,
        )

    def apply_dashboard_decision(
        self,
        workspace_id: UUID,
        action_run_id: UUID,
        target_status: GovernanceStatus,
        governance_reason: str,
    ) -> DashboardDecisionUpdateResult:
        run = self.get_action_run(workspace_id=workspace_id, action_run_id=action_run_id)
        if run is None:
            return DashboardDecisionUpdateResult(action_run=None, updated=False)

        if run.governance_status != GovernanceStatus.PENDING_APPROVAL:
            return DashboardDecisionUpdateResult(action_run=run, updated=False)

        now = datetime.now(timezone.utc)
        run.governance_status = target_status
        run.governance_reason = governance_reason
        run.decided_at = now
        if target_status == GovernanceStatus.APPROVED:
            run.execution_status = ExecutionStatus.AWAITING_EXECUTION_REPORT
        else:
            run.execution_status = ExecutionStatus.NOT_EXECUTED

        for candidate in self._decision_tokens_by_hash.values():
            if (
                candidate.workspace_id == workspace_id
                and candidate.action_run_id == action_run_id
                and candidate.used_at is None
            ):
                candidate.used_at = now

        return DashboardDecisionUpdateResult(action_run=run, updated=True)

    def report_executed(
        self,
        workspace_id: UUID,
        action_run_id: UUID,
        execution_result: dict[str, Any],
    ) -> ExecutionReportUpdateResult:
        run = self.get_action_run(workspace_id=workspace_id, action_run_id=action_run_id)
        if run is None:
            return ExecutionReportUpdateResult(action_run=None, updated=False)

        if (
            run.governance_status not in (GovernanceStatus.ALLOWED, GovernanceStatus.APPROVED)
            or run.execution_status != ExecutionStatus.AWAITING_EXECUTION_REPORT
        ):
            return ExecutionReportUpdateResult(action_run=run, updated=False)

        now = datetime.now(timezone.utc)
        run.execution_status = ExecutionStatus.EXECUTED
        run.execution_result = execution_result
        run.execution_error = None
        run.execution_reported_at = now
        run.executed_at = now
        run.failed_at = None
        return ExecutionReportUpdateResult(action_run=run, updated=True)

    def report_failed(
        self,
        workspace_id: UUID,
        action_run_id: UUID,
        execution_error: str,
        execution_result: dict[str, Any],
    ) -> ExecutionReportUpdateResult:
        run = self.get_action_run(workspace_id=workspace_id, action_run_id=action_run_id)
        if run is None:
            return ExecutionReportUpdateResult(action_run=None, updated=False)

        if (
            run.governance_status not in (GovernanceStatus.ALLOWED, GovernanceStatus.APPROVED)
            or run.execution_status != ExecutionStatus.AWAITING_EXECUTION_REPORT
        ):
            return ExecutionReportUpdateResult(action_run=run, updated=False)

        now = datetime.now(timezone.utc)
        run.execution_status = ExecutionStatus.FAILED
        run.execution_result = execution_result
        run.execution_error = execution_error
        run.execution_reported_at = now
        run.executed_at = None
        run.failed_at = now
        return ExecutionReportUpdateResult(action_run=run, updated=True)

    def get_admin_overview(
        self,
        month_start: datetime,
        next_month_start: datetime,
    ) -> AdminOverviewMetrics:
        runs = list(self._action_runs.values())
        return AdminOverviewMetrics(
            total_users=len(self._profiles),
            total_workspaces=len(self._workspaces),
            total_registered_actions=len(self._registered_actions),
            total_action_runs=len(runs),
            pending_approvals=sum(
                1
                for run in runs
                if run.governance_status == GovernanceStatus.PENDING_APPROVAL
            ),
            approved_actions=sum(
                1 for run in runs if run.governance_status == GovernanceStatus.APPROVED
            ),
            blocked_actions=sum(
                1 for run in runs if run.governance_status == GovernanceStatus.BLOCKED
            ),
            executed_actions=sum(
                1 for run in runs if run.execution_status == ExecutionStatus.EXECUTED
            ),
            failed_actions=sum(
                1 for run in runs if run.execution_status == ExecutionStatus.FAILED
            ),
            approval_emails_sent_this_month=sum(
                event.email_count
                for event in self._approval_email_events
                if month_start <= event.created_at < next_month_start
            ),
            activated_users=sum(
                1
                for user_id in self._profiles
                if self._admin_user_counts(user_id)["workspace_count"] > 0
                and self._admin_user_counts(user_id)["registered_action_count"] > 0
                and self._admin_user_counts(user_id)["action_run_count"] > 0
            ),
        )

    def list_admin_users(
        self,
        search: str | None = None,
        activated_only: bool = False,
        sort: str = "newest",
    ) -> list[AdminUserSummary]:
        search_text = (search or "").strip().lower()
        users: list[AdminUserSummary] = []
        for user_id, email in self._profiles.items():
            counts = self._admin_user_counts(user_id)
            activated = (
                counts["workspace_count"] > 0
                and counts["registered_action_count"] > 0
                and counts["action_run_count"] > 0
            )
            if activated_only and not activated:
                continue
            if search_text and not self._admin_user_matches_search(user_id, search_text):
                continue
            users.append(
                AdminUserSummary(
                    email=email,
                    signed_up_at=self._profile_created_at.get(
                        user_id, datetime.now(timezone.utc)
                    ),
                    plan=self._plans.get(user_id, "free"),
                    workspace_count=counts["workspace_count"],
                    registered_action_count=counts["registered_action_count"],
                    action_run_count=counts["action_run_count"],
                    last_action_run_at=counts["last_action_run_at"],
                    activated=activated,
                )
            )

        if sort == "last_activity":
            users.sort(
                key=lambda user: (
                    user.last_action_run_at is not None,
                    user.last_action_run_at or datetime.min.replace(tzinfo=timezone.utc),
                    user.signed_up_at,
                ),
                reverse=True,
            )
        else:
            users.sort(key=lambda user: user.signed_up_at, reverse=True)
        return users

    def list_admin_workspaces(
        self,
        month_start: datetime,
        next_month_start: datetime,
        search: str | None = None,
    ) -> list[AdminWorkspaceSummary]:
        search_text = (search or "").strip().lower()
        workspaces: list[AdminWorkspaceSummary] = []
        for workspace in self._workspaces.values():
            owner_id = self.get_workspace_owner_id(workspace.id)
            owner_email = self._profiles.get(owner_id) if owner_id is not None else None
            plan = self._plans.get(owner_id, "free") if owner_id is not None else "free"
            if search_text and not self._admin_workspace_matches_search(
                workspace.id,
                search_text,
                owner_email,
            ):
                continue

            runs = [
                run for run in self._action_runs.values() if run.workspace_id == workspace.id
            ]
            workspaces.append(
                AdminWorkspaceSummary(
                    workspace_id=workspace.id,
                    workspace_name=workspace.name,
                    client_name=workspace.client_name,
                    owner_email=owner_email,
                    plan=plan,
                    registered_action_count=len(
                        self.list_registered_actions(workspace.id)
                    ),
                    action_runs_this_month=sum(
                        1
                        for run in runs
                        if month_start <= run.created_at < next_month_start
                    ),
                    approval_emails_this_month=sum(
                        event.email_count
                        for event in self._approval_email_events
                        if (
                            event.workspace_id == workspace.id
                            and month_start <= event.created_at < next_month_start
                        )
                    ),
                    last_action_run_at=max(
                        (run.created_at for run in runs),
                        default=None,
                    ),
                    created_at=workspace.created_at,
                )
            )

        workspaces.sort(
            key=lambda workspace: (
                workspace.last_action_run_at is not None,
                workspace.last_action_run_at
                or datetime.min.replace(tzinfo=timezone.utc),
                workspace.created_at,
            ),
            reverse=True,
        )
        return workspaces

    def list_admin_recent_action_runs(
        self,
        limit: int = 50,
        search: str | None = None,
        governance_status: GovernanceStatus | None = None,
    ) -> list[AdminActionRunSummary]:
        search_text = (search or "").strip().lower()
        runs = list(self._action_runs.values())
        if governance_status is not None:
            runs = [
                run for run in runs if run.governance_status == governance_status
            ]
        runs.sort(key=lambda run: run.created_at, reverse=True)

        summaries: list[AdminActionRunSummary] = []
        for run in runs:
            workspace = self._workspaces.get(run.workspace_id)
            workspace_name = workspace.name if workspace is not None else "Workspace"
            owner_id = self.get_workspace_owner_id(run.workspace_id)
            owner_email = self._profiles.get(owner_id) if owner_id is not None else None
            actor = self._admin_actor_from_payload(run.payload)
            if search_text:
                haystack = " ".join(
                    [
                        workspace_name,
                        owner_email or "",
                        run.action_name,
                        actor or "",
                    ]
                ).lower()
                if search_text not in haystack:
                    continue
            summaries.append(
                AdminActionRunSummary(
                    action_run_id=run.id,
                    created_at=run.created_at,
                    workspace_id=run.workspace_id,
                    workspace_name=workspace_name,
                    owner_email=owner_email,
                    action_name=run.action_name,
                    actor=actor,
                    governance_status=run.governance_status,
                    governance_reason=run.governance_reason,
                    execution_status=run.execution_status,
                )
            )
            if len(summaries) >= limit:
                break
        return summaries

    def _to_workspace_api_key(self, record: _WorkspaceApiKeyRecord) -> WorkspaceApiKey:
        workspace = self._workspaces.get(record.workspace_id)
        workspace_name = workspace.name if workspace is not None else "Workspace"
        workspace_client_name = workspace.client_name if workspace is not None else None
        return WorkspaceApiKey(
            id=record.id,
            workspace_id=record.workspace_id,
            workspace_name=workspace_name,
            workspace_client_name=workspace_client_name,
            name=record.name,
            key_prefix=record.key_prefix,
            created_at=record.created_at,
            created_by=record.created_by,
            last_used_at=record.last_used_at,
            revoked_at=record.revoked_at,
        )

    def get_workspace_api_key_hash(self, api_key_id: UUID) -> str | None:
        record = self._api_keys_by_id.get(api_key_id)
        if record is None:
            return None
        return record.key_hash

    @property
    def action_run_count(self) -> int:
        return len(self._action_runs)

    @property
    def receipt_count(self) -> int:
        return len(self._receipts_by_run)

    @property
    def approval_email_count(self) -> int:
        return sum(event.email_count for event in self._approval_email_events)

    def _admin_workspace_ids_for_owner(self, user_id: UUID) -> set[UUID]:
        return {
            workspace_id
            for (workspace_id, member_user_id), role in self._workspace_memberships.items()
            if member_user_id == user_id and role == "owner"
        }

    def _admin_user_counts(self, user_id: UUID) -> dict[str, Any]:
        workspace_ids = self._admin_workspace_ids_for_owner(user_id)
        runs = [
            run
            for run in self._action_runs.values()
            if run.workspace_id in workspace_ids
        ]
        return {
            "workspace_count": len(workspace_ids),
            "registered_action_count": sum(
                1
                for (workspace_id, _action_name) in self._registered_actions
                if workspace_id in workspace_ids
            ),
            "action_run_count": len(runs),
            "last_action_run_at": max(
                (run.created_at for run in runs),
                default=None,
            ),
        }

    def _admin_user_matches_search(self, user_id: UUID, search_text: str) -> bool:
        email = (self._profiles.get(user_id) or "").lower()
        if search_text in email:
            return True
        return any(
            self._admin_workspace_matches_search(workspace_id, search_text, email)
            for workspace_id in self._admin_workspace_ids_for_owner(user_id)
        )

    def _admin_workspace_matches_search(
        self,
        workspace_id: UUID,
        search_text: str,
        owner_email: str | None,
    ) -> bool:
        workspace = self._workspaces.get(workspace_id)
        values = [
            workspace.name if workspace is not None else "",
            workspace.client_name if workspace is not None else "",
            owner_email or "",
        ]
        values.extend(
            action.action_name
            for action in self.list_registered_actions(workspace_id)
        )
        values.extend(
            action.title
            for action in self.list_registered_actions(workspace_id)
        )
        return search_text in " ".join(values).lower()

    def _admin_actor_from_payload(self, payload: dict[str, Any]) -> str | None:
        actor = payload.get("actor")
        if isinstance(actor, str) and actor:
            return actor
        source = payload.get("source")
        if isinstance(source, dict):
            source_actor = source.get("actor")
            if isinstance(source_actor, str) and source_actor:
                return source_actor
        return None
