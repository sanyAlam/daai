from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
from fastapi.testclient import TestClient

from app.config import Settings
from app.domain import ExecutionStatus, GovernanceStatus
from app.main import create_app
from app.quotas import current_month_window
from fakes import InMemoryGovernanceRepository

SUPABASE_JWT_SECRET = "test-supabase-jwt-secret"
ADMIN_EMAIL = "sany.alam.au@gmail.com"
NON_ADMIN_EMAIL = "beta-user@example.com"


def _dashboard_auth_headers(
    *,
    user_id: UUID | None = None,
    email: str = ADMIN_EMAIL,
) -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": str(user_id or uuid4()),
            "aud": "authenticated",
            "email": email,
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        },
        SUPABASE_JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _build_client(
    repository: InMemoryGovernanceRepository | None = None,
    admin_emails: str = ADMIN_EMAIL,
) -> tuple[TestClient, InMemoryGovernanceRepository]:
    resolved_repository = repository or InMemoryGovernanceRepository()
    app = create_app(
        repository=resolved_repository,
        settings=Settings(
            database_url=None,
            supabase_jwt_secret=SUPABASE_JWT_SECRET,
            admin_emails=admin_emails,
            dev_auto_link_seeded_workspace=False,
        ),
    )
    return TestClient(app), resolved_repository


def _seed_beta_usage(
    repository: InMemoryGovernanceRepository,
) -> tuple[UUID, UUID]:
    activated_user_id = uuid4()
    starter_user_id = uuid4()

    repository.upsert_profile(activated_user_id, "activated@example.com")
    repository.upsert_profile(starter_user_id, "starter@example.com")

    activated_workspace = repository.create_workspace_for_owner(
        owner_user_id=activated_user_id,
        name="Activated Finance Workspace",
        client_name="Activated Finance",
        workspace_key_hash="activated-workspace-key-hash",
        active_workspace_limit=10,
    )
    assert activated_workspace is not None
    starter_workspace = repository.create_workspace_for_owner(
        owner_user_id=starter_user_id,
        name="Starter Workspace",
        client_name="Starter Client",
        workspace_key_hash="starter-workspace-key-hash",
        active_workspace_limit=10,
    )
    assert starter_workspace is not None

    action = repository.add_registered_action(
        workspace_id=activated_workspace.id,
        action_name="send_invoice_reminder",
        policy_type="always_require_approval",
        title="Send invoice reminder",
    )
    run = repository.create_action_run(
        workspace_id=activated_workspace.id,
        action_name=action.action_name,
        registered_action_id=action.id,
        governance_status=GovernanceStatus.APPROVED,
        execution_status=ExecutionStatus.EXECUTED,
        governance_reason="Approved by client",
        payload={"actor": "finance_agent", "amount": 1200},
        policy_snapshot={"policy_type": action.policy_type},
        idempotency_key=None,
        idempotency_payload_hash=None,
    )

    month_start, next_month_start = current_month_window()
    assert repository.reserve_approval_email_quota(
        owner_user_id=activated_user_id,
        workspace_id=activated_workspace.id,
        action_run_id=run.id,
        email_count=2,
        month_start=month_start,
        next_month_start=next_month_start,
        monthly_limit=100,
    )
    return activated_user_id, starter_user_id


def test_non_admin_cannot_access_admin_endpoints() -> None:
    client, _ = _build_client()

    response = client.get(
        "/v1/admin/overview",
        headers=_dashboard_auth_headers(email=NON_ADMIN_EMAIL),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "admin access required"


def test_admin_can_access_admin_endpoints() -> None:
    client, repository = _build_client()
    _seed_beta_usage(repository)

    for path in [
        "/v1/admin/overview",
        "/v1/admin/users",
        "/v1/admin/workspaces",
        "/v1/admin/action-runs/recent",
    ]:
        response = client.get(path, headers=_dashboard_auth_headers())
        assert response.status_code == 200, response.text


def test_admin_overview_counts_return_expected_structure() -> None:
    client, repository = _build_client()
    _seed_beta_usage(repository)

    response = client.get("/v1/admin/overview", headers=_dashboard_auth_headers())

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "total_users": 2,
        "total_workspaces": 2,
        "total_registered_actions": 1,
        "total_action_runs": 1,
        "pending_approvals": 0,
        "approved_actions": 1,
        "blocked_actions": 0,
        "executed_actions": 1,
        "failed_actions": 0,
        "approval_emails_sent_this_month": 2,
        "activated_users": 1,
    }


def test_admin_users_include_activation_calculation_and_recent_runs() -> None:
    client, repository = _build_client()
    _seed_beta_usage(repository)

    users_response = client.get("/v1/admin/users", headers=_dashboard_auth_headers())
    runs_response = client.get(
        "/v1/admin/action-runs/recent",
        headers=_dashboard_auth_headers(),
    )

    assert users_response.status_code == 200
    users = {user["email"]: user for user in users_response.json()}
    assert users["activated@example.com"]["activated"] is True
    assert users["activated@example.com"]["workspace_count"] == 1
    assert users["activated@example.com"]["registered_action_count"] == 1
    assert users["activated@example.com"]["action_run_count"] == 1
    assert users["starter@example.com"]["activated"] is False

    assert runs_response.status_code == 200
    recent_runs = runs_response.json()
    assert len(recent_runs) == 1
    assert recent_runs[0]["workspace_name"] == "Activated Finance Workspace"
    assert recent_runs[0]["owner_email"] == "activated@example.com"
    assert recent_runs[0]["action_name"] == "send_invoice_reminder"
    assert recent_runs[0]["actor"] == "finance_agent"
    assert recent_runs[0]["governance_status"] == "approved"
    assert recent_runs[0]["executable"] is True
    assert recent_runs[0]["execution_status"] == "executed"
