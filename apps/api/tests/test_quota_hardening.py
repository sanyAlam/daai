from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
from fastapi.testclient import TestClient

from app.config import Settings
from app.domain import ExecutionStatus, GovernanceStatus
from app.hashing import hash_api_key, hash_workspace_key
from app.main import create_app
from app.quotas import current_month_window, day_window_start
from fakes import InMemoryGovernanceRepository

API_KEY = "test-api-key"
WORKSPACE_KEY = "wsk_test_workspace"
PEPPER = "test-pepper"
SUPABASE_JWT_SECRET = "test-supabase-jwt-secret"
DASHBOARD_USER_ID = UUID("aaaaaaaa-1111-1111-1111-111111111111")
DASHBOARD_EMAIL = "dashboard-owner@example.com"


@dataclass
class PendingApprovalLinkCapture:
    approve_url: str
    reject_url: str
    block_url: str


class CaptureApprovalLinkNotifier:
    def __init__(self) -> None:
        self.sent_links: list[PendingApprovalLinkCapture] = []

    def notify_pending_approval(self, links: object) -> None:
        self.sent_links.append(
            PendingApprovalLinkCapture(
                approve_url=getattr(links, "approve_url"),
                reject_url=getattr(links, "reject_url"),
                block_url=getattr(links, "block_url"),
            )
        )


def _auth_headers(
    api_key: str = API_KEY,
    workspace_key: str = WORKSPACE_KEY,
) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "X-DAAI-Workspace-Key": workspace_key,
    }


def _dashboard_auth_headers(
    *,
    user_id: UUID = DASHBOARD_USER_ID,
    email: str = DASHBOARD_EMAIL,
) -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": str(user_id),
            "aud": "authenticated",
            "email": email,
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        },
        SUPABASE_JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _build_client(
    *,
    seed_workspace: bool = True,
    workspace_id: UUID | None = None,
) -> tuple[TestClient, InMemoryGovernanceRepository]:
    repository = InMemoryGovernanceRepository()
    notifier = CaptureApprovalLinkNotifier()
    repository.upsert_profile(DASHBOARD_USER_ID, DASHBOARD_EMAIL)

    if seed_workspace:
        resolved_workspace_id = workspace_id or uuid4()
        repository.add_workspace_key_hash(
            workspace_id=resolved_workspace_id,
            workspace_key_hash=hash_workspace_key(WORKSPACE_KEY, PEPPER),
        )
        repository.add_api_key_hash(
            workspace_id=resolved_workspace_id,
            key_hash=hash_api_key(API_KEY, PEPPER),
        )
        repository.ensure_workspace_membership(
            workspace_id=resolved_workspace_id,
            user_id=DASHBOARD_USER_ID,
            role="owner",
        )

    app = create_app(
        repository=repository,
        settings=Settings(
            database_url=None,
            supabase_jwt_secret=SUPABASE_JWT_SECRET,
            api_key_pepper=PEPPER,
            workspace_key_pepper=PEPPER,
            approval_token_pepper=PEPPER,
            public_base_url="http://testserver",
            dashboard_base_url="http://dashboard.test",
            dev_auto_link_seeded_workspace=False,
        ),
        approval_link_notifier=notifier,
    )
    repository.approval_notifier = notifier
    return TestClient(app), repository


def _create_workspace(client: TestClient, name: str) -> object:
    return client.post(
        "/v1/dashboard/workspaces",
        headers=_dashboard_auth_headers(),
        json={"workspace_name": name, "client_name": name},
    )


def _register_action(client: TestClient, workspace_id: UUID, action_name: str) -> object:
    return client.post(
        f"/v1/dashboard/workspaces/{workspace_id}/actions",
        headers=_dashboard_auth_headers(),
        json={
            "action_name": action_name,
            "title": action_name.replace("_", " ").title(),
            "description": "",
            "risk_level": "medium",
            "policy_type": "always_allow",
        },
    )


def test_free_user_can_create_two_workspaces_but_not_third() -> None:
    client, _ = _build_client(seed_workspace=False)

    first = _create_workspace(client, "Workspace One")
    second = _create_workspace(client, "Workspace Two")
    third = _create_workspace(client, "Workspace Three")

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 403
    assert third.json() == {
        "error": "free_plan_workspace_limit_reached",
        "message": "Free beta allows up to 2 active client workspaces.",
        "limit": 2,
    }


def test_free_workspace_can_create_three_active_actions_but_not_fourth() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id=workspace_id)

    assert _register_action(client, workspace_id, "action_one").status_code == 200
    assert _register_action(client, workspace_id, "action_two").status_code == 200
    assert _register_action(client, workspace_id, "action_three").status_code == 200

    rejected = _register_action(client, workspace_id, "action_four")

    assert rejected.status_code == 403
    assert rejected.json()["error"] == "free_plan_action_limit_reached"
    assert rejected.json()["limit"] == 3

    repository.get_registered_action(workspace_id, "action_three").is_active = False
    freed_slot = _register_action(client, workspace_id, "action_four")
    assert freed_slot.status_code == 200


def test_action_run_quota_is_owner_scoped_across_workspaces() -> None:
    workspace_id = uuid4()
    other_workspace_id = uuid4()
    client, repository = _build_client(workspace_id=workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="mark_invoice_paid",
        policy_type="always_allow",
    )
    repository.add_workspace_key_hash(
        workspace_id=other_workspace_id,
        workspace_key_hash=hash_workspace_key("other-workspace-key", PEPPER),
    )
    repository.ensure_workspace_membership(
        workspace_id=other_workspace_id,
        user_id=DASHBOARD_USER_ID,
        role="owner",
    )

    for index in range(1000):
        repository.create_action_run(
            workspace_id=other_workspace_id,
            action_name=f"seed_{index}",
            registered_action_id=None,
            governance_status=GovernanceStatus.ALLOWED,
            execution_status=ExecutionStatus.AWAITING_EXECUTION_REPORT,
            governance_reason="seed",
            payload={},
            policy_snapshot={"policy_type": "seed"},
            idempotency_key=None,
            idempotency_payload_hash=None,
        )

    response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={"action": "mark_invoice_paid", "payload": {"invoice_id": "INV-1"}},
    )

    assert response.status_code == 403
    assert response.json()["error"] == "free_plan_monthly_action_run_limit_reached"
    assert response.json()["limit"] == 1000


def test_action_run_quota_allows_request_below_monthly_limit() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id=workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="mark_invoice_paid",
        policy_type="always_allow",
    )

    for index in range(999):
        repository.create_action_run(
            workspace_id=workspace_id,
            action_name=f"seed_{index}",
            registered_action_id=None,
            governance_status=GovernanceStatus.ALLOWED,
            execution_status=ExecutionStatus.AWAITING_EXECUTION_REPORT,
            governance_reason="seed",
            payload={},
            policy_snapshot={"policy_type": "seed"},
            idempotency_key=None,
            idempotency_payload_hash=None,
        )

    response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={"action": "mark_invoice_paid", "payload": {"invoice_id": "INV-1"}},
    )

    assert response.status_code == 200
    assert response.json()["governance_status"] == "allowed"


def test_approval_email_quota_blocks_pending_approval_safely() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id=workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="pay_vendor",
        policy_type="always_require_approval",
    )
    repository.update_workspace_approval_settings(
        workspace_id=workspace_id,
        approval_emails=["approver@example.com"],
        approval_link_ttl_minutes=15,
    )
    month_start, next_month_start = current_month_window()
    assert repository.reserve_approval_email_quota(
        owner_user_id=DASHBOARD_USER_ID,
        workspace_id=workspace_id,
        action_run_id=uuid4(),
        email_count=100,
        month_start=month_start,
        next_month_start=next_month_start,
        monthly_limit=100,
    )

    response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={"action": "pay_vendor", "payload": {"amount": 500}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["governance_status"] == "blocked"
    assert payload["receipt"]["outcome"] == "blocked"
    assert "approval email limit" in payload["governance_reason"]
    assert repository.approval_notifier.sent_links == []


def test_approval_email_quota_sends_below_limit() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id=workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="pay_vendor",
        policy_type="always_require_approval",
    )
    repository.update_workspace_approval_settings(
        workspace_id=workspace_id,
        approval_emails=["approver@example.com"],
        approval_link_ttl_minutes=15,
    )

    response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={"action": "pay_vendor", "payload": {"amount": 500}},
    )

    assert response.status_code == 200
    assert response.json()["governance_status"] == "pending_approval"
    assert len(repository.approval_notifier.sent_links) == 1
    assert repository.approval_email_count == 1


def test_intercept_rejects_after_per_minute_api_key_limit() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id=workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="mark_invoice_paid",
        policy_type="always_allow",
    )

    last_response = None
    for index in range(31):
        last_response = client.post(
            "/v1/sdk/intercept",
            headers=_auth_headers(),
            json={
                "action": "mark_invoice_paid",
                "payload": {"invoice_id": f"INV-{index}"},
            },
        )

    assert last_response is not None
    assert last_response.status_code == 429
    assert last_response.json()["error"] == "intercept_rate_limit_exceeded"


def test_intercept_rejects_after_daily_api_key_limit() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id=workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="mark_invoice_paid",
        policy_type="always_allow",
    )
    api_key_hash = hash_api_key(API_KEY, PEPPER)
    for _ in range(500):
        repository.increment_rate_limit_counter(
            key_type="api_key",
            key_value_hash=api_key_hash,
            endpoint="/v1/sdk/intercept",
            window_start=day_window_start(),
            window_seconds=86_400,
        )

    response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={"action": "mark_invoice_paid", "payload": {"invoice_id": "INV-1"}},
    )

    assert response.status_code == 429
    assert response.json()["error"] == "intercept_daily_rate_limit_exceeded"


def test_intercept_payload_limits_are_enforced_before_insert() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id=workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="mark_invoice_paid",
        policy_type="always_allow",
    )

    oversized = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={"action": "mark_invoice_paid", "input": {"data": "x" * 17000}},
    )
    oversized_reasoning = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={
            "action": "mark_invoice_paid",
            "payload": {"invoice_id": "INV-1"},
            "reasoning": "x" * 2001,
        },
    )
    normal = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={"action": "mark_invoice_paid", "payload": {"invoice_id": "INV-1"}},
    )

    assert oversized.status_code == 413
    assert oversized.json()["error"] == "payload_too_large"
    assert oversized.json()["limit_bytes"] == 16384
    assert oversized_reasoning.status_code == 422
    assert oversized_reasoning.json()["error"] == "reasoning_too_large"
    assert normal.status_code == 200


def test_public_invalid_token_uses_generic_error() -> None:
    client, _ = _build_client(seed_workspace=False)

    response = client.post("/v1/public/approve/not-a-real-token")

    assert response.status_code == 404
    assert response.json() == {
        "error": "invalid_or_expired_token",
        "message": "This approval link is invalid, expired, or already used.",
    }


def test_public_invalid_token_attempts_are_rate_limited_by_ip() -> None:
    client, _ = _build_client(seed_workspace=False)

    response = None
    for index in range(21):
        response = client.post(
            f"/v1/public/reject/not-a-real-token-{index}",
            headers={"x-forwarded-for": "203.0.113.10"},
        )

    assert response is not None
    assert response.status_code == 429
    assert response.json()["error"] == "public_approval_rate_limit_exceeded"
