from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class PlanLimits:
    max_client_workspaces_per_owner: int
    max_active_actions_per_workspace: int
    max_action_runs_per_month: int
    max_approval_emails_per_month: int
    max_intercept_requests_per_minute_per_api_key: int
    max_intercept_requests_per_day_per_api_key: int
    max_public_approval_token_attempts_per_minute_per_ip: int
    max_input_payload_size_bytes: int
    max_reasoning_size_chars: int
    max_source_ref_size_chars: int


FREE_PLAN_LIMITS = PlanLimits(
    max_client_workspaces_per_owner=2,
    max_active_actions_per_workspace=3,
    max_action_runs_per_month=1000,
    max_approval_emails_per_month=100,
    max_intercept_requests_per_minute_per_api_key=30,
    max_intercept_requests_per_day_per_api_key=500,
    max_public_approval_token_attempts_per_minute_per_ip=20,
    max_input_payload_size_bytes=16_384,
    max_reasoning_size_chars=2_000,
    max_source_ref_size_chars=500,
)

PLAN_LIMITS = {
    "free": FREE_PLAN_LIMITS,
}


def normalize_plan(plan: str | None) -> str:
    normalized = (plan or "free").strip().lower()
    return normalized if normalized in PLAN_LIMITS else "free"


def limits_for_plan(plan: str | None) -> PlanLimits:
    return PLAN_LIMITS[normalize_plan(plan)]


def current_month_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    month_start = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if month_start.month == 12:
        next_month = month_start.replace(
            year=month_start.year + 1,
            month=1,
        )
    else:
        next_month = month_start.replace(month=month_start.month + 1)
    return month_start, next_month


def minute_window_start(now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.replace(second=0, microsecond=0)


def day_window_start(now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.replace(hour=0, minute=0, second=0, microsecond=0)
