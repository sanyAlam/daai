from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID


class GovernanceStatus(str, Enum):
    ALLOWED = "allowed"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    BLOCKED = "blocked"


class ExecutionStatus(str, Enum):
    NOT_EXECUTED = "not_executed"
    AWAITING_EXECUTION_REPORT = "awaiting_execution_report"
    EXECUTED = "executed"
    FAILED = "failed"


class PolicyType(str, Enum):
    LOG_ONLY = "log_only"
    ALWAYS_ALLOW = "always_allow"
    ALWAYS_REQUIRE_APPROVAL = "always_require_approval"
    REQUIRE_APPROVAL_ABOVE_AMOUNT = "require_approval_above_amount"
    ALWAYS_BLOCK = "always_block"
    REQUIRE_APPROVAL_WHEN_EXTERNAL_RECIPIENT = (
        "require_approval_when_external_recipient"
    )
    REQUIRE_APPROVAL_WHEN_NEW_RECIPIENT = "require_approval_when_new_recipient"
    REQUIRE_APPROVAL_WHEN_NOT_REVERSIBLE = "require_approval_when_not_reversible"
    REQUIRE_APPROVAL_WHEN_DESTRUCTIVE = "require_approval_when_destructive"


class ApprovalTokenType(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    BLOCK = "block"


@dataclass
class RegisteredAction:
    id: UUID
    workspace_id: UUID
    action_name: str
    policy_type: str
    policy_config: dict[str, Any]
    title: str = ""
    description: str = ""
    risk_level: str = "medium"
    is_active: bool = True


@dataclass
class ActionRun:
    id: UUID
    workspace_id: UUID
    action_name: str
    governance_status: GovernanceStatus
    execution_status: ExecutionStatus
    governance_reason: str
    payload: dict[str, Any]
    policy_snapshot: dict[str, Any]
    idempotency_key: str | None
    idempotency_payload_hash: str | None
    execution_result: dict[str, Any]
    execution_error: str | None
    execution_reported_at: datetime | None
    executed_at: datetime | None
    failed_at: datetime | None
    created_at: datetime
    decided_at: datetime | None


@dataclass
class GovernanceReceipt:
    id: UUID
    workspace_id: UUID
    action_run_id: UUID
    outcome: str
    reason: str
    policy_type: str
    policy_snapshot: dict[str, Any]
    created_at: datetime


@dataclass
class PolicyDecision:
    governance_status: GovernanceStatus
    governance_reason: str
    policy_snapshot: dict[str, Any]


@dataclass
class Workspace:
    id: UUID
    name: str
    created_at: datetime
    client_name: str | None = None
    status: str = "active"
    approval_emails: list[str] | None = None
    approval_link_ttl_minutes: int = 15


@dataclass
class WorkspaceApiKey:
    id: UUID
    workspace_id: UUID
    workspace_name: str
    workspace_client_name: str | None
    name: str
    key_prefix: str
    created_at: datetime
    created_by: UUID | None
    last_used_at: datetime | None
    revoked_at: datetime | None


@dataclass
class WorkspaceKeyInfo:
    workspace_id: UUID
    workspace_name: str
    workspace_client_name: str | None
    key_identifier: str
