from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol
from uuid import UUID, uuid4

from psycopg import errors
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

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


class IdempotencyPayloadMismatchError(RuntimeError):
    """Raised when a stored idempotency key has a different payload hash."""


@dataclass(frozen=True)
class DashboardRunMetrics:
    total_runs: int
    pending_approval: int
    approved: int
    rejected: int
    blocked: int
    allowed: int
    executed: int
    failed: int


@dataclass(frozen=True)
class AdminOverviewMetrics:
    total_users: int
    total_workspaces: int
    total_registered_actions: int
    total_action_runs: int
    pending_approvals: int
    approved_actions: int
    blocked_actions: int
    executed_actions: int
    failed_actions: int
    approval_emails_sent_this_month: int
    activated_users: int


@dataclass(frozen=True)
class AdminUserSummary:
    email: str | None
    signed_up_at: datetime
    plan: str
    workspace_count: int
    registered_action_count: int
    action_run_count: int
    last_action_run_at: datetime | None
    activated: bool


@dataclass(frozen=True)
class AdminWorkspaceSummary:
    workspace_id: UUID
    workspace_name: str
    client_name: str | None
    owner_email: str | None
    plan: str
    registered_action_count: int
    action_runs_this_month: int
    approval_emails_this_month: int
    last_action_run_at: datetime | None
    created_at: datetime


@dataclass(frozen=True)
class AdminActionRunSummary:
    action_run_id: UUID
    created_at: datetime
    workspace_id: UUID
    workspace_name: str
    owner_email: str | None
    action_name: str
    actor: str | None
    governance_status: GovernanceStatus
    governance_reason: str
    execution_status: ExecutionStatus


@dataclass(frozen=True)
class PaginatedActionRuns:
    items: list[ActionRun]
    total: int


@dataclass(frozen=True)
class DashboardPendingApprovalRecord:
    action_run: ActionRun
    decision_expires_at: datetime | None


@dataclass(frozen=True)
class RegisteredActionInsertResult:
    action: RegisteredAction | None
    conflict: bool = False
    limit_reached: bool = False


class GovernanceRepository(Protocol):
    def get_workspace_id_by_workspace_key_hash(self, workspace_key_hash: str) -> UUID | None: ...

    def get_workspace(self, workspace_id: UUID) -> Workspace | None: ...

    def update_workspace_approval_settings(
        self,
        workspace_id: UUID,
        approval_emails: list[str],
        approval_link_ttl_minutes: int,
    ) -> Workspace | None: ...

    def upsert_profile(self, user_id: UUID, email: str | None) -> None: ...

    def get_owner_plan(self, user_id: UUID) -> str: ...

    def get_workspace_owner_id(self, workspace_id: UUID) -> UUID | None: ...

    def list_workspaces_for_user(self, user_id: UUID) -> list[Workspace]: ...

    def count_active_workspaces_for_owner(self, user_id: UUID) -> int: ...

    def user_has_workspace_access(self, user_id: UUID, workspace_id: UUID) -> bool: ...

    def ensure_workspace_membership(
        self,
        workspace_id: UUID,
        user_id: UUID,
        role: str = "owner",
    ) -> bool: ...

    def create_workspace(
        self,
        name: str,
        client_name: str,
        workspace_key_hash: str,
        status: str = "active",
    ) -> Workspace: ...

    def create_workspace_for_owner(
        self,
        owner_user_id: UUID,
        name: str,
        client_name: str,
        workspace_key_hash: str,
        active_workspace_limit: int,
        status: str = "active",
    ) -> Workspace | None: ...

    def delete_workspace_for_owner(
        self,
        owner_user_id: UUID,
        workspace_id: UUID,
    ) -> Workspace | None: ...

    def verify_workspace_api_key(self, workspace_id: UUID, key_hash: str) -> bool: ...

    def list_workspace_api_keys_for_user(self, user_id: UUID) -> list[WorkspaceApiKey]: ...

    def create_workspace_api_key(
        self,
        workspace_id: UUID,
        key_hash: str,
        key_prefix: str,
        name: str,
        created_by: UUID,
    ) -> WorkspaceApiKey: ...

    def get_workspace_api_key(
        self,
        workspace_id: UUID,
        api_key_id: UUID,
    ) -> WorkspaceApiKey | None: ...

    def revoke_workspace_api_key(
        self,
        workspace_id: UUID,
        api_key_id: UUID,
    ) -> WorkspaceApiKey | None: ...

    def get_workspace_key_hash(self, workspace_id: UUID) -> str | None: ...

    def update_workspace_key_hash(
        self,
        workspace_id: UUID,
        workspace_key_hash: str,
    ) -> str | None: ...

    def get_registered_action(self, workspace_id: UUID, action_name: str) -> RegisteredAction | None: ...

    def list_registered_actions(self, workspace_id: UUID) -> list[RegisteredAction]: ...

    def count_active_registered_actions(self, workspace_id: UUID) -> int: ...

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
    ) -> RegisteredAction | None: ...

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
    ) -> RegisteredActionInsertResult: ...

    def count_action_runs_for_owner_in_month(
        self,
        owner_user_id: UUID,
        month_start: datetime,
        next_month_start: datetime,
    ) -> int: ...

    def count_approval_emails_for_owner_in_month(
        self,
        owner_user_id: UUID,
        month_start: datetime,
        next_month_start: datetime,
    ) -> int: ...

    def reserve_approval_email_quota(
        self,
        owner_user_id: UUID,
        workspace_id: UUID,
        action_run_id: UUID,
        email_count: int,
        month_start: datetime,
        next_month_start: datetime,
        monthly_limit: int,
    ) -> bool: ...

    def increment_rate_limit_counter(
        self,
        key_type: str,
        key_value_hash: str,
        endpoint: str,
        window_start: datetime,
        window_seconds: int,
    ) -> int: ...

    def get_action_run_by_idempotency(
        self,
        workspace_id: UUID,
        action_name: str,
        idempotency_key: str,
    ) -> ActionRun | None: ...

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
    ) -> ActionRun: ...

    def create_governance_receipt(
        self,
        workspace_id: UUID,
        action_run_id: UUID,
        outcome: GovernanceStatus,
        reason: str,
        policy_type: str,
        policy_snapshot: dict[str, Any],
    ) -> GovernanceReceipt: ...

    def get_governance_receipt(self, workspace_id: UUID, action_run_id: UUID) -> GovernanceReceipt | None: ...

    def get_action_run(self, workspace_id: UUID, action_run_id: UUID) -> ActionRun | None: ...

    def get_action_run_by_id(self, action_run_id: UUID) -> ActionRun | None: ...

    def list_action_runs(self, workspace_id: UUID, limit: int = 100) -> list[ActionRun]: ...

    def get_dashboard_run_metrics(self, workspace_id: UUID) -> DashboardRunMetrics: ...

    def list_action_runs_paginated(
        self,
        workspace_id: UUID,
        page: int,
        page_size: int,
        search: str | None = None,
        governance_status: GovernanceStatus | None = None,
        execution_status: ExecutionStatus | None = None,
    ) -> PaginatedActionRuns: ...

    def list_pending_approvals(
        self,
        workspace_id: UUID,
        limit: int = 25,
    ) -> list[DashboardPendingApprovalRecord]: ...

    def create_action_decision_tokens(
        self,
        workspace_id: UUID,
        action_run_id: UUID,
        approve_token_hash: str,
        reject_token_hash: str,
        block_token_hash: str,
        expires_at: datetime,
    ) -> bool: ...

    def apply_public_decision(
        self,
        token_hash: str,
        token_type: ApprovalTokenType,
        target_status: GovernanceStatus,
        governance_reason: str,
    ) -> PublicDecisionUpdateResult: ...

    def apply_dashboard_decision(
        self,
        workspace_id: UUID,
        action_run_id: UUID,
        target_status: GovernanceStatus,
        governance_reason: str,
    ) -> DashboardDecisionUpdateResult: ...

    def report_executed(
        self,
        workspace_id: UUID,
        action_run_id: UUID,
        execution_result: dict[str, Any],
    ) -> ExecutionReportUpdateResult: ...

    def report_failed(
        self,
        workspace_id: UUID,
        action_run_id: UUID,
        execution_error: str,
        execution_result: dict[str, Any],
    ) -> ExecutionReportUpdateResult: ...

    def get_admin_overview(
        self,
        month_start: datetime,
        next_month_start: datetime,
    ) -> AdminOverviewMetrics: ...

    def list_admin_users(
        self,
        search: str | None = None,
        activated_only: bool = False,
        sort: str = "newest",
    ) -> list[AdminUserSummary]: ...

    def list_admin_workspaces(
        self,
        month_start: datetime,
        next_month_start: datetime,
        search: str | None = None,
    ) -> list[AdminWorkspaceSummary]: ...

    def list_admin_recent_action_runs(
        self,
        limit: int = 50,
        search: str | None = None,
        governance_status: GovernanceStatus | None = None,
    ) -> list[AdminActionRunSummary]: ...


@dataclass
class ExecutionReportUpdateResult:
    action_run: ActionRun | None
    updated: bool


@dataclass
class DashboardDecisionUpdateResult:
    action_run: ActionRun | None
    updated: bool


class PublicDecisionOutcome(str, Enum):
    APPLIED = "applied"
    INVALID_TOKEN = "invalid_token"
    EXPIRED_TOKEN = "expired_token"
    USED_TOKEN = "used_token"


@dataclass
class PublicDecisionUpdateResult:
    action_run: ActionRun | None
    outcome: PublicDecisionOutcome


class PostgresGovernanceRepository:
    def __init__(self, database_url: str):
        self._database_url = database_url
        self._pool: ConnectionPool | None = None
        self._workspace_api_keys_columns: set[str] = set()

    def open(self) -> None:
        if self._pool is None:
            self._pool = ConnectionPool(
                conninfo=self._database_url,
                kwargs={"row_factory": dict_row},
                max_size=10,
                open=True,
            )
            self._workspace_api_keys_columns = self._load_workspace_api_keys_columns()

    def close(self) -> None:
        if self._pool is not None:
            self._pool.close()
            self._pool = None

    def _has_workspace_api_keys_column(self, column_name: str) -> bool:
        return column_name in self._workspace_api_keys_columns

    def verify_workspace_api_key(self, workspace_id: UUID, key_hash: str) -> bool:
        pool = self._require_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                if self._has_workspace_api_keys_column("last_used_at"):
                    cur.execute(
                        """
                        UPDATE workspace_api_keys
                        SET last_used_at = NOW()
                        WHERE workspace_id = %s
                          AND key_hash = %s
                          AND revoked_at IS NULL
                        RETURNING 1
                        """,
                        (workspace_id, key_hash),
                    )
                else:
                    cur.execute(
                        """
                        SELECT 1
                        FROM workspace_api_keys
                        WHERE workspace_id = %s
                          AND key_hash = %s
                          AND revoked_at IS NULL
                        LIMIT 1
                        """,
                        (workspace_id, key_hash),
                    )
                row = cur.fetchone()
        return row is not None

    def list_workspace_api_keys_for_user(self, user_id: UUID) -> list[WorkspaceApiKey]:
        name_expr = (
            "COALESCE(NULLIF(k.name, ''), COALESCE(NULLIF(k.label, ''), 'API key')) AS name"
            if self._has_workspace_api_keys_column("name")
            else "COALESCE(NULLIF(k.label, ''), 'API key') AS name"
        )
        key_prefix_expr = (
            "COALESCE(NULLIF(k.key_prefix, ''), 'daai_sk_') AS key_prefix"
            if self._has_workspace_api_keys_column("key_prefix")
            else "'daai_sk_'::text AS key_prefix"
        )
        created_by_expr = (
            "k.created_by"
            if self._has_workspace_api_keys_column("created_by")
            else "NULL::uuid AS created_by"
        )
        last_used_at_expr = (
            "k.last_used_at"
            if self._has_workspace_api_keys_column("last_used_at")
            else "NULL::timestamptz AS last_used_at"
        )

        pool = self._require_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT k.id,
                           k.workspace_id,
                           w.name AS workspace_name,
                           w.client_name AS workspace_client_name,
                           {name_expr},
                           {key_prefix_expr},
                           k.created_at,
                           {created_by_expr},
                           {last_used_at_expr},
                           k.revoked_at
                    FROM workspace_api_keys AS k
                    INNER JOIN workspaces AS w
                      ON w.id = k.workspace_id
                    INNER JOIN workspace_members AS m
                      ON m.workspace_id = k.workspace_id
                    WHERE m.user_id = %s
                    ORDER BY k.created_at DESC
                    """,
                    (user_id,),
                )
                rows = cur.fetchall()

        return [
            api_key
            for api_key in (_workspace_api_key_from_row(row) for row in rows)
            if api_key is not None
        ]

    def create_workspace_api_key(
        self,
        workspace_id: UUID,
        key_hash: str,
        key_prefix: str,
        name: str,
        created_by: UUID,
    ) -> WorkspaceApiKey:
        pool = self._require_pool()
        api_key_id = uuid4()
        now = datetime.now(timezone.utc)
        insert_columns = [
            "id",
            "workspace_id",
            "key_hash",
            "label",
            "created_at",
            "revoked_at",
        ]
        insert_values: list[Any] = [
            api_key_id,
            workspace_id,
            key_hash,
            name,
            now,
            None,
        ]
        if self._has_workspace_api_keys_column("name"):
            insert_columns.append("name")
            insert_values.append(name)
        if self._has_workspace_api_keys_column("key_prefix"):
            insert_columns.append("key_prefix")
            insert_values.append(key_prefix)
        if self._has_workspace_api_keys_column("created_by"):
            insert_columns.append("created_by")
            insert_values.append(created_by)
        if self._has_workspace_api_keys_column("last_used_at"):
            insert_columns.append("last_used_at")
            insert_values.append(None)

        placeholders = ", ".join(["%s"] * len(insert_columns))
        columns_sql = ", ".join(insert_columns)
        with pool.connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        INSERT INTO workspace_api_keys ({columns_sql})
                        VALUES ({placeholders})
                        """,
                        tuple(insert_values),
                    )

        created = self.get_workspace_api_key(workspace_id=workspace_id, api_key_id=api_key_id)
        if created is None:
            raise RuntimeError("created api key could not be loaded")
        return created

    def get_workspace_api_key(
        self,
        workspace_id: UUID,
        api_key_id: UUID,
    ) -> WorkspaceApiKey | None:
        name_expr = (
            "COALESCE(NULLIF(k.name, ''), COALESCE(NULLIF(k.label, ''), 'API key')) AS name"
            if self._has_workspace_api_keys_column("name")
            else "COALESCE(NULLIF(k.label, ''), 'API key') AS name"
        )
        key_prefix_expr = (
            "COALESCE(NULLIF(k.key_prefix, ''), 'daai_sk_') AS key_prefix"
            if self._has_workspace_api_keys_column("key_prefix")
            else "'daai_sk_'::text AS key_prefix"
        )
        created_by_expr = (
            "k.created_by"
            if self._has_workspace_api_keys_column("created_by")
            else "NULL::uuid AS created_by"
        )
        last_used_at_expr = (
            "k.last_used_at"
            if self._has_workspace_api_keys_column("last_used_at")
            else "NULL::timestamptz AS last_used_at"
        )

        pool = self._require_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT k.id,
                           k.workspace_id,
                           w.name AS workspace_name,
                           w.client_name AS workspace_client_name,
                           {name_expr},
                           {key_prefix_expr},
                           k.created_at,
                           {created_by_expr},
                           {last_used_at_expr},
                           k.revoked_at
                    FROM workspace_api_keys AS k
                    INNER JOIN workspaces AS w
                      ON w.id = k.workspace_id
                    WHERE k.workspace_id = %s
                      AND k.id = %s
                    LIMIT 1
                    """,
                    (workspace_id, api_key_id),
                )
                row = cur.fetchone()
        return _workspace_api_key_from_row(row)

    def revoke_workspace_api_key(
        self,
        workspace_id: UUID,
        api_key_id: UUID,
    ) -> WorkspaceApiKey | None:
        pool = self._require_pool()
        now = datetime.now(timezone.utc)
        with pool.connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE workspace_api_keys
                        SET revoked_at = COALESCE(revoked_at, %s)
                        WHERE workspace_id = %s
                          AND id = %s
                        RETURNING id
                        """,
                        (now, workspace_id, api_key_id),
                    )
                    row = cur.fetchone()
        if row is None:
            return None
        return self.get_workspace_api_key(workspace_id=workspace_id, api_key_id=api_key_id)

    def get_workspace_key_hash(self, workspace_id: UUID) -> str | None:
        pool = self._require_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT workspace_key_hash
                    FROM workspaces
                    WHERE id = %s
                    LIMIT 1
                    """,
                    (workspace_id,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return row["workspace_key_hash"]

    def update_workspace_key_hash(
        self,
        workspace_id: UUID,
        workspace_key_hash: str,
    ) -> str | None:
        pool = self._require_pool()
        with pool.connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE workspaces
                        SET workspace_key_hash = %s
                        WHERE id = %s
                        RETURNING workspace_key_hash
                        """,
                        (workspace_key_hash, workspace_id),
                    )
                    row = cur.fetchone()
        if row is None:
            return None
        return row["workspace_key_hash"]

    def upsert_profile(self, user_id: UUID, email: str | None) -> None:
        pool = self._require_pool()
        with pool.connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO profiles (id, email, created_at, updated_at)
                        VALUES (%s, %s, NOW(), NOW())
                        ON CONFLICT (id) DO UPDATE
                        SET email = COALESCE(EXCLUDED.email, profiles.email),
                            updated_at = NOW()
                        """,
                        (user_id, email),
                    )

    def get_owner_plan(self, user_id: UUID) -> str:
        pool = self._require_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COALESCE(plan, 'free') AS plan
                    FROM profiles
                    WHERE id = %s
                    LIMIT 1
                    """,
                    (user_id,),
                )
                row = cur.fetchone()
        if row is None:
            return "free"
        return row["plan"] or "free"

    def get_workspace_owner_id(self, workspace_id: UUID) -> UUID | None:
        pool = self._require_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT user_id
                    FROM workspace_members
                    WHERE workspace_id = %s
                      AND role = 'owner'
                    ORDER BY created_at ASC
                    LIMIT 1
                    """,
                    (workspace_id,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return row["user_id"]

    def list_workspaces_for_user(self, user_id: UUID) -> list[Workspace]:
        pool = self._require_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT w.id,
                           w.name,
                           w.client_name,
                           w.status,
                           w.approval_emails,
                           w.approval_link_ttl_minutes,
                           w.created_at
                    FROM workspaces AS w
                    INNER JOIN workspace_members AS m
                      ON m.workspace_id = w.id
                    WHERE m.user_id = %s
                    ORDER BY w.created_at DESC
                    """,
                    (user_id,),
                )
                rows = cur.fetchall()

        workspaces: list[Workspace] = []
        for row in rows:
            workspaces.append(
                Workspace(
                    id=row["id"],
                    name=row["name"],
                    created_at=row["created_at"],
                    client_name=row.get("client_name"),
                    status=row.get("status") or "active",
                    approval_emails=list(row.get("approval_emails") or []),
                    approval_link_ttl_minutes=int(
                        row.get("approval_link_ttl_minutes") or 15
                    ),
                )
            )
        return workspaces

    def count_active_workspaces_for_owner(self, user_id: UUID) -> int:
        pool = self._require_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM workspaces AS w
                    INNER JOIN workspace_members AS m
                      ON m.workspace_id = w.id
                    WHERE m.user_id = %s
                      AND m.role = 'owner'
                      AND COALESCE(w.status, 'active') = 'active'
                    """,
                    (user_id,),
                )
                row = cur.fetchone()
        return int(row["count"] if row is not None else 0)

    def user_has_workspace_access(self, user_id: UUID, workspace_id: UUID) -> bool:
        pool = self._require_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1
                    FROM workspace_members
                    WHERE workspace_id = %s
                      AND user_id = %s
                    LIMIT 1
                    """,
                    (workspace_id, user_id),
                )
                row = cur.fetchone()
        return row is not None

    def ensure_workspace_membership(
        self,
        workspace_id: UUID,
        user_id: UUID,
        role: str = "owner",
    ) -> bool:
        pool = self._require_pool()
        with pool.connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO workspace_members (
                            id,
                            workspace_id,
                            user_id,
                            role,
                            created_at
                        )
                        SELECT %s, w.id, %s, %s, NOW()
                        FROM workspaces AS w
                        WHERE w.id = %s
                        ON CONFLICT (workspace_id, user_id) DO NOTHING
                        RETURNING id
                        """,
                        (uuid4(), user_id, role, workspace_id),
                    )
                    row = cur.fetchone()
        return row is not None

    def create_workspace(
        self,
        name: str,
        client_name: str,
        workspace_key_hash: str,
        status: str = "active",
    ) -> Workspace:
        pool = self._require_pool()
        workspace_id = uuid4()
        now = datetime.now(timezone.utc)
        with pool.connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO workspaces (
                            id,
                            workspace_key_hash,
                            name,
                            client_name,
                            status,
                            created_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            workspace_id,
                            workspace_key_hash,
                            name,
                            client_name,
                            status,
                            now,
                        ),
                    )

        return Workspace(
            id=workspace_id,
            name=name,
            created_at=now,
            client_name=client_name,
            status=status,
            approval_emails=[],
            approval_link_ttl_minutes=15,
        )

    def create_workspace_for_owner(
        self,
        owner_user_id: UUID,
        name: str,
        client_name: str,
        workspace_key_hash: str,
        active_workspace_limit: int,
        status: str = "active",
    ) -> Workspace | None:
        pool = self._require_pool()
        workspace_id = uuid4()
        now = datetime.now(timezone.utc)

        with pool.connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id
                        FROM profiles
                        WHERE id = %s
                        FOR UPDATE
                        """,
                        (owner_user_id,),
                    )
                    cur.fetchone()

                    cur.execute(
                        """
                        SELECT COUNT(*) AS count
                        FROM workspaces AS w
                        INNER JOIN workspace_members AS m
                          ON m.workspace_id = w.id
                        WHERE m.user_id = %s
                          AND m.role = 'owner'
                          AND COALESCE(w.status, 'active') = 'active'
                        """,
                        (owner_user_id,),
                    )
                    count_row = cur.fetchone()
                    active_count = int(count_row["count"] if count_row else 0)
                    if active_count >= active_workspace_limit:
                        return None

                    cur.execute(
                        """
                        INSERT INTO workspaces (
                            id,
                            workspace_key_hash,
                            name,
                            client_name,
                            status,
                            created_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            workspace_id,
                            workspace_key_hash,
                            name,
                            client_name,
                            status,
                            now,
                        ),
                    )
                    cur.execute(
                        """
                        INSERT INTO workspace_members (
                            id,
                            workspace_id,
                            user_id,
                            role,
                            created_at
                        )
                        VALUES (%s, %s, %s, 'owner', %s)
                        ON CONFLICT (workspace_id, user_id) DO NOTHING
                        """,
                        (uuid4(), workspace_id, owner_user_id, now),
                    )

        return Workspace(
            id=workspace_id,
            name=name,
            created_at=now,
            client_name=client_name,
            status=status,
            approval_emails=[],
            approval_link_ttl_minutes=15,
        )

    def delete_workspace_for_owner(
        self,
        owner_user_id: UUID,
        workspace_id: UUID,
    ) -> Workspace | None:
        pool = self._require_pool()
        deleted_workspace: Workspace | None = None

        with pool.connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT w.id,
                               w.name,
                               w.client_name,
                               w.status,
                               w.approval_emails,
                               w.approval_link_ttl_minutes,
                               w.created_at
                        FROM workspaces AS w
                        INNER JOIN workspace_members AS m
                          ON m.workspace_id = w.id
                        WHERE w.id = %s
                          AND m.user_id = %s
                          AND m.role = 'owner'
                        LIMIT 1
                        FOR UPDATE OF w
                        """,
                        (workspace_id, owner_user_id),
                    )
                    row = cur.fetchone()
                    if row is None:
                        return None

                    deleted_workspace = Workspace(
                        id=row["id"],
                        name=row["name"],
                        created_at=row["created_at"],
                        client_name=row.get("client_name"),
                        status=row.get("status") or "active",
                        approval_emails=list(row.get("approval_emails") or []),
                        approval_link_ttl_minutes=int(
                            row.get("approval_link_ttl_minutes") or 15
                        ),
                    )

                    cur.execute(
                        """
                        DELETE FROM rate_limit_events
                        WHERE key_type = 'api_key'
                          AND endpoint = '/v1/sdk/intercept'
                          AND key_value_hash IN (
                              SELECT key_hash
                              FROM workspace_api_keys
                              WHERE workspace_id = %s
                          )
                        """,
                        (workspace_id,),
                    )
                    cur.execute(
                        """
                        DELETE FROM workspaces
                        WHERE id = %s
                        """,
                        (workspace_id,),
                    )

        return deleted_workspace

    def get_workspace_id_by_workspace_key_hash(self, workspace_key_hash: str) -> UUID | None:
        pool = self._require_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id
                    FROM workspaces
                    WHERE workspace_key_hash = %s
                    LIMIT 1
                    """,
                    (workspace_key_hash,),
                )
                row = cur.fetchone()

        if row is None:
            return None
        return row["id"]

    def get_workspace(self, workspace_id: UUID) -> Workspace | None:
        pool = self._require_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id,
                           name,
                           client_name,
                           status,
                           approval_emails,
                           approval_link_ttl_minutes,
                           created_at
                    FROM workspaces
                    WHERE id = %s
                    LIMIT 1
                    """,
                    (workspace_id,),
                )
                row = cur.fetchone()

        if row is None:
            return None

        return Workspace(
            id=row["id"],
            name=row["name"],
            created_at=row["created_at"],
            client_name=row.get("client_name"),
            status=row.get("status") or "active",
            approval_emails=list(row.get("approval_emails") or []),
            approval_link_ttl_minutes=int(row.get("approval_link_ttl_minutes") or 15),
        )

    def update_workspace_approval_settings(
        self,
        workspace_id: UUID,
        approval_emails: list[str],
        approval_link_ttl_minutes: int,
    ) -> Workspace | None:
        pool = self._require_pool()
        with pool.connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE workspaces
                        SET approval_emails = %s,
                            approval_link_ttl_minutes = %s
                        WHERE id = %s
                        RETURNING id
                        """,
                        (
                            approval_emails,
                            approval_link_ttl_minutes,
                            workspace_id,
                        ),
                    )
                    row = cur.fetchone()

        if row is None:
            return None
        return self.get_workspace(workspace_id=workspace_id)

    def get_registered_action(self, workspace_id: UUID, action_name: str) -> RegisteredAction | None:
        pool = self._require_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id,
                           workspace_id,
                           action_name,
                           title,
                           description,
                           risk_level,
                           is_active,
                           policy_type,
                           policy_config
                    FROM registered_actions
                    WHERE workspace_id = %s AND action_name = %s
                    LIMIT 1
                    """,
                    (workspace_id, action_name),
                )
                row = cur.fetchone()

        return _registered_action_from_row(row)

    def list_registered_actions(self, workspace_id: UUID) -> list[RegisteredAction]:
        pool = self._require_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id,
                           workspace_id,
                           action_name,
                           title,
                           description,
                           risk_level,
                           is_active,
                           policy_type,
                           policy_config
                    FROM registered_actions
                    WHERE workspace_id = %s
                    ORDER BY action_name ASC
                    """,
                    (workspace_id,),
                )
                rows = cur.fetchall()

        return [
            action
            for action in (_registered_action_from_row(row) for row in rows)
            if action is not None
        ]

    def count_active_registered_actions(self, workspace_id: UUID) -> int:
        pool = self._require_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM registered_actions
                    WHERE workspace_id = %s
                      AND is_active = TRUE
                    """,
                    (workspace_id,),
                )
                row = cur.fetchone()
        return int(row["count"] if row is not None else 0)

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
        pool = self._require_pool()
        try:
            with pool.connection() as conn:
                with conn.transaction():
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO registered_actions (
                                id,
                                workspace_id,
                                action_name,
                                title,
                                description,
                                risk_level,
                                is_active,
                                policy_type,
                                policy_config
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            RETURNING id,
                                      workspace_id,
                                      action_name,
                                      title,
                                      description,
                                      risk_level,
                                      is_active,
                                      policy_type,
                                      policy_config
                            """,
                            (
                                uuid4(),
                                workspace_id,
                                action_name,
                                title,
                                description,
                                risk_level,
                                is_active,
                                policy_type,
                                Jsonb(policy_config),
                            ),
                        )
                        row = cur.fetchone()
        except errors.UniqueViolation:
            return None

        return _registered_action_from_row(row)

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
        pool = self._require_pool()
        row: dict[str, Any] | None = None
        try:
            with pool.connection() as conn:
                with conn.transaction():
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            SELECT id
                            FROM workspaces
                            WHERE id = %s
                            FOR UPDATE
                            """,
                            (workspace_id,),
                        )
                        if cur.fetchone() is None:
                            return RegisteredActionInsertResult(action=None)

                        if is_active:
                            cur.execute(
                                """
                                SELECT COUNT(*) AS count
                                FROM registered_actions
                                WHERE workspace_id = %s
                                  AND is_active = TRUE
                                """,
                                (workspace_id,),
                            )
                            count_row = cur.fetchone()
                            active_count = int(count_row["count"] if count_row else 0)
                            if active_count >= active_action_limit:
                                return RegisteredActionInsertResult(
                                    action=None,
                                    limit_reached=True,
                                )

                        cur.execute(
                            """
                            INSERT INTO registered_actions (
                                id,
                                workspace_id,
                                action_name,
                                title,
                                description,
                                risk_level,
                                is_active,
                                policy_type,
                                policy_config
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            RETURNING id,
                                      workspace_id,
                                      action_name,
                                      title,
                                      description,
                                      risk_level,
                                      is_active,
                                      policy_type,
                                      policy_config
                            """,
                            (
                                uuid4(),
                                workspace_id,
                                action_name,
                                title,
                                description,
                                risk_level,
                                is_active,
                                policy_type,
                                Jsonb(policy_config),
                            ),
                        )
                        row = cur.fetchone()
        except errors.UniqueViolation:
            return RegisteredActionInsertResult(action=None, conflict=True)

        return RegisteredActionInsertResult(action=_registered_action_from_row(row))

    def get_action_run_by_idempotency(
        self,
        workspace_id: UUID,
        action_name: str,
        idempotency_key: str,
    ) -> ActionRun | None:
        pool = self._require_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id,
                           workspace_id,
                           action_name,
                           governance_status,
                           execution_status,
                           governance_reason,
                           payload,
                           policy_snapshot,
                           idempotency_key,
                           idempotency_payload_hash,
                           execution_result,
                           execution_error,
                           execution_reported_at,
                           executed_at,
                           failed_at,
                           created_at,
                           decided_at
                    FROM action_runs
                    WHERE workspace_id = %s
                      AND action_name = %s
                      AND idempotency_key = %s
                    LIMIT 1
                    """,
                    (workspace_id, action_name, idempotency_key),
                )
                row = cur.fetchone()

        return _action_run_from_row(row)

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
        pool = self._require_pool()
        action_run_id = uuid4()
        now = datetime.now(timezone.utc)

        with pool.connection() as conn:
            try:
                with conn.transaction():
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO action_runs (
                                id,
                                workspace_id,
                                registered_action_id,
                                action_name,
                                idempotency_key,
                                idempotency_payload_hash,
                                governance_status,
                                execution_status,
                                governance_reason,
                                payload,
                                policy_snapshot,
                                execution_result,
                                execution_error,
                                execution_reported_at,
                                executed_at,
                                failed_at,
                                created_at,
                                requested_at,
                                decided_at,
                                updated_at
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                action_run_id,
                                workspace_id,
                                registered_action_id,
                                action_name,
                                idempotency_key,
                                idempotency_payload_hash,
                                governance_status.value,
                                execution_status.value,
                                governance_reason,
                                Jsonb(payload),
                                Jsonb(policy_snapshot),
                                Jsonb({}),
                                None,
                                None,
                                None,
                                None,
                                now,
                                now,
                                now,
                                now,
                            ),
                        )
            except errors.UniqueViolation:
                if idempotency_key is None:
                    raise
                existing = self.get_action_run_by_idempotency(
                    workspace_id=workspace_id,
                    action_name=action_name,
                    idempotency_key=idempotency_key,
                )
                if existing is None:
                    raise
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

        return ActionRun(
            id=action_run_id,
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

    def count_action_runs_for_owner_in_month(
        self,
        owner_user_id: UUID,
        month_start: datetime,
        next_month_start: datetime,
    ) -> int:
        pool = self._require_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM action_runs AS r
                    INNER JOIN workspace_members AS m
                      ON m.workspace_id = r.workspace_id
                    INNER JOIN workspaces AS w
                      ON w.id = r.workspace_id
                    WHERE m.user_id = %s
                      AND m.role = 'owner'
                      AND COALESCE(w.status, 'active') = 'active'
                      AND r.created_at >= %s
                      AND r.created_at < %s
                    """,
                    (owner_user_id, month_start, next_month_start),
                )
                row = cur.fetchone()
        return int(row["count"] if row is not None else 0)

    def count_approval_emails_for_owner_in_month(
        self,
        owner_user_id: UUID,
        month_start: datetime,
        next_month_start: datetime,
    ) -> int:
        pool = self._require_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(email_count), 0) AS count
                    FROM approval_email_events
                    WHERE owner_user_id = %s
                      AND created_at >= %s
                      AND created_at < %s
                    """,
                    (owner_user_id, month_start, next_month_start),
                )
                row = cur.fetchone()
        return int(row["count"] if row is not None else 0)

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

        pool = self._require_pool()
        with pool.connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id
                        FROM profiles
                        WHERE id = %s
                        FOR UPDATE
                        """,
                        (owner_user_id,),
                    )
                    cur.fetchone()

                    cur.execute(
                        """
                        SELECT COALESCE(SUM(email_count), 0) AS count
                        FROM approval_email_events
                        WHERE owner_user_id = %s
                          AND created_at >= %s
                          AND created_at < %s
                        """,
                        (owner_user_id, month_start, next_month_start),
                    )
                    row = cur.fetchone()
                    existing_count = int(row["count"] if row is not None else 0)
                    if existing_count + email_count > monthly_limit:
                        return False

                    cur.execute(
                        """
                        INSERT INTO approval_email_events (
                            id,
                            owner_user_id,
                            workspace_id,
                            action_run_id,
                            email_count,
                            created_at
                        )
                        VALUES (%s, %s, %s, %s, %s, NOW())
                        """,
                        (
                            uuid4(),
                            owner_user_id,
                            workspace_id,
                            action_run_id,
                            email_count,
                        ),
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
        pool = self._require_pool()
        with pool.connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO rate_limit_events (
                            id,
                            key_type,
                            key_value_hash,
                            endpoint,
                            window_start,
                            window_seconds,
                            request_count,
                            created_at,
                            updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, 1, NOW(), NOW())
                        ON CONFLICT (
                            key_type,
                            key_value_hash,
                            endpoint,
                            window_start,
                            window_seconds
                        )
                        DO UPDATE
                        SET request_count = rate_limit_events.request_count + 1,
                            updated_at = NOW()
                        RETURNING request_count
                        """,
                        (
                            uuid4(),
                            key_type,
                            key_value_hash,
                            endpoint,
                            window_start,
                            window_seconds,
                        ),
                    )
                    row = cur.fetchone()
        return int(row["request_count"] if row is not None else 1)

    def create_governance_receipt(
        self,
        workspace_id: UUID,
        action_run_id: UUID,
        outcome: GovernanceStatus,
        reason: str,
        policy_type: str,
        policy_snapshot: dict[str, Any],
    ) -> GovernanceReceipt:
        pool = self._require_pool()
        receipt_id = uuid4()
        now = datetime.now(timezone.utc)

        with pool.connection() as conn:
            try:
                with conn.transaction():
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO governance_receipts (
                                id,
                                workspace_id,
                                action_run_id,
                                outcome,
                                reason,
                                policy_type,
                                policy_snapshot,
                                created_at
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                receipt_id,
                                workspace_id,
                                action_run_id,
                                outcome.value,
                                reason,
                                policy_type,
                                Jsonb(policy_snapshot),
                                now,
                            ),
                        )
            except errors.UniqueViolation:
                existing = self.get_governance_receipt(
                    workspace_id=workspace_id,
                    action_run_id=action_run_id,
                )
                if existing is None:
                    raise
                return existing

        return GovernanceReceipt(
            id=receipt_id,
            workspace_id=workspace_id,
            action_run_id=action_run_id,
            outcome=outcome.value,
            reason=reason,
            policy_type=policy_type,
            policy_snapshot=policy_snapshot,
            created_at=now,
        )

    def get_governance_receipt(self, workspace_id: UUID, action_run_id: UUID) -> GovernanceReceipt | None:
        pool = self._require_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id,
                           workspace_id,
                           action_run_id,
                           outcome,
                           reason,
                           policy_type,
                           policy_snapshot,
                           created_at
                    FROM governance_receipts
                    WHERE workspace_id = %s AND action_run_id = %s
                    LIMIT 1
                    """,
                    (workspace_id, action_run_id),
                )
                row = cur.fetchone()

        if row is None:
            return None

        return GovernanceReceipt(
            id=row["id"],
            workspace_id=row["workspace_id"],
            action_run_id=row["action_run_id"],
            outcome=row["outcome"],
            reason=row["reason"],
            policy_type=row["policy_type"],
            policy_snapshot=row["policy_snapshot"] or {},
            created_at=row["created_at"],
        )

    def get_action_run(self, workspace_id: UUID, action_run_id: UUID) -> ActionRun | None:
        pool = self._require_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id,
                           workspace_id,
                           action_name,
                           governance_status,
                           execution_status,
                           governance_reason,
                           payload,
                           policy_snapshot,
                           idempotency_key,
                           execution_result,
                           execution_error,
                           execution_reported_at,
                           executed_at,
                           failed_at,
                           created_at,
                           decided_at
                    FROM action_runs
                    WHERE workspace_id = %s
                      AND id = %s
                    LIMIT 1
                    """,
                    (workspace_id, action_run_id),
                )
                row = cur.fetchone()

        return _action_run_from_row(row)

    def get_action_run_by_id(self, action_run_id: UUID) -> ActionRun | None:
        pool = self._require_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id,
                           workspace_id,
                           action_name,
                           governance_status,
                           execution_status,
                           governance_reason,
                           payload,
                           policy_snapshot,
                           idempotency_key,
                           execution_result,
                           execution_error,
                           execution_reported_at,
                           executed_at,
                           failed_at,
                           created_at,
                           decided_at
                    FROM action_runs
                    WHERE id = %s
                    LIMIT 1
                    """,
                    (action_run_id,),
                )
                row = cur.fetchone()

        return _action_run_from_row(row)

    def list_action_runs(self, workspace_id: UUID, limit: int = 100) -> list[ActionRun]:
        pool = self._require_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id,
                           workspace_id,
                           action_name,
                           governance_status,
                           execution_status,
                           governance_reason,
                           payload,
                           policy_snapshot,
                           idempotency_key,
                           execution_result,
                           execution_error,
                           execution_reported_at,
                           executed_at,
                           failed_at,
                           created_at,
                           decided_at
                    FROM action_runs
                    WHERE workspace_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (workspace_id, limit),
                )
                rows = cur.fetchall()

        return [run for run in (_action_run_from_row(row) for row in rows) if run is not None]

    def get_dashboard_run_metrics(self, workspace_id: UUID) -> DashboardRunMetrics:
        pool = self._require_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) AS total_runs,
                           COUNT(*) FILTER (
                               WHERE governance_status = 'pending_approval'
                           ) AS pending_approval,
                           COUNT(*) FILTER (WHERE governance_status = 'approved') AS approved,
                           COUNT(*) FILTER (WHERE governance_status = 'rejected') AS rejected,
                           COUNT(*) FILTER (WHERE governance_status = 'blocked') AS blocked,
                           COUNT(*) FILTER (WHERE governance_status = 'allowed') AS allowed,
                           COUNT(*) FILTER (WHERE execution_status = 'executed') AS executed,
                           COUNT(*) FILTER (WHERE execution_status = 'failed') AS failed
                    FROM action_runs
                    WHERE workspace_id = %s
                    """,
                    (workspace_id,),
                )
                row = cur.fetchone()

        if row is None:
            return DashboardRunMetrics(
                total_runs=0,
                pending_approval=0,
                approved=0,
                rejected=0,
                blocked=0,
                allowed=0,
                executed=0,
                failed=0,
            )

        return DashboardRunMetrics(
            total_runs=int(row["total_runs"] or 0),
            pending_approval=int(row["pending_approval"] or 0),
            approved=int(row["approved"] or 0),
            rejected=int(row["rejected"] or 0),
            blocked=int(row["blocked"] or 0),
            allowed=int(row["allowed"] or 0),
            executed=int(row["executed"] or 0),
            failed=int(row["failed"] or 0),
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
        offset = (page - 1) * page_size
        where_parts = ["workspace_id = %s"]
        where_params: list[Any] = [workspace_id]

        if governance_status is not None:
            where_parts.append("governance_status = %s")
            where_params.append(governance_status.value)

        if execution_status is not None:
            where_parts.append("execution_status = %s")
            where_params.append(execution_status.value)

        if search:
            search_pattern = f"%{search}%"
            where_parts.append(
                "(action_name ILIKE %s OR governance_reason ILIKE %s OR payload::text ILIKE %s)"
            )
            where_params.extend([search_pattern, search_pattern, search_pattern])

        where_sql = " AND ".join(where_parts)

        pool = self._require_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT COUNT(*) AS total
                    FROM action_runs
                    WHERE {where_sql}
                    """,
                    tuple(where_params),
                )
                count_row = cur.fetchone()
                total = int((count_row or {}).get("total", 0))

                cur.execute(
                    f"""
                    SELECT id,
                           workspace_id,
                           action_name,
                           governance_status,
                           execution_status,
                           governance_reason,
                           payload,
                           policy_snapshot,
                           idempotency_key,
                           execution_result,
                           execution_error,
                           execution_reported_at,
                           executed_at,
                           failed_at,
                           created_at,
                           decided_at
                    FROM action_runs
                    WHERE {where_sql}
                    ORDER BY created_at DESC
                    LIMIT %s
                    OFFSET %s
                    """,
                    tuple([*where_params, page_size, offset]),
                )
                rows = cur.fetchall()

        runs = [run for run in (_action_run_from_row(row) for row in rows) if run is not None]
        return PaginatedActionRuns(items=runs, total=total)

    def get_admin_overview(
        self,
        month_start: datetime,
        next_month_start: datetime,
    ) -> AdminOverviewMetrics:
        pool = self._require_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH user_rollup AS (
                        SELECT p.id,
                               COUNT(DISTINCT w.id) AS workspace_count,
                               COUNT(DISTINCT ra.id) AS registered_action_count,
                               COUNT(DISTINCT ar.id) AS action_run_count
                        FROM profiles AS p
                        LEFT JOIN workspace_members AS m
                          ON m.user_id = p.id
                         AND m.role = 'owner'
                        LEFT JOIN workspaces AS w
                          ON w.id = m.workspace_id
                        LEFT JOIN registered_actions AS ra
                          ON ra.workspace_id = w.id
                        LEFT JOIN action_runs AS ar
                          ON ar.workspace_id = w.id
                        GROUP BY p.id
                    )
                    SELECT (SELECT COUNT(*) FROM profiles) AS total_users,
                           (SELECT COUNT(*) FROM workspaces) AS total_workspaces,
                           (SELECT COUNT(*) FROM registered_actions) AS total_registered_actions,
                           (SELECT COUNT(*) FROM action_runs) AS total_action_runs,
                           (SELECT COUNT(*)
                              FROM action_runs
                             WHERE governance_status = 'pending_approval') AS pending_approvals,
                           (SELECT COUNT(*)
                              FROM action_runs
                             WHERE governance_status = 'approved') AS approved_actions,
                           (SELECT COUNT(*)
                              FROM action_runs
                             WHERE governance_status = 'blocked') AS blocked_actions,
                           (SELECT COUNT(*)
                              FROM action_runs
                             WHERE execution_status = 'executed') AS executed_actions,
                           (SELECT COUNT(*)
                              FROM action_runs
                             WHERE execution_status = 'failed') AS failed_actions,
                           (SELECT COALESCE(SUM(email_count), 0)
                              FROM approval_email_events
                             WHERE created_at >= %s
                               AND created_at < %s) AS approval_emails_sent_this_month,
                           (SELECT COUNT(*)
                              FROM user_rollup
                             WHERE workspace_count > 0
                               AND registered_action_count > 0
                               AND action_run_count > 0) AS activated_users
                    """,
                    (month_start, next_month_start),
                )
                row = cur.fetchone()

        if row is None:
            return AdminOverviewMetrics(
                total_users=0,
                total_workspaces=0,
                total_registered_actions=0,
                total_action_runs=0,
                pending_approvals=0,
                approved_actions=0,
                blocked_actions=0,
                executed_actions=0,
                failed_actions=0,
                approval_emails_sent_this_month=0,
                activated_users=0,
            )

        return AdminOverviewMetrics(
            total_users=int(row["total_users"] or 0),
            total_workspaces=int(row["total_workspaces"] or 0),
            total_registered_actions=int(row["total_registered_actions"] or 0),
            total_action_runs=int(row["total_action_runs"] or 0),
            pending_approvals=int(row["pending_approvals"] or 0),
            approved_actions=int(row["approved_actions"] or 0),
            blocked_actions=int(row["blocked_actions"] or 0),
            executed_actions=int(row["executed_actions"] or 0),
            failed_actions=int(row["failed_actions"] or 0),
            approval_emails_sent_this_month=int(
                row["approval_emails_sent_this_month"] or 0
            ),
            activated_users=int(row["activated_users"] or 0),
        )

    def list_admin_users(
        self,
        search: str | None = None,
        activated_only: bool = False,
        sort: str = "newest",
    ) -> list[AdminUserSummary]:
        search_text = (search or "").strip()
        search_pattern = f"%{search_text}%"
        order_by = (
            "last_action_run_at DESC NULLS LAST, signed_up_at DESC"
            if sort == "last_activity"
            else "signed_up_at DESC"
        )

        pool = self._require_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    WITH user_rollup AS (
                        SELECT p.id,
                               p.email,
                               p.created_at AS signed_up_at,
                               COALESCE(p.plan, 'free') AS plan,
                               COUNT(DISTINCT w.id) AS workspace_count,
                               COUNT(DISTINCT ra.id) AS registered_action_count,
                               COUNT(DISTINCT ar.id) AS action_run_count,
                               MAX(ar.created_at) AS last_action_run_at
                        FROM profiles AS p
                        LEFT JOIN workspace_members AS m
                          ON m.user_id = p.id
                         AND m.role = 'owner'
                        LEFT JOIN workspaces AS w
                          ON w.id = m.workspace_id
                        LEFT JOIN registered_actions AS ra
                          ON ra.workspace_id = w.id
                        LEFT JOIN action_runs AS ar
                          ON ar.workspace_id = w.id
                        GROUP BY p.id, p.email, p.created_at, p.plan
                    ),
                    matched_users AS (
                        SELECT DISTINCT p.id
                        FROM profiles AS p
                        LEFT JOIN workspace_members AS m
                          ON m.user_id = p.id
                         AND m.role = 'owner'
                        LEFT JOIN workspaces AS w
                          ON w.id = m.workspace_id
                        LEFT JOIN registered_actions AS ra
                          ON ra.workspace_id = w.id
                        WHERE %s = ''
                           OR p.email ILIKE %s
                           OR w.name ILIKE %s
                           OR w.client_name ILIKE %s
                           OR ra.action_name ILIKE %s
                           OR ra.title ILIKE %s
                    )
                    SELECT email,
                           signed_up_at,
                           plan,
                           workspace_count,
                           registered_action_count,
                           action_run_count,
                           last_action_run_at,
                           (
                               workspace_count > 0
                               AND registered_action_count > 0
                               AND action_run_count > 0
                           ) AS activated
                    FROM user_rollup
                    WHERE id IN (SELECT id FROM matched_users)
                      AND (
                          %s = false
                          OR (
                              workspace_count > 0
                              AND registered_action_count > 0
                              AND action_run_count > 0
                          )
                      )
                    ORDER BY {order_by}
                    """,
                    (
                        search_text,
                        search_pattern,
                        search_pattern,
                        search_pattern,
                        search_pattern,
                        search_pattern,
                        activated_only,
                    ),
                )
                rows = cur.fetchall()

        return [
            AdminUserSummary(
                email=row.get("email"),
                signed_up_at=row["signed_up_at"],
                plan=row.get("plan") or "free",
                workspace_count=int(row["workspace_count"] or 0),
                registered_action_count=int(row["registered_action_count"] or 0),
                action_run_count=int(row["action_run_count"] or 0),
                last_action_run_at=row.get("last_action_run_at"),
                activated=bool(row["activated"]),
            )
            for row in rows
        ]

    def list_admin_workspaces(
        self,
        month_start: datetime,
        next_month_start: datetime,
        search: str | None = None,
    ) -> list[AdminWorkspaceSummary]:
        search_text = (search or "").strip()
        search_pattern = f"%{search_text}%"

        pool = self._require_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH owners AS (
                        SELECT DISTINCT ON (workspace_id)
                               workspace_id,
                               user_id
                        FROM workspace_members
                        WHERE role = 'owner'
                        ORDER BY workspace_id, created_at ASC
                    ),
                    action_counts AS (
                        SELECT workspace_id,
                               COUNT(*) AS registered_action_count
                        FROM registered_actions
                        GROUP BY workspace_id
                    ),
                    monthly_runs AS (
                        SELECT workspace_id,
                               COUNT(*) AS action_runs_this_month
                        FROM action_runs
                        WHERE created_at >= %s
                          AND created_at < %s
                        GROUP BY workspace_id
                    ),
                    monthly_emails AS (
                        SELECT workspace_id,
                               COALESCE(SUM(email_count), 0) AS approval_emails_this_month
                        FROM approval_email_events
                        WHERE created_at >= %s
                          AND created_at < %s
                        GROUP BY workspace_id
                    ),
                    latest_runs AS (
                        SELECT workspace_id,
                               MAX(created_at) AS last_action_run_at
                        FROM action_runs
                        GROUP BY workspace_id
                    )
                    SELECT w.id AS workspace_id,
                           w.name AS workspace_name,
                           w.client_name,
                           p.email AS owner_email,
                           COALESCE(p.plan, 'free') AS plan,
                           COALESCE(action_counts.registered_action_count, 0) AS registered_action_count,
                           COALESCE(monthly_runs.action_runs_this_month, 0) AS action_runs_this_month,
                           COALESCE(monthly_emails.approval_emails_this_month, 0) AS approval_emails_this_month,
                           latest_runs.last_action_run_at,
                           w.created_at
                    FROM workspaces AS w
                    LEFT JOIN owners
                      ON owners.workspace_id = w.id
                    LEFT JOIN profiles AS p
                      ON p.id = owners.user_id
                    LEFT JOIN action_counts
                      ON action_counts.workspace_id = w.id
                    LEFT JOIN monthly_runs
                      ON monthly_runs.workspace_id = w.id
                    LEFT JOIN monthly_emails
                      ON monthly_emails.workspace_id = w.id
                    LEFT JOIN latest_runs
                      ON latest_runs.workspace_id = w.id
                    WHERE %s = ''
                       OR w.name ILIKE %s
                       OR w.client_name ILIKE %s
                       OR p.email ILIKE %s
                       OR EXISTS (
                           SELECT 1
                           FROM registered_actions AS ra
                           WHERE ra.workspace_id = w.id
                             AND (
                                 ra.action_name ILIKE %s
                                 OR ra.title ILIKE %s
                             )
                       )
                    ORDER BY latest_runs.last_action_run_at DESC NULLS LAST,
                             w.created_at DESC
                    """,
                    (
                        month_start,
                        next_month_start,
                        month_start,
                        next_month_start,
                        search_text,
                        search_pattern,
                        search_pattern,
                        search_pattern,
                        search_pattern,
                        search_pattern,
                    ),
                )
                rows = cur.fetchall()

        return [
            AdminWorkspaceSummary(
                workspace_id=row["workspace_id"],
                workspace_name=row["workspace_name"],
                client_name=row.get("client_name"),
                owner_email=row.get("owner_email"),
                plan=row.get("plan") or "free",
                registered_action_count=int(row["registered_action_count"] or 0),
                action_runs_this_month=int(row["action_runs_this_month"] or 0),
                approval_emails_this_month=int(
                    row["approval_emails_this_month"] or 0
                ),
                last_action_run_at=row.get("last_action_run_at"),
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def list_admin_recent_action_runs(
        self,
        limit: int = 50,
        search: str | None = None,
        governance_status: GovernanceStatus | None = None,
    ) -> list[AdminActionRunSummary]:
        search_text = (search or "").strip()
        search_pattern = f"%{search_text}%"
        where_parts = [
            """
            (
                %s = ''
                OR w.name ILIKE %s
                OR p.email ILIKE %s
                OR ar.action_name ILIKE %s
                OR COALESCE(
                    ar.payload->>'actor',
                    ar.payload #>> '{source,actor}',
                    ''
                ) ILIKE %s
            )
            """
        ]
        params: list[Any] = [
            search_text,
            search_pattern,
            search_pattern,
            search_pattern,
            search_pattern,
        ]
        if governance_status is not None:
            where_parts.append("ar.governance_status = %s")
            params.append(governance_status.value)
        params.append(limit)
        where_sql = " AND ".join(where_parts)

        pool = self._require_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    WITH owners AS (
                        SELECT DISTINCT ON (workspace_id)
                               workspace_id,
                               user_id
                        FROM workspace_members
                        WHERE role = 'owner'
                        ORDER BY workspace_id, created_at ASC
                    )
                    SELECT ar.id AS action_run_id,
                           ar.created_at,
                           w.id AS workspace_id,
                           w.name AS workspace_name,
                           p.email AS owner_email,
                           ar.action_name,
                           NULLIF(
                               COALESCE(
                                   ar.payload->>'actor',
                                   ar.payload #>> '{{source,actor}}',
                                   ''
                               ),
                               ''
                           ) AS actor,
                           ar.governance_status,
                           ar.governance_reason,
                           ar.execution_status
                    FROM action_runs AS ar
                    INNER JOIN workspaces AS w
                      ON w.id = ar.workspace_id
                    LEFT JOIN owners
                      ON owners.workspace_id = w.id
                    LEFT JOIN profiles AS p
                      ON p.id = owners.user_id
                    WHERE {where_sql}
                    ORDER BY ar.created_at DESC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                rows = cur.fetchall()

        return [
            AdminActionRunSummary(
                action_run_id=row["action_run_id"],
                created_at=row["created_at"],
                workspace_id=row["workspace_id"],
                workspace_name=row["workspace_name"],
                owner_email=row.get("owner_email"),
                action_name=row["action_name"],
                actor=row.get("actor"),
                governance_status=GovernanceStatus(row["governance_status"]),
                governance_reason=row["governance_reason"],
                execution_status=ExecutionStatus(row["execution_status"]),
            )
            for row in rows
        ]

    def list_pending_approvals(
        self,
        workspace_id: UUID,
        limit: int = 25,
    ) -> list[DashboardPendingApprovalRecord]:
        pool = self._require_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT r.id,
                           r.workspace_id,
                           r.action_name,
                           r.governance_status,
                           r.execution_status,
                           r.governance_reason,
                           r.payload,
                           r.policy_snapshot,
                           r.idempotency_key,
                           r.execution_result,
                           r.execution_error,
                           r.execution_reported_at,
                           r.executed_at,
                           r.failed_at,
                           r.created_at,
                           r.decided_at,
                           token_summary.decision_expires_at
                    FROM action_runs AS r
                    LEFT JOIN (
                        SELECT workspace_id,
                               action_run_id,
                               MIN(expires_at) AS decision_expires_at
                        FROM action_run_decision_tokens
                        WHERE token_type IN ('approve', 'reject', 'block')
                          AND used_at IS NULL
                        GROUP BY workspace_id, action_run_id
                    ) AS token_summary
                      ON token_summary.workspace_id = r.workspace_id
                     AND token_summary.action_run_id = r.id
                    WHERE r.workspace_id = %s
                      AND r.governance_status = %s
                    ORDER BY r.created_at DESC
                    LIMIT %s
                    """,
                    (
                        workspace_id,
                        GovernanceStatus.PENDING_APPROVAL.value,
                        limit,
                    ),
                )
                rows = cur.fetchall()

        records: list[DashboardPendingApprovalRecord] = []
        for row in rows:
            run = _action_run_from_row(row)
            if run is None:
                continue
            records.append(
                DashboardPendingApprovalRecord(
                    action_run=run,
                    decision_expires_at=row.get("decision_expires_at"),
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
        pool = self._require_pool()
        now = datetime.now(timezone.utc)
        with pool.connection() as conn:
            try:
                with conn.transaction():
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO action_run_decision_tokens (
                                id,
                                workspace_id,
                                action_run_id,
                                token_type,
                                token_hash,
                                expires_at,
                                used_at,
                                created_at,
                                updated_at
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                uuid4(),
                                workspace_id,
                                action_run_id,
                                ApprovalTokenType.APPROVE.value,
                                approve_token_hash,
                                expires_at,
                                None,
                                now,
                                now,
                            ),
                        )
                        cur.execute(
                            """
                            INSERT INTO action_run_decision_tokens (
                                id,
                                workspace_id,
                                action_run_id,
                                token_type,
                                token_hash,
                                expires_at,
                                used_at,
                                created_at,
                                updated_at
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                uuid4(),
                                workspace_id,
                                action_run_id,
                                ApprovalTokenType.REJECT.value,
                                reject_token_hash,
                                expires_at,
                                None,
                                now,
                                now,
                            ),
                        )
                        cur.execute(
                            """
                            INSERT INTO action_run_decision_tokens (
                                id,
                                workspace_id,
                                action_run_id,
                                token_type,
                                token_hash,
                                expires_at,
                                used_at,
                                created_at,
                                updated_at
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                uuid4(),
                                workspace_id,
                                action_run_id,
                                ApprovalTokenType.BLOCK.value,
                                block_token_hash,
                                expires_at,
                                None,
                                now,
                                now,
                            ),
                        )
                return True
            except errors.UniqueViolation:
                return False

    def apply_public_decision(
        self,
        token_hash: str,
        token_type: ApprovalTokenType,
        target_status: GovernanceStatus,
        governance_reason: str,
    ) -> PublicDecisionUpdateResult:
        pool = self._require_pool()
        now = datetime.now(timezone.utc)
        next_execution_status = (
            ExecutionStatus.AWAITING_EXECUTION_REPORT
            if target_status == GovernanceStatus.APPROVED
            else ExecutionStatus.NOT_EXECUTED
        )

        with pool.connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT t.id AS token_id,
                               t.workspace_id,
                               t.action_run_id,
                               t.expires_at,
                               t.used_at,
                               r.id,
                               r.workspace_id,
                               r.action_name,
                               r.governance_status,
                               r.execution_status,
                               r.governance_reason,
                               r.payload,
                               r.policy_snapshot,
                               r.idempotency_key,
                               r.execution_result,
                               r.execution_error,
                               r.execution_reported_at,
                               r.executed_at,
                               r.failed_at,
                               r.created_at,
                               r.decided_at
                        FROM action_run_decision_tokens AS t
                        JOIN action_runs AS r
                          ON r.id = t.action_run_id
                         AND r.workspace_id = t.workspace_id
                        WHERE t.token_hash = %s
                          AND t.token_type = %s
                        LIMIT 1
                        FOR UPDATE OF t, r
                        """,
                        (token_hash, token_type.value),
                    )
                    token_row = cur.fetchone()

                    if token_row is None:
                        return PublicDecisionUpdateResult(
                            action_run=None,
                            outcome=PublicDecisionOutcome.INVALID_TOKEN,
                        )

                    token_id = token_row["token_id"]
                    workspace_id = token_row["workspace_id"]
                    action_run_id = token_row["action_run_id"]

                    if token_row["used_at"] is not None:
                        return PublicDecisionUpdateResult(
                            action_run=None,
                            outcome=PublicDecisionOutcome.USED_TOKEN,
                        )

                    if token_row["expires_at"] <= now:
                        cur.execute(
                            """
                            UPDATE action_run_decision_tokens
                            SET used_at = %s,
                                updated_at = %s
                            WHERE id = %s
                              AND used_at IS NULL
                            """,
                            (now, now, token_id),
                        )
                        return PublicDecisionUpdateResult(
                            action_run=None,
                            outcome=PublicDecisionOutcome.EXPIRED_TOKEN,
                        )

                    if (
                        token_row["governance_status"]
                        != GovernanceStatus.PENDING_APPROVAL.value
                    ):
                        cur.execute(
                            """
                            UPDATE action_run_decision_tokens
                            SET used_at = %s,
                                updated_at = %s
                            WHERE id = %s
                              AND used_at IS NULL
                            """,
                            (now, now, token_id),
                        )
                        return PublicDecisionUpdateResult(
                            action_run=None,
                            outcome=PublicDecisionOutcome.USED_TOKEN,
                        )

                    cur.execute(
                        """
                        UPDATE action_runs
                        SET governance_status = %s,
                            execution_status = %s,
                            governance_reason = %s,
                            decided_at = %s,
                            updated_at = %s
                        WHERE workspace_id = %s
                          AND id = %s
                          AND governance_status = %s
                        RETURNING id,
                                  workspace_id,
                                  action_name,
                                  governance_status,
                                  execution_status,
                                  governance_reason,
                                  payload,
                                  policy_snapshot,
                                  idempotency_key,
                                  execution_result,
                                  execution_error,
                                  execution_reported_at,
                                  executed_at,
                                  failed_at,
                                  created_at,
                                  decided_at
                        """,
                        (
                            target_status.value,
                            next_execution_status.value,
                            governance_reason,
                            now,
                            now,
                            workspace_id,
                            action_run_id,
                            GovernanceStatus.PENDING_APPROVAL.value,
                        ),
                    )
                    updated_row = cur.fetchone()
                    if updated_row is None:
                        cur.execute(
                            """
                            UPDATE action_run_decision_tokens
                            SET used_at = %s,
                                updated_at = %s
                            WHERE id = %s
                              AND used_at IS NULL
                            """,
                            (now, now, token_id),
                        )
                        return PublicDecisionUpdateResult(
                            action_run=None,
                            outcome=PublicDecisionOutcome.USED_TOKEN,
                        )

                    cur.execute(
                        """
                        UPDATE action_run_decision_tokens
                        SET used_at = %s,
                            updated_at = %s
                        WHERE workspace_id = %s
                          AND action_run_id = %s
                          AND used_at IS NULL
                        """,
                        (now, now, workspace_id, action_run_id),
                    )

        return PublicDecisionUpdateResult(
            action_run=_action_run_from_row(updated_row),
            outcome=PublicDecisionOutcome.APPLIED,
        )

    def apply_dashboard_decision(
        self,
        workspace_id: UUID,
        action_run_id: UUID,
        target_status: GovernanceStatus,
        governance_reason: str,
    ) -> DashboardDecisionUpdateResult:
        pool = self._require_pool()
        now = datetime.now(timezone.utc)
        next_execution_status = (
            ExecutionStatus.AWAITING_EXECUTION_REPORT
            if target_status == GovernanceStatus.APPROVED
            else ExecutionStatus.NOT_EXECUTED
        )

        with pool.connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE action_runs
                        SET governance_status = %s,
                            execution_status = %s,
                            governance_reason = %s,
                            decided_at = %s,
                            updated_at = %s
                        WHERE workspace_id = %s
                          AND id = %s
                          AND governance_status = %s
                        RETURNING id,
                                  workspace_id,
                                  action_name,
                                  governance_status,
                                  execution_status,
                                  governance_reason,
                                  payload,
                                  policy_snapshot,
                                  idempotency_key,
                                  execution_result,
                                  execution_error,
                                  execution_reported_at,
                                  executed_at,
                                  failed_at,
                                  created_at,
                                  decided_at
                        """,
                        (
                            target_status.value,
                            next_execution_status.value,
                            governance_reason,
                            now,
                            now,
                            workspace_id,
                            action_run_id,
                            GovernanceStatus.PENDING_APPROVAL.value,
                        ),
                    )
                    row = cur.fetchone()
                    if row is not None:
                        cur.execute(
                            """
                            UPDATE action_run_decision_tokens
                            SET used_at = %s,
                                updated_at = %s
                            WHERE workspace_id = %s
                              AND action_run_id = %s
                              AND used_at IS NULL
                            """,
                            (now, now, workspace_id, action_run_id),
                        )
                        return DashboardDecisionUpdateResult(
                            action_run=_action_run_from_row(row),
                            updated=True,
                        )

                    cur.execute(
                        """
                        SELECT id,
                               workspace_id,
                               action_name,
                               governance_status,
                               execution_status,
                               governance_reason,
                               payload,
                               policy_snapshot,
                               idempotency_key,
                               execution_result,
                               execution_error,
                               execution_reported_at,
                               executed_at,
                               failed_at,
                               created_at,
                               decided_at
                        FROM action_runs
                        WHERE workspace_id = %s
                          AND id = %s
                        LIMIT 1
                        """,
                        (workspace_id, action_run_id),
                    )
                    existing = cur.fetchone()

        return DashboardDecisionUpdateResult(
            action_run=_action_run_from_row(existing),
            updated=False,
        )

    def report_executed(
        self,
        workspace_id: UUID,
        action_run_id: UUID,
        execution_result: dict[str, Any],
    ) -> ExecutionReportUpdateResult:
        pool = self._require_pool()
        now = datetime.now(timezone.utc)
        with pool.connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE action_runs
                        SET execution_status = %s,
                            execution_result = %s,
                            execution_error = NULL,
                            execution_reported_at = %s,
                            executed_at = %s,
                            failed_at = NULL,
                            updated_at = %s
                        WHERE workspace_id = %s
                          AND id = %s
                          AND governance_status IN (%s, %s)
                          AND execution_status = %s
                        RETURNING id,
                                  workspace_id,
                                  action_name,
                                  governance_status,
                                  execution_status,
                                  governance_reason,
                                  payload,
                                  policy_snapshot,
                                  idempotency_key,
                                  execution_result,
                                  execution_error,
                                  execution_reported_at,
                                  executed_at,
                                  failed_at,
                                  created_at,
                                  decided_at
                        """,
                        (
                            ExecutionStatus.EXECUTED.value,
                            Jsonb(execution_result),
                            now,
                            now,
                            now,
                            workspace_id,
                            action_run_id,
                            GovernanceStatus.ALLOWED.value,
                            GovernanceStatus.APPROVED.value,
                            ExecutionStatus.AWAITING_EXECUTION_REPORT.value,
                        ),
                    )
                    row = cur.fetchone()
                    if row is not None:
                        return ExecutionReportUpdateResult(
                            action_run=_action_run_from_row(row),
                            updated=True,
                        )

                    cur.execute(
                        """
                        SELECT id,
                               workspace_id,
                               action_name,
                               governance_status,
                               execution_status,
                               governance_reason,
                               payload,
                               policy_snapshot,
                               idempotency_key,
                               execution_result,
                               execution_error,
                               execution_reported_at,
                               executed_at,
                               failed_at,
                               created_at,
                               decided_at
                        FROM action_runs
                        WHERE workspace_id = %s
                          AND id = %s
                        LIMIT 1
                        """,
                        (workspace_id, action_run_id),
                    )
                    existing_row = cur.fetchone()

        return ExecutionReportUpdateResult(
            action_run=_action_run_from_row(existing_row),
            updated=False,
        )

    def report_failed(
        self,
        workspace_id: UUID,
        action_run_id: UUID,
        execution_error: str,
        execution_result: dict[str, Any],
    ) -> ExecutionReportUpdateResult:
        pool = self._require_pool()
        now = datetime.now(timezone.utc)
        with pool.connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE action_runs
                        SET execution_status = %s,
                            execution_result = %s,
                            execution_error = %s,
                            execution_reported_at = %s,
                            executed_at = NULL,
                            failed_at = %s,
                            updated_at = %s
                        WHERE workspace_id = %s
                          AND id = %s
                          AND governance_status IN (%s, %s)
                          AND execution_status = %s
                        RETURNING id,
                                  workspace_id,
                                  action_name,
                                  governance_status,
                                  execution_status,
                                  governance_reason,
                                  payload,
                                  policy_snapshot,
                                  idempotency_key,
                                  execution_result,
                                  execution_error,
                                  execution_reported_at,
                                  executed_at,
                                  failed_at,
                                  created_at,
                                  decided_at
                        """,
                        (
                            ExecutionStatus.FAILED.value,
                            Jsonb(execution_result),
                            execution_error,
                            now,
                            now,
                            now,
                            workspace_id,
                            action_run_id,
                            GovernanceStatus.ALLOWED.value,
                            GovernanceStatus.APPROVED.value,
                            ExecutionStatus.AWAITING_EXECUTION_REPORT.value,
                        ),
                    )
                    row = cur.fetchone()
                    if row is not None:
                        return ExecutionReportUpdateResult(
                            action_run=_action_run_from_row(row),
                            updated=True,
                        )

                    cur.execute(
                        """
                        SELECT id,
                               workspace_id,
                               action_name,
                               governance_status,
                               execution_status,
                               governance_reason,
                               payload,
                               policy_snapshot,
                               idempotency_key,
                               execution_result,
                               execution_error,
                               execution_reported_at,
                               executed_at,
                               failed_at,
                               created_at,
                               decided_at
                        FROM action_runs
                        WHERE workspace_id = %s
                          AND id = %s
                        LIMIT 1
                        """,
                        (workspace_id, action_run_id),
                    )
                    existing_row = cur.fetchone()

        return ExecutionReportUpdateResult(
            action_run=_action_run_from_row(existing_row),
            updated=False,
        )

    def _require_pool(self) -> ConnectionPool:
        if self._pool is None:
            raise RuntimeError("repository is not open")
        return self._pool

    def _load_workspace_api_keys_columns(self) -> set[str]:
        pool = self._require_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.column_name
                    FROM information_schema.columns AS c
                    WHERE c.table_schema = current_schema()
                      AND c.table_name = 'workspace_api_keys'
                    """
                )
                rows = cur.fetchall()
        return {str(row["column_name"]) for row in rows}


def _action_run_from_row(row: dict[str, Any] | None) -> ActionRun | None:
    if row is None:
        return None

    return ActionRun(
        id=row["id"],
        workspace_id=row["workspace_id"],
        action_name=row["action_name"],
        governance_status=GovernanceStatus(row["governance_status"]),
        execution_status=ExecutionStatus(row["execution_status"]),
        governance_reason=row["governance_reason"],
        payload=row["payload"] or {},
        policy_snapshot=row["policy_snapshot"] or {},
        idempotency_key=row["idempotency_key"],
        idempotency_payload_hash=row.get("idempotency_payload_hash"),
        execution_result=row["execution_result"] or {},
        execution_error=row["execution_error"],
        execution_reported_at=row["execution_reported_at"],
        executed_at=row["executed_at"],
        failed_at=row["failed_at"],
        created_at=row["created_at"],
        decided_at=row["decided_at"],
    )


def _registered_action_from_row(row: dict[str, Any] | None) -> RegisteredAction | None:
    if row is None:
        return None

    return RegisteredAction(
        id=row["id"],
        workspace_id=row["workspace_id"],
        action_name=row["action_name"],
        policy_type=row["policy_type"],
        policy_config=row["policy_config"] or {},
        title=row.get("title") or "",
        description=row.get("description") or "",
        risk_level=row.get("risk_level") or "medium",
        is_active=bool(row.get("is_active", True)),
    )


def _workspace_api_key_from_row(row: dict[str, Any] | None) -> WorkspaceApiKey | None:
    if row is None:
        return None

    return WorkspaceApiKey(
        id=row["id"],
        workspace_id=row["workspace_id"],
        workspace_name=row["workspace_name"],
        workspace_client_name=row.get("workspace_client_name"),
        name=row["name"],
        key_prefix=row["key_prefix"],
        created_at=row["created_at"],
        created_by=row.get("created_by"),
        last_used_at=row.get("last_used_at"),
        revoked_at=row.get("revoked_at"),
    )
