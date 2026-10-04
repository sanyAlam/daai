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


@dataclass(frozen=True)
class GovernanceReceipt:
    id: UUID
    outcome: str
    reason: str
    policy_type: str
    policy_snapshot: dict[str, Any]
    created_at: datetime


@dataclass(frozen=True)
class InterceptResponse:
    action_run_id: UUID
    governance_status: GovernanceStatus
    execution_status: ExecutionStatus
    governance_reason: str
    executable: bool
    idempotent_replay: bool
    receipt: GovernanceReceipt | None


@dataclass(frozen=True)
class ActionRunStatusResponse:
    action_run_id: UUID
    action: str
    governance_status: GovernanceStatus
    execution_status: ExecutionStatus
    governance_reason: str
    executable: bool
    receipt: GovernanceReceipt | None
    created_at: datetime
    decided_at: datetime | None


@dataclass(frozen=True)
class ExecutionReportResponse:
    action_run_id: UUID
    execution_status: ExecutionStatus
    execution_error: str | None
    execution_reported_at: datetime | None
    idempotent_replay: bool
