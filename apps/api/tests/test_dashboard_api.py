from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import jwt
from fastapi.testclient import TestClient

from app.config import Settings
from app.domain import ExecutionStatus, GovernanceStatus
from app.hashing import hash_api_key, hash_approval_token, hash_workspace_key
from app.main import create_app
from app.quotas import current_month_window, minute_window_start
from app.policy_suggestion import OpenAIPolicySuggester
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
        approve_url = getattr(links, "approve_url")
        reject_url = getattr(links, "reject_url")
        block_url = getattr(links, "block_url")
        self.sent_links.append(
            PendingApprovalLinkCapture(
                approve_url=approve_url,
                reject_url=reject_url,
                block_url=block_url,
            )
        )

    def latest_approve_token(self) -> str:
        return self.sent_links[-1].approve_url.rsplit("/", 1)[1]

    def latest_reject_token(self) -> str:
        return self.sent_links[-1].reject_url.rsplit("/", 1)[1]

    def latest_block_token(self) -> str:
        return self.sent_links[-1].block_url.rsplit("/", 1)[1]


class FakeOpenAIResponses:
    def __init__(self, parsed: dict[str, Any] | None = None, error: Exception | None = None):
        self._parsed = parsed
        self._error = error
        self.calls: list[dict[str, Any]] = []

    def parse(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return SimpleNamespace(output_parsed=self._parsed)


class FakeOpenAIClient:
    def __init__(self, responses: FakeOpenAIResponses):
        self.responses = responses


class CountingPolicySuggester:
    def __init__(self) -> None:
        self.calls = 0

    def suggest(self, request: object) -> object:
        self.calls += 1
        raise AssertionError("runtime interception must not request policy suggestions")


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
    workspace_id: UUID,
    workspace_name: str = "DAAI Demo Workspace",
    dashboard_user_id: UUID = DASHBOARD_USER_ID,
    dashboard_user_email: str = DASHBOARD_EMAIL,
    policy_suggester: object | None = None,
) -> tuple[TestClient, InMemoryGovernanceRepository]:
    repository = InMemoryGovernanceRepository()
    notifier = CaptureApprovalLinkNotifier()
    repository.add_workspace_key_hash(
        workspace_id=workspace_id,
        workspace_key_hash=hash_workspace_key(WORKSPACE_KEY, PEPPER),
        name=workspace_name,
    )
    repository.add_api_key_hash(
        workspace_id=workspace_id,
        key_hash=hash_api_key(API_KEY, PEPPER),
    )
    repository.upsert_profile(
        user_id=dashboard_user_id,
        email=dashboard_user_email,
    )
    repository.ensure_workspace_membership(
        workspace_id=workspace_id,
        user_id=dashboard_user_id,
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
        policy_suggester=policy_suggester,
    )
    repository.approval_notifier = notifier
    return TestClient(app), repository


def _create_seed_run(
    repository: InMemoryGovernanceRepository,
    workspace_id: UUID,
    *,
    action: str,
    governance_status: GovernanceStatus,
    execution_status: ExecutionStatus,
    governance_reason: str,
    payload: dict[str, object] | None = None,
    created_at: datetime | None = None,
):
    run = repository.create_action_run(
        workspace_id=workspace_id,
        action_name=action,
        registered_action_id=None,
        governance_status=governance_status,
        execution_status=execution_status,
        governance_reason=governance_reason,
        payload=payload or {},
        policy_snapshot={"policy_type": "seed"},
        idempotency_key=None,
        idempotency_payload_hash=None,
    )
    run.governance_status = governance_status
    run.execution_status = execution_status
    run.governance_reason = governance_reason
    run.payload = payload or {}
    if created_at is not None:
        run.created_at = created_at
        run.decided_at = created_at
    return run


def _create_pending_run_via_intercept(
    client: TestClient,
    repository: InMemoryGovernanceRepository,
    workspace_id: UUID,
    *,
    action_name: str = "pay_vendor",
    amount: int = 9000,
    idempotency_key: str | None = None,
) -> str:
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name=action_name,
        policy_type="always_require_approval",
    )
    response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={
            "action": action_name,
            "payload": {"amount": amount, "vendor": "acme"},
            "idempotency_key": idempotency_key,
        },
    )
    assert response.status_code == 200
    assert response.json()["governance_status"] == "pending_approval"
    return str(response.json()["action_run_id"])


def _suggestion_request_payload() -> dict[str, object]:
    return {
        "action_name": "send_invoice_reminder",
        "title": "Send invoice reminder",
        "description": "Sends a polite reminder email to a customer for an overdue invoice.",
        "risk_level": "medium",
        "approver_email": "owner@example.com",
        "setup_answers": {
            "main_action_type": "contacts_customer_supplier_or_external_person",
            "main_action_type_other": "",
            "biggest_risk": "financial_loss_or_incorrect_payment_handling",
            "biggest_risk_other": "",
            "approval_preference": "only_above_money_threshold",
            "approval_preference_other": "",
            "additional_context": "Client wants reminders above $500 approved first.",
        },
    }


def _valid_policy_suggestion() -> dict[str, object]:
    return {
        "risk_level": "medium",
        "rule_type": "require_approval_above_amount",
        "threshold_amount": 500,
        "approval_triggers": ["amount_above_threshold", "external_recipient"],
        "risk_factors": ["financial_impact", "external_communication"],
        "explanation": (
            "Approval is recommended for invoice reminders above $500 because the "
            "action contacts an external customer about a financial matter."
        ),
        "client_facing_summary": (
            "This action may contact customers about overdue invoices. Higher-value "
            "reminders should be reviewed before sending."
        ),
        "receipt_summary_template": (
            "The agent proposed sending an invoice reminder. Approval was required "
            "because the invoice amount exceeded the configured threshold."
        ),
        "confidence": "high",
    }


def test_dashboard_workspaces_returns_authenticated_workspace() -> None:
    workspace_id = uuid4()
    client, _ = _build_client(workspace_id)

    list_response = client.get(
        "/v1/dashboard/workspaces",
        headers=_dashboard_auth_headers(),
    )

    assert list_response.status_code == 200
    workspaces = list_response.json()
    assert len(workspaces) == 1
    assert workspaces[0]["id"] == str(workspace_id)
    assert workspaces[0]["name"] == "DAAI Demo Workspace"
    assert workspaces[0]["status"] == "active"

    detail_response = client.get(
        f"/v1/dashboard/workspaces/{workspace_id}",
        headers=_dashboard_auth_headers(),
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == str(workspace_id)


def test_dashboard_delete_workspace_requires_exact_name_confirmation() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)

    response = client.request(
        "DELETE",
        f"/v1/dashboard/workspaces/{workspace_id}",
        headers=_dashboard_auth_headers(),
        json={"workspace_name_confirmation": "Wrong workspace"},
    )

    assert response.status_code == 422
    assert "workspace name exactly" in response.json()["detail"]
    assert repository.get_workspace(workspace_id) is not None


def test_dashboard_delete_workspace_removes_workspace_owned_records() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    action = repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="pay_vendor",
        policy_type="always_require_approval",
    )
    run = repository.create_action_run(
        workspace_id=workspace_id,
        action_name=action.action_name,
        registered_action_id=action.id,
        governance_status=GovernanceStatus.BLOCKED,
        execution_status=ExecutionStatus.NOT_EXECUTED,
        governance_reason="seed",
        payload={"amount": 900},
        policy_snapshot={"policy_type": action.policy_type},
        idempotency_key="delete-test",
        idempotency_payload_hash="payload-hash",
    )
    repository.create_governance_receipt(
        workspace_id=workspace_id,
        action_run_id=run.id,
        outcome=GovernanceStatus.BLOCKED,
        reason="seed",
        policy_type=action.policy_type,
        policy_snapshot={"policy_type": action.policy_type},
    )
    token_hash = hash_approval_token("delete-token", PEPPER)
    assert repository.create_action_decision_tokens(
        workspace_id=workspace_id,
        action_run_id=run.id,
        approve_token_hash=token_hash,
        reject_token_hash=hash_approval_token("delete-reject-token", PEPPER),
        block_token_hash=hash_approval_token("delete-block-token", PEPPER),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    month_start, next_month_start = current_month_window()
    assert repository.reserve_approval_email_quota(
        owner_user_id=DASHBOARD_USER_ID,
        workspace_id=workspace_id,
        action_run_id=run.id,
        email_count=1,
        month_start=month_start,
        next_month_start=next_month_start,
        monthly_limit=100,
    )
    api_key_hash = hash_api_key(API_KEY, PEPPER)
    assert repository.increment_rate_limit_counter(
        key_type="api_key",
        key_value_hash=api_key_hash,
        endpoint="/v1/sdk/intercept",
        window_start=minute_window_start(),
        window_seconds=60,
    ) == 1

    response = client.request(
        "DELETE",
        f"/v1/dashboard/workspaces/{workspace_id}",
        headers=_dashboard_auth_headers(),
        json={"workspace_name_confirmation": "DAAI Demo Workspace"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": str(workspace_id),
        "name": "DAAI Demo Workspace",
        "deleted": True,
    }
    assert repository.get_workspace(workspace_id) is None
    assert repository.list_workspaces_for_user(DASHBOARD_USER_ID) == []
    assert repository.list_registered_actions(workspace_id) == []
    assert repository.get_action_run(workspace_id, run.id) is None
    assert repository.get_action_run_by_id(run.id) is None
    assert repository.get_governance_receipt(workspace_id, run.id) is None
    assert repository.list_workspace_api_keys_for_user(DASHBOARD_USER_ID) == []
    assert repository.action_run_count == 0
    assert repository.receipt_count == 0
    assert repository.approval_email_count == 0
    assert repository.count_active_workspaces_for_owner(DASHBOARD_USER_ID) == 0
    assert repository.increment_rate_limit_counter(
        key_type="api_key",
        key_value_hash=api_key_hash,
        endpoint="/v1/sdk/intercept",
        window_start=minute_window_start(),
        window_seconds=60,
    ) == 1


def test_dashboard_workspace_actions_returns_registered_actions() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="pay_vendor",
        policy_type="require_approval_above_amount",
        policy_config={"threshold": 5000, "amount_field": "amount"},
        title="Pay vendor",
        description="Pays an approved vendor invoice.",
        risk_level="high",
    )
    repository.update_workspace_approval_settings(
        workspace_id=workspace_id,
        approval_emails=["approver@example.com"],
        approval_link_ttl_minutes=15,
    )

    response = client.get(
        f"/v1/dashboard/workspaces/{workspace_id}/actions",
        headers=_dashboard_auth_headers(),
    )

    assert response.status_code == 200
    actions = response.json()
    assert len(actions) == 1
    assert actions[0]["action_name"] == "pay_vendor"
    assert actions[0]["title"] == "Pay vendor"
    assert actions[0]["description"] == "Pays an approved vendor invoice."
    assert actions[0]["risk_level"] == "high"
    assert actions[0]["is_active"] is True
    assert actions[0]["policy_type"] == "require_approval_above_amount"
    assert actions[0]["policy"]["rule_type"] == "require_approval_above_amount"
    assert actions[0]["policy"]["threshold_amount"] == 5000
    assert actions[0]["approver_email"] == "approver@example.com"


def test_suggest_policy_returns_structured_policy_for_external_invoice_reminder() -> None:
    workspace_id = uuid4()
    responses = FakeOpenAIResponses(parsed=_valid_policy_suggestion())
    client, _ = _build_client(
        workspace_id,
        policy_suggester=OpenAIPolicySuggester(
            api_key="test-openai-key",
            model="gpt-5.4-mini",
            client=FakeOpenAIClient(responses),
        ),
    )

    response = client.post(
        f"/v1/workspaces/{workspace_id}/actions/suggest-policy",
        headers=_dashboard_auth_headers(),
        json=_suggestion_request_payload(),
    )

    assert response.status_code == 200
    suggestion = response.json()
    assert suggestion["rule_type"] == "require_approval_above_amount"
    assert suggestion["threshold_amount"] == 500
    assert suggestion["approval_triggers"] == [
        "amount_above_threshold",
        "external_recipient",
    ]
    assert responses.calls[0]["model"] == "gpt-5.4-mini"


def test_suggest_policy_returns_safe_fallback_when_openai_key_is_missing() -> None:
    workspace_id = uuid4()
    client, _ = _build_client(workspace_id)

    response = client.post(
        f"/v1/workspaces/{workspace_id}/actions/suggest-policy",
        headers=_dashboard_auth_headers(),
        json=_suggestion_request_payload(),
    )

    assert response.status_code == 200
    suggestion = response.json()
    assert suggestion["rule_type"] == "always_require_approval"
    assert suggestion["risk_factors"] == ["policy_suggestion_uncertain"]
    assert suggestion["confidence"] == "low"


def test_suggest_policy_returns_safe_fallback_when_openai_client_fails() -> None:
    workspace_id = uuid4()
    client, _ = _build_client(
        workspace_id,
        policy_suggester=OpenAIPolicySuggester(
            api_key="test-openai-key",
            model="gpt-5.4-mini",
            client=FakeOpenAIClient(
                FakeOpenAIResponses(error=RuntimeError("OpenAI unavailable"))
            ),
        ),
    )

    response = client.post(
        f"/v1/workspaces/{workspace_id}/actions/suggest-policy",
        headers=_dashboard_auth_headers(),
        json=_suggestion_request_payload(),
    )

    assert response.status_code == 200
    assert response.json()["approval_triggers"] == ["manual_review_recommended"]


def test_suggest_policy_rejects_invalid_llm_enum_with_fallback() -> None:
    workspace_id = uuid4()
    invalid_suggestion = _valid_policy_suggestion()
    invalid_suggestion["rule_type"] = "approval_by_magic"
    client, _ = _build_client(
        workspace_id,
        policy_suggester=OpenAIPolicySuggester(
            api_key="test-openai-key",
            model="gpt-5.4-mini",
            client=FakeOpenAIClient(FakeOpenAIResponses(parsed=invalid_suggestion)),
        ),
    )

    response = client.post(
        f"/v1/workspaces/{workspace_id}/actions/suggest-policy",
        headers=_dashboard_auth_headers(),
        json=_suggestion_request_payload(),
    )

    assert response.status_code == 200
    assert response.json()["rule_type"] == "always_require_approval"
    assert response.json()["risk_factors"] == ["policy_suggestion_uncertain"]


def test_dashboard_user_can_create_action_in_their_workspace() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)

    response = client.post(
        f"/v1/dashboard/workspaces/{workspace_id}/actions",
        headers=_dashboard_auth_headers(),
        json={
            "action_name": "send_invoice_reminder",
            "title": "Send invoice reminder",
            "description": "Sends a payment reminder to an overdue invoice customer.",
            "risk_level": "medium",
            "policy_type": "always_require_approval",
            "threshold_amount": None,
            "approver_email": "Tester@Example.com",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workspace_id"] == str(workspace_id)
    assert payload["action_name"] == "send_invoice_reminder"
    assert payload["title"] == "Send invoice reminder"
    assert payload["risk_level"] == "medium"
    assert payload["is_active"] is True
    assert payload["policy_type"] == "always_require_approval"
    assert payload["policy"] == {
        "rule_type": "always_require_approval",
        "threshold_amount": None,
    }
    assert payload["approver_email"] == "tester@example.com"

    created = repository.get_registered_action(
        workspace_id=workspace_id,
        action_name="send_invoice_reminder",
    )
    assert created is not None
    assert created.policy_type == "always_require_approval"
    assert repository.get_workspace(workspace_id).approval_emails == [
        "tester@example.com"
    ]


def test_dashboard_can_save_confirmed_suggested_policy_snapshot() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    setup_answers = _suggestion_request_payload()["setup_answers"]
    suggestion = _valid_policy_suggestion()

    response = client.post(
        f"/v1/dashboard/workspaces/{workspace_id}/actions",
        headers=_dashboard_auth_headers(),
        json={
            "action_name": "send_invoice_reminder",
            "title": "Send invoice reminder",
            "description": "Sends a payment reminder to an overdue invoice customer.",
            "risk_level": "medium",
            "policy_type": "require_approval_above_amount",
            "threshold_amount": 500,
            "approver_email": "owner@example.com",
            "explanation": suggestion["explanation"],
            "approval_triggers": suggestion["approval_triggers"],
            "risk_factors": suggestion["risk_factors"],
            "client_facing_summary": suggestion["client_facing_summary"],
            "receipt_summary_template": suggestion["receipt_summary_template"],
            "policy_source": "llm_suggested_confirmed",
            "setup_answers": setup_answers,
            "policy_suggestion_snapshot": suggestion,
        },
    )

    assert response.status_code == 200
    created = repository.get_registered_action(
        workspace_id=workspace_id,
        action_name="send_invoice_reminder",
    )
    assert created is not None
    assert created.policy_type == "require_approval_above_amount"
    assert created.policy_config["threshold"] == 500
    assert created.policy_config["policy_source"] == "llm_suggested_confirmed"
    assert created.policy_config["setup_answers"] == setup_answers
    assert created.policy_config["policy_suggestion_snapshot"] == suggestion


def test_dashboard_user_cannot_create_action_in_another_workspace() -> None:
    workspace_id = uuid4()
    other_workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_workspace_key_hash(
        workspace_id=other_workspace_id,
        workspace_key_hash=hash_workspace_key("other-workspace-key", PEPPER),
        name="Other Workspace",
    )

    response = client.post(
        f"/v1/dashboard/workspaces/{other_workspace_id}/actions",
        headers=_dashboard_auth_headers(),
        json={
            "action_name": "send_invoice_reminder",
            "title": "Send invoice reminder",
            "description": "Sends a payment reminder.",
            "risk_level": "medium",
            "policy_type": "always_allow",
        },
    )

    assert response.status_code == 404
    assert repository.get_registered_action(
        workspace_id=other_workspace_id,
        action_name="send_invoice_reminder",
    ) is None


def test_dashboard_create_action_rejects_duplicate_action_name() -> None:
    workspace_id = uuid4()
    client, _ = _build_client(workspace_id)
    payload = {
        "action_name": "send_invoice_reminder",
        "title": "Send invoice reminder",
        "description": "Sends a payment reminder.",
        "risk_level": "medium",
        "policy_type": "always_allow",
    }

    first_response = client.post(
        f"/v1/dashboard/workspaces/{workspace_id}/actions",
        headers=_dashboard_auth_headers(),
        json=payload,
    )
    duplicate_response = client.post(
        f"/v1/dashboard/workspaces/{workspace_id}/actions",
        headers=_dashboard_auth_headers(),
        json=payload,
    )

    assert first_response.status_code == 200
    assert duplicate_response.status_code == 409
    assert "already exists" in duplicate_response.json()["detail"]


def test_dashboard_create_action_rejects_invalid_action_name() -> None:
    workspace_id = uuid4()
    client, _ = _build_client(workspace_id)

    response = client.post(
        f"/v1/dashboard/workspaces/{workspace_id}/actions",
        headers=_dashboard_auth_headers(),
        json={
            "action_name": "SendInvoiceReminder",
            "title": "Send invoice reminder",
            "description": "Sends a payment reminder.",
            "risk_level": "medium",
            "policy_type": "always_allow",
        },
    )

    assert response.status_code == 422


def test_dashboard_amount_policy_requires_threshold_amount() -> None:
    workspace_id = uuid4()
    client, _ = _build_client(workspace_id)

    response = client.post(
        f"/v1/dashboard/workspaces/{workspace_id}/actions",
        headers=_dashboard_auth_headers(),
        json={
            "action_name": "send_invoice_reminder",
            "title": "Send invoice reminder",
            "description": "Sends a payment reminder.",
            "risk_level": "medium",
            "policy_type": "require_approval_above_amount",
            "approver_email": "approver@example.com",
        },
    )

    assert response.status_code == 422
    assert "threshold_amount is required" in response.json()["detail"]


def test_dashboard_approval_policy_requires_approver_when_workspace_has_none() -> None:
    workspace_id = uuid4()
    client, _ = _build_client(workspace_id)

    response = client.post(
        f"/v1/dashboard/workspaces/{workspace_id}/actions",
        headers=_dashboard_auth_headers(),
        json={
            "action_name": "send_invoice_reminder",
            "title": "Send invoice reminder",
            "description": "Sends a payment reminder.",
            "risk_level": "medium",
            "policy_type": "always_require_approval",
        },
    )

    assert response.status_code == 422
    assert "approver_email is required" in response.json()["detail"]


def test_dashboard_created_action_is_returned_by_get_with_policy_summary() -> None:
    workspace_id = uuid4()
    client, _ = _build_client(workspace_id)

    create_response = client.post(
        f"/v1/dashboard/workspaces/{workspace_id}/actions",
        headers=_dashboard_auth_headers(),
        json={
            "action_name": "send_invoice_reminder",
            "title": "Send invoice reminder",
            "description": "Sends a payment reminder to an overdue invoice customer.",
            "risk_level": "medium",
            "policy_type": "require_approval_above_amount",
            "threshold_amount": 250,
            "approver_email": "approver@example.com",
        },
    )
    assert create_response.status_code == 200

    list_response = client.get(
        f"/v1/dashboard/workspaces/{workspace_id}/actions",
        headers=_dashboard_auth_headers(),
    )

    assert list_response.status_code == 200
    actions = list_response.json()
    assert len(actions) == 1
    assert actions[0]["action_name"] == "send_invoice_reminder"
    assert actions[0]["policy"]["rule_type"] == "require_approval_above_amount"
    assert actions[0]["policy"]["threshold_amount"] == 250
    assert actions[0]["approver_email"] == "approver@example.com"


def test_sdk_intercept_for_dashboard_registered_approval_action_is_pending() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)

    create_response = client.post(
        f"/v1/dashboard/workspaces/{workspace_id}/actions",
        headers=_dashboard_auth_headers(),
        json={
            "action_name": "send_invoice_reminder",
            "title": "Send invoice reminder",
            "description": "Sends a payment reminder to an overdue invoice customer.",
            "risk_level": "medium",
            "policy_type": "always_require_approval",
            "approver_email": "approver@example.com",
        },
    )
    assert create_response.status_code == 200

    intercept_response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={
            "action": "send_invoice_reminder",
            "payload": {"invoice_id": "INV-1025"},
            "idempotency_key": "invoice-reminder:INV-1025",
        },
    )

    assert intercept_response.status_code == 200
    payload = intercept_response.json()
    assert payload["governance_status"] == "pending_approval"
    assert payload["governance_reason"] == "policy_requires_approval"
    assert payload["executable"] is False
    assert len(repository.approval_notifier.sent_links) == 1


def test_sdk_intercept_never_calls_policy_suggester_at_runtime() -> None:
    workspace_id = uuid4()
    policy_suggester = CountingPolicySuggester()
    client, repository = _build_client(
        workspace_id,
        policy_suggester=policy_suggester,
    )
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="send_invoice_reminder",
        policy_type="require_approval_when_external_recipient",
    )
    repository.update_workspace_approval_settings(
        workspace_id=workspace_id,
        approval_emails=["owner@example.com"],
        approval_link_ttl_minutes=15,
    )

    response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={
            "action": "send_invoice_reminder",
            "payload": {"external_recipient": True},
        },
    )

    assert response.status_code == 200
    assert response.json()["governance_status"] == "pending_approval"
    assert policy_suggester.calls == 0


def test_dashboard_workspace_runs_and_detail_show_full_action_story() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="pay_vendor",
        policy_type="require_approval_above_amount",
        policy_config={"threshold": 5000, "amount_field": "amount"},
    )

    intercept_response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={
            "action": "pay_vendor",
            "payload": {"amount": 9000, "vendor_id": "VENDOR-42"},
            "idempotency_key": "dashboard-story:pay_vendor:9000",
        },
    )
    assert intercept_response.status_code == 200
    action_run_id = intercept_response.json()["action_run_id"]

    approve_token = repository.approval_notifier.latest_approve_token()
    approve_response = client.post(f"/v1/public/approve/{approve_token}")
    assert approve_response.status_code == 200

    report_response = client.post(
        f"/v1/sdk/action-runs/{action_run_id}/report-executed",
        headers=_auth_headers(),
        json={"execution_result": {"provider_id": "pay_123"}},
    )
    assert report_response.status_code == 200

    runs_response = client.get(
        f"/v1/dashboard/workspaces/{workspace_id}/runs",
        headers=_dashboard_auth_headers(),
    )
    assert runs_response.status_code == 200
    runs_page = runs_response.json()
    assert runs_page["page"] == 1
    assert runs_page["page_size"] == 25
    assert runs_page["total"] == 1
    assert runs_page["total_pages"] == 1
    runs = runs_page["items"]
    assert len(runs) == 1
    assert runs[0]["action_run_id"] == action_run_id
    assert runs[0]["action"] == "pay_vendor"
    assert runs[0]["governance_status"] == "approved"
    assert runs[0]["execution_status"] == "executed"
    assert runs[0]["executable"] is True
    assert runs[0]["governance_reason"] == "approved_by_human"
    assert runs[0]["receipt"]["outcome"] == "approved"

    detail_response = client.get(
        f"/v1/dashboard/workspaces/{workspace_id}/runs/{action_run_id}",
        headers=_dashboard_auth_headers(),
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["action_run_id"] == action_run_id
    assert detail["payload"]["amount"] == 9000
    assert detail["execution_result"]["provider_id"] == "pay_123"
    assert detail["receipt"]["outcome"] == "approved"
    assert detail["receipt"]["created_at"] is not None


def test_authenticated_workspace_member_can_fetch_metrics() -> None:
    workspace_id = uuid4()
    client, _ = _build_client(workspace_id)

    response = client.get(
        f"/v1/dashboard/workspaces/{workspace_id}/metrics",
        headers=_dashboard_auth_headers(),
    )

    assert response.status_code == 200
    assert response.json()["total_runs"] == 0


def test_unauthenticated_user_cannot_fetch_workspace_metrics() -> None:
    workspace_id = uuid4()
    client, _ = _build_client(workspace_id)

    response = client.get(
        f"/v1/dashboard/workspaces/{workspace_id}/metrics",
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 401


def test_user_cannot_fetch_metrics_for_another_users_workspace() -> None:
    workspace_id = uuid4()
    other_workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_workspace_key_hash(
        workspace_id=other_workspace_id,
        workspace_key_hash=hash_workspace_key("wsk_metrics_other", PEPPER),
        name="Other Workspace",
    )
    repository.ensure_workspace_membership(
        workspace_id=other_workspace_id,
        user_id=UUID("bbbbbbbb-2222-2222-2222-222222222222"),
        role="owner",
    )

    response = client.get(
        f"/v1/dashboard/workspaces/{other_workspace_id}/metrics",
        headers=_dashboard_auth_headers(),
    )

    assert response.status_code == 404


def test_workspace_metrics_counts_reflect_seeded_statuses() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)

    _create_seed_run(
        repository,
        workspace_id,
        action="invoice_paid",
        governance_status=GovernanceStatus.ALLOWED,
        execution_status=ExecutionStatus.EXECUTED,
        governance_reason="always_allow",
    )
    _create_seed_run(
        repository,
        workspace_id,
        action="invoice_sync",
        governance_status=GovernanceStatus.ALLOWED,
        execution_status=ExecutionStatus.FAILED,
        governance_reason="always_allow",
    )
    _create_seed_run(
        repository,
        workspace_id,
        action="approve_payout",
        governance_status=GovernanceStatus.PENDING_APPROVAL,
        execution_status=ExecutionStatus.NOT_EXECUTED,
        governance_reason="pending_human_approval",
    )
    _create_seed_run(
        repository,
        workspace_id,
        action="pay_vendor",
        governance_status=GovernanceStatus.APPROVED,
        execution_status=ExecutionStatus.AWAITING_EXECUTION_REPORT,
        governance_reason="approved_by_human",
    )
    _create_seed_run(
        repository,
        workspace_id,
        action="reject_vendor",
        governance_status=GovernanceStatus.REJECTED,
        execution_status=ExecutionStatus.NOT_EXECUTED,
        governance_reason="rejected_by_human",
    )
    _create_seed_run(
        repository,
        workspace_id,
        action="unknown_action",
        governance_status=GovernanceStatus.BLOCKED,
        execution_status=ExecutionStatus.NOT_EXECUTED,
        governance_reason="unknown_action",
    )

    response = client.get(
        f"/v1/dashboard/workspaces/{workspace_id}/metrics",
        headers=_dashboard_auth_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_runs"] == 6
    assert payload["pending_approval"] == 1
    assert payload["approved"] == 1
    assert payload["rejected"] == 1
    assert payload["blocked"] == 1
    assert payload["allowed"] == 2
    assert payload["executed"] == 1
    assert payload["failed"] == 1


def test_runs_list_returns_paginated_response_shape() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    _create_seed_run(
        repository,
        workspace_id,
        action="invoice_a",
        governance_status=GovernanceStatus.ALLOWED,
        execution_status=ExecutionStatus.NOT_EXECUTED,
        governance_reason="always_allow",
    )
    _create_seed_run(
        repository,
        workspace_id,
        action="invoice_b",
        governance_status=GovernanceStatus.ALLOWED,
        execution_status=ExecutionStatus.NOT_EXECUTED,
        governance_reason="always_allow",
    )

    response = client.get(
        f"/v1/dashboard/workspaces/{workspace_id}/runs?page=1&page_size=1",
        headers=_dashboard_auth_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {"items", "page", "page_size", "total", "total_pages"}
    assert payload["page"] == 1
    assert payload["page_size"] == 1
    assert payload["total"] == 2
    assert payload["total_pages"] == 2
    assert len(payload["items"]) == 1


def test_runs_list_default_page_size_is_25() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)

    for index in range(30):
        _create_seed_run(
            repository,
            workspace_id,
            action=f"invoice_{index}",
            governance_status=GovernanceStatus.ALLOWED,
            execution_status=ExecutionStatus.NOT_EXECUTED,
            governance_reason="always_allow",
        )

    response = client.get(
        f"/v1/dashboard/workspaces/{workspace_id}/runs",
        headers=_dashboard_auth_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["page_size"] == 25
    assert len(payload["items"]) == 25
    assert payload["total"] == 30


def test_runs_list_enforces_max_page_size_of_100() -> None:
    workspace_id = uuid4()
    client, _ = _build_client(workspace_id)

    response = client.get(
        f"/v1/dashboard/workspaces/{workspace_id}/runs?page=1&page_size=101",
        headers=_dashboard_auth_headers(),
    )

    assert response.status_code == 422


def test_runs_list_sorts_newest_first() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    older = datetime.now(timezone.utc) - timedelta(days=1)
    newer = datetime.now(timezone.utc)

    _create_seed_run(
        repository,
        workspace_id,
        action="older_run",
        governance_status=GovernanceStatus.ALLOWED,
        execution_status=ExecutionStatus.NOT_EXECUTED,
        governance_reason="always_allow",
        created_at=older,
    )
    _create_seed_run(
        repository,
        workspace_id,
        action="newer_run",
        governance_status=GovernanceStatus.ALLOWED,
        execution_status=ExecutionStatus.NOT_EXECUTED,
        governance_reason="always_allow",
        created_at=newer,
    )

    response = client.get(
        f"/v1/dashboard/workspaces/{workspace_id}/runs?page=1&page_size=25",
        headers=_dashboard_auth_headers(),
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert items[0]["action"] == "newer_run"
    assert items[1]["action"] == "older_run"


def test_runs_search_filters_by_action_name() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    _create_seed_run(
        repository,
        workspace_id,
        action="invoice_reminder",
        governance_status=GovernanceStatus.ALLOWED,
        execution_status=ExecutionStatus.NOT_EXECUTED,
        governance_reason="always_allow",
    )
    _create_seed_run(
        repository,
        workspace_id,
        action="vendor_payout",
        governance_status=GovernanceStatus.ALLOWED,
        execution_status=ExecutionStatus.NOT_EXECUTED,
        governance_reason="always_allow",
    )

    response = client.get(
        f"/v1/dashboard/workspaces/{workspace_id}/runs?search=invoice",
        headers=_dashboard_auth_headers(),
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["action"] == "invoice_reminder"


def test_runs_search_filters_by_governance_reason() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    _create_seed_run(
        repository,
        workspace_id,
        action="invoice_reminder",
        governance_status=GovernanceStatus.ALLOWED,
        execution_status=ExecutionStatus.NOT_EXECUTED,
        governance_reason="always_allow",
    )
    _create_seed_run(
        repository,
        workspace_id,
        action="vendor_payout",
        governance_status=GovernanceStatus.PENDING_APPROVAL,
        execution_status=ExecutionStatus.NOT_EXECUTED,
        governance_reason="needs_manual_review",
    )

    response = client.get(
        f"/v1/dashboard/workspaces/{workspace_id}/runs?search=manual_review",
        headers=_dashboard_auth_headers(),
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["action"] == "vendor_payout"


def test_runs_governance_status_filter_works() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    _create_seed_run(
        repository,
        workspace_id,
        action="pending_review",
        governance_status=GovernanceStatus.PENDING_APPROVAL,
        execution_status=ExecutionStatus.NOT_EXECUTED,
        governance_reason="needs_approval",
    )
    _create_seed_run(
        repository,
        workspace_id,
        action="already_approved",
        governance_status=GovernanceStatus.APPROVED,
        execution_status=ExecutionStatus.AWAITING_EXECUTION_REPORT,
        governance_reason="approved_by_human",
    )

    response = client.get(
        f"/v1/dashboard/workspaces/{workspace_id}/runs?governance_status=approved",
        headers=_dashboard_auth_headers(),
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["governance_status"] == "approved"


def test_runs_execution_status_filter_works() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    _create_seed_run(
        repository,
        workspace_id,
        action="executed_run",
        governance_status=GovernanceStatus.ALLOWED,
        execution_status=ExecutionStatus.EXECUTED,
        governance_reason="always_allow",
    )
    _create_seed_run(
        repository,
        workspace_id,
        action="failed_run",
        governance_status=GovernanceStatus.ALLOWED,
        execution_status=ExecutionStatus.FAILED,
        governance_reason="always_allow",
    )

    response = client.get(
        f"/v1/dashboard/workspaces/{workspace_id}/runs?execution_status=failed",
        headers=_dashboard_auth_headers(),
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["execution_status"] == "failed"


def test_runs_combined_search_and_filters_work() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    _create_seed_run(
        repository,
        workspace_id,
        action="invoice_sync",
        governance_status=GovernanceStatus.APPROVED,
        execution_status=ExecutionStatus.EXECUTED,
        governance_reason="approved_by_human",
    )
    _create_seed_run(
        repository,
        workspace_id,
        action="invoice_sync",
        governance_status=GovernanceStatus.PENDING_APPROVAL,
        execution_status=ExecutionStatus.NOT_EXECUTED,
        governance_reason="pending_human_approval",
    )
    _create_seed_run(
        repository,
        workspace_id,
        action="vendor_sync",
        governance_status=GovernanceStatus.APPROVED,
        execution_status=ExecutionStatus.EXECUTED,
        governance_reason="approved_by_human",
    )

    response = client.get(
        f"/v1/dashboard/workspaces/{workspace_id}/runs?search=invoice&governance_status=approved&execution_status=executed",
        headers=_dashboard_auth_headers(),
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["action"] == "invoice_sync"
    assert items[0]["governance_status"] == "approved"
    assert items[0]["execution_status"] == "executed"


def test_user_cannot_list_runs_for_another_users_workspace() -> None:
    workspace_id = uuid4()
    other_workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_workspace_key_hash(
        workspace_id=other_workspace_id,
        workspace_key_hash=hash_workspace_key("wsk_runs_other", PEPPER),
        name="Other Workspace",
    )
    repository.ensure_workspace_membership(
        workspace_id=other_workspace_id,
        user_id=UUID("bbbbbbbb-2222-2222-2222-222222222222"),
        role="owner",
    )

    response = client.get(
        f"/v1/dashboard/workspaces/{other_workspace_id}/runs",
        headers=_dashboard_auth_headers(),
    )

    assert response.status_code == 404


def test_dashboard_workspace_scope_enforced() -> None:
    workspace_id = uuid4()
    other_workspace_id = uuid4()
    client, _ = _build_client(workspace_id)

    response = client.get(
        f"/v1/dashboard/workspaces/{other_workspace_id}",
        headers=_dashboard_auth_headers(),
    )

    assert response.status_code == 404


def test_dashboard_workspaces_are_scoped_to_authenticated_user() -> None:
    user_workspace_id = uuid4()
    second_user_workspace_id = uuid4()
    other_user_workspace_id = uuid4()

    client, repository = _build_client(user_workspace_id)
    repository.add_workspace_key_hash(
        workspace_id=second_user_workspace_id,
        workspace_key_hash=hash_workspace_key("wsk_secondary", PEPPER),
        name="Second Workspace",
    )
    repository.ensure_workspace_membership(
        workspace_id=second_user_workspace_id,
        user_id=DASHBOARD_USER_ID,
        role="member",
    )
    repository.add_workspace_key_hash(
        workspace_id=other_user_workspace_id,
        workspace_key_hash=hash_workspace_key("wsk_other", PEPPER),
        name="Other User Workspace",
    )
    repository.ensure_workspace_membership(
        workspace_id=other_user_workspace_id,
        user_id=UUID("bbbbbbbb-2222-2222-2222-222222222222"),
        role="owner",
    )

    response = client.get(
        "/v1/dashboard/workspaces",
        headers=_dashboard_auth_headers(),
    )

    assert response.status_code == 200
    workspace_ids = {workspace["id"] for workspace in response.json()}
    assert str(user_workspace_id) in workspace_ids
    assert str(second_user_workspace_id) in workspace_ids
    assert str(other_user_workspace_id) not in workspace_ids


def test_dashboard_rejects_invalid_supabase_token() -> None:
    workspace_id = uuid4()
    client, _ = _build_client(workspace_id)

    response = client.get(
        "/v1/dashboard/workspaces",
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 401


def test_dashboard_create_workspace_links_owner_and_returns_workspace_key() -> None:
    existing_workspace_id = uuid4()
    client, repository = _build_client(existing_workspace_id)

    create_response = client.post(
        "/v1/dashboard/workspaces",
        headers=_dashboard_auth_headers(),
        json={
            "workspace_name": "Acme Finance Workspace",
            "client_name": "Acme Finance",
        },
    )

    assert create_response.status_code == 200
    created = create_response.json()
    assert created["name"] == "Acme Finance Workspace"
    assert created["client_name"] == "Acme Finance"
    assert created["status"] == "active"
    assert created["workspace_key_is_one_time"] is True
    assert isinstance(created["workspace_key"], str)
    assert created["workspace_key"]

    list_response = client.get(
        "/v1/dashboard/workspaces",
        headers=_dashboard_auth_headers(),
    )
    assert list_response.status_code == 200
    workspace_ids = {workspace["id"] for workspace in list_response.json()}
    assert created["id"] in workspace_ids

    created_workspace = repository.get_workspace(UUID(created["id"]))
    assert created_workspace is not None
    assert created_workspace.client_name == "Acme Finance"
    assert created_workspace.status == "active"


def _create_dashboard_api_key(
    client: TestClient,
    workspace_id: UUID,
    *,
    name: str = "Automation Key",
    headers: dict[str, str] | None = None,
) -> dict[str, object]:
    response = client.post(
        "/v1/dashboard/api-keys",
        headers=headers or _dashboard_auth_headers(),
        json={
            "workspace_id": str(workspace_id),
            "name": name,
        },
    )
    assert response.status_code == 200
    return response.json()


def test_authenticated_user_can_list_their_api_keys() -> None:
    workspace_id = uuid4()
    client, _ = _build_client(workspace_id)

    response = client.get(
        "/v1/dashboard/api-keys",
        headers=_dashboard_auth_headers(),
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["workspace_id"] == str(workspace_id)
    assert data[0]["status"] == "active"


def test_unauthenticated_user_cannot_list_api_keys() -> None:
    workspace_id = uuid4()
    client, _ = _build_client(workspace_id)

    response = client.get(
        "/v1/dashboard/api-keys",
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 401


def test_user_cannot_list_api_keys_for_other_users_workspace() -> None:
    workspace_id = uuid4()
    other_workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_workspace_key_hash(
        workspace_id=other_workspace_id,
        workspace_key_hash=hash_workspace_key("wsk_other_workspace", PEPPER),
        name="Other Workspace",
    )
    repository.add_api_key_hash(
        workspace_id=other_workspace_id,
        key_hash=hash_api_key("other-workspace-api-key", PEPPER),
    )
    repository.ensure_workspace_membership(
        workspace_id=other_workspace_id,
        user_id=UUID("bbbbbbbb-2222-2222-2222-222222222222"),
        role="owner",
    )

    response = client.get(
        "/v1/dashboard/api-keys",
        headers=_dashboard_auth_headers(),
    )

    assert response.status_code == 200
    data = response.json()
    assert all(item["workspace_id"] != str(other_workspace_id) for item in data)


def test_authenticated_user_can_create_api_key_for_own_workspace() -> None:
    workspace_id = uuid4()
    client, _ = _build_client(workspace_id)

    response = client.post(
        "/v1/dashboard/api-keys",
        headers=_dashboard_auth_headers(),
        json={
            "workspace_id": str(workspace_id),
            "name": "Production Runner",
        },
    )

    assert response.status_code == 200
    created = response.json()
    assert created["workspace_id"] == str(workspace_id)
    assert created["name"] == "Production Runner"
    assert created["status"] == "active"
    assert created["raw_api_key_is_one_time"] is True
    assert isinstance(created["raw_api_key"], str)
    assert created["raw_api_key"]


def test_user_cannot_create_api_key_for_another_workspace() -> None:
    workspace_id = uuid4()
    other_workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_workspace_key_hash(
        workspace_id=other_workspace_id,
        workspace_key_hash=hash_workspace_key("wsk_forbidden", PEPPER),
        name="Forbidden Workspace",
    )
    repository.ensure_workspace_membership(
        workspace_id=other_workspace_id,
        user_id=UUID("bbbbbbbb-2222-2222-2222-222222222222"),
        role="owner",
    )

    response = client.post(
        "/v1/dashboard/api-keys",
        headers=_dashboard_auth_headers(),
        json={
            "workspace_id": str(other_workspace_id),
            "name": "Forbidden Key",
        },
    )

    assert response.status_code == 404


def test_created_api_key_returns_raw_key_only_once() -> None:
    workspace_id = uuid4()
    client, _ = _build_client(workspace_id)

    created = _create_dashboard_api_key(client, workspace_id)
    assert isinstance(created["raw_api_key"], str)
    assert created["raw_api_key"]

    listing_response = client.get(
        "/v1/dashboard/api-keys",
        headers=_dashboard_auth_headers(),
    )
    assert listing_response.status_code == 200
    listed = listing_response.json()
    created_entry = next(item for item in listed if item["id"] == created["id"])
    assert "raw_api_key" not in created_entry


def test_stored_api_key_is_hashed_not_plaintext() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)

    created = _create_dashboard_api_key(client, workspace_id)
    raw_api_key = str(created["raw_api_key"])
    api_key_id = UUID(str(created["id"]))

    stored_hash = repository.get_workspace_api_key_hash(api_key_id)
    assert stored_hash is not None
    assert stored_hash != raw_api_key
    assert stored_hash == hash_api_key(raw_api_key, PEPPER)


def test_existing_api_key_listing_does_not_return_raw_key() -> None:
    workspace_id = uuid4()
    client, _ = _build_client(workspace_id)
    _ = _create_dashboard_api_key(client, workspace_id, name="No Raw Key in List")

    response = client.get(
        "/v1/dashboard/api-keys",
        headers=_dashboard_auth_headers(),
    )

    assert response.status_code == 200
    for item in response.json():
        assert "raw_api_key" not in item


def test_created_api_key_works_with_sdk_intercept() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="mark_invoice_paid",
        policy_type="always_allow",
    )

    created = _create_dashboard_api_key(client, workspace_id, name="SDK Runtime Key")
    raw_api_key = str(created["raw_api_key"])

    response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(api_key=raw_api_key),
        json={
            "action": "mark_invoice_paid",
            "payload": {"invoice_id": "INV-2001"},
            "idempotency_key": "sdk-created-key:INV-2001",
        },
    )

    assert response.status_code == 200
    assert response.json()["governance_status"] == "allowed"


def test_revoked_api_key_no_longer_works_with_sdk_intercept() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="mark_invoice_paid",
        policy_type="always_allow",
    )

    created = _create_dashboard_api_key(client, workspace_id, name="Revoke Me")
    raw_api_key = str(created["raw_api_key"])
    api_key_id = created["id"]

    revoke_response = client.post(
        f"/v1/dashboard/api-keys/{api_key_id}/revoke",
        headers=_dashboard_auth_headers(),
    )
    assert revoke_response.status_code == 200

    response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(api_key=raw_api_key),
        json={
            "action": "mark_invoice_paid",
            "payload": {"invoice_id": "INV-2002"},
            "idempotency_key": "sdk-revoked-key:INV-2002",
        },
    )

    assert response.status_code == 401


def test_user_can_revoke_own_workspace_api_key() -> None:
    workspace_id = uuid4()
    client, _ = _build_client(workspace_id)
    created = _create_dashboard_api_key(client, workspace_id, name="Owner Revoke Key")

    response = client.post(
        f"/v1/dashboard/api-keys/{created['id']}/revoke",
        headers=_dashboard_auth_headers(),
    )

    assert response.status_code == 200
    revoked = response.json()
    assert revoked["status"] == "revoked"
    assert revoked["revoked_at"] is not None


def test_user_cannot_revoke_another_workspaces_api_key() -> None:
    workspace_id = uuid4()
    other_workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_workspace_key_hash(
        workspace_id=other_workspace_id,
        workspace_key_hash=hash_workspace_key("wsk_other_revoke", PEPPER),
        name="Other Workspace",
    )
    repository.ensure_workspace_membership(
        workspace_id=other_workspace_id,
        user_id=UUID("bbbbbbbb-2222-2222-2222-222222222222"),
        role="owner",
    )
    other_api_key = repository.create_workspace_api_key(
        workspace_id=other_workspace_id,
        key_hash=hash_api_key("other-owner-key", PEPPER),
        key_prefix="daai_sk_other",
        name="Other Owner Key",
        created_by=UUID("bbbbbbbb-2222-2222-2222-222222222222"),
    )

    response = client.post(
        f"/v1/dashboard/api-keys/{other_api_key.id}/revoke",
        headers=_dashboard_auth_headers(),
    )

    assert response.status_code == 404


def test_revoking_already_revoked_key_is_deterministic_and_safe() -> None:
    workspace_id = uuid4()
    client, _ = _build_client(workspace_id)
    created = _create_dashboard_api_key(client, workspace_id, name="Deterministic Revoke")

    first = client.post(
        f"/v1/dashboard/api-keys/{created['id']}/revoke",
        headers=_dashboard_auth_headers(),
    )
    second = client.post(
        f"/v1/dashboard/api-keys/{created['id']}/revoke",
        headers=_dashboard_auth_headers(),
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["status"] == "revoked"
    assert second.json()["status"] == "revoked"
    assert first.json()["revoked_at"] == second.json()["revoked_at"]


def test_workspace_key_info_requires_auth() -> None:
    workspace_id = uuid4()
    client, _ = _build_client(workspace_id)

    response = client.get(
        f"/v1/dashboard/workspaces/{workspace_id}/key-info",
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 401


def test_user_cannot_access_workspace_key_info_for_another_workspace() -> None:
    workspace_id = uuid4()
    other_workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_workspace_key_hash(
        workspace_id=other_workspace_id,
        workspace_key_hash=hash_workspace_key("wsk_other_key_info", PEPPER),
        name="Other Workspace",
    )
    repository.ensure_workspace_membership(
        workspace_id=other_workspace_id,
        user_id=UUID("bbbbbbbb-2222-2222-2222-222222222222"),
        role="owner",
    )

    response = client.get(
        f"/v1/dashboard/workspaces/{other_workspace_id}/key-info",
        headers=_dashboard_auth_headers(),
    )

    assert response.status_code == 404


def test_workspace_key_regeneration_requires_auth_and_workspace_membership() -> None:
    workspace_id = uuid4()
    other_workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_workspace_key_hash(
        workspace_id=other_workspace_id,
        workspace_key_hash=hash_workspace_key("wsk_other_regen", PEPPER),
        name="Other Workspace",
    )
    repository.ensure_workspace_membership(
        workspace_id=other_workspace_id,
        user_id=UUID("bbbbbbbb-2222-2222-2222-222222222222"),
        role="owner",
    )

    unauthenticated_response = client.post(
        f"/v1/dashboard/workspaces/{workspace_id}/regenerate-key",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert unauthenticated_response.status_code == 401

    unauthorized_response = client.post(
        f"/v1/dashboard/workspaces/{other_workspace_id}/regenerate-key",
        headers=_dashboard_auth_headers(),
    )
    assert unauthorized_response.status_code == 404


def test_old_workspace_key_fails_and_new_workspace_key_works_after_regeneration() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="mark_invoice_paid",
        policy_type="always_allow",
    )

    key_info_response = client.get(
        f"/v1/dashboard/workspaces/{workspace_id}/key-info",
        headers=_dashboard_auth_headers(),
    )
    assert key_info_response.status_code == 200
    assert key_info_response.json()["full_key_available"] is False

    regenerate_response = client.post(
        f"/v1/dashboard/workspaces/{workspace_id}/regenerate-key",
        headers=_dashboard_auth_headers(),
    )
    assert regenerate_response.status_code == 200
    regenerated = regenerate_response.json()
    assert regenerated["workspace_key_is_one_time"] is True
    assert isinstance(regenerated["workspace_key"], str)
    assert regenerated["workspace_key"]

    old_key_response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(workspace_key=WORKSPACE_KEY),
        json={
            "action": "mark_invoice_paid",
            "payload": {"invoice_id": "INV-OLD-KEY"},
            "idempotency_key": "old-workspace-key",
        },
    )
    assert old_key_response.status_code == 401

    new_key_response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(workspace_key=str(regenerated["workspace_key"])),
        json={
            "action": "mark_invoice_paid",
            "payload": {"invoice_id": "INV-NEW-KEY"},
            "idempotency_key": "new-workspace-key",
        },
    )
    assert new_key_response.status_code == 200
    assert new_key_response.json()["governance_status"] == "allowed"


def test_sdk_endpoints_reject_supabase_dashboard_tokens() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="mark_invoice_paid",
        policy_type="always_allow",
    )

    response = client.post(
        "/v1/sdk/intercept",
        headers={
            "Authorization": _dashboard_auth_headers()["Authorization"],
            "X-DAAI-Workspace-Key": WORKSPACE_KEY,
        },
        json={
            "action": "mark_invoice_paid",
            "payload": {"invoice_id": "INV-REJECT-DASHBOARD-TOKEN"},
        },
    )

    assert response.status_code == 401


def test_dashboard_endpoints_reject_sdk_api_keys() -> None:
    workspace_id = uuid4()
    client, _ = _build_client(workspace_id)

    response = client.get(
        "/v1/dashboard/api-keys",
        headers={"Authorization": f"Bearer {API_KEY}"},
    )

    assert response.status_code == 401


def test_workspace_approval_settings_default_ttl_is_15() -> None:
    workspace_id = uuid4()
    client, _ = _build_client(workspace_id)

    response = client.get(
        f"/v1/dashboard/workspaces/{workspace_id}/approval-settings",
        headers=_dashboard_auth_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["approval_emails"] == []
    assert payload["approval_link_ttl_minutes"] == 15


def test_workspace_can_store_one_approval_email() -> None:
    workspace_id = uuid4()
    client, _ = _build_client(workspace_id)

    response = client.post(
        f"/v1/dashboard/workspaces/{workspace_id}/approval-settings",
        headers=_dashboard_auth_headers(),
        json={
            "approval_emails": ["approver1@example.com"],
            "approval_link_ttl_minutes": 15,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["approval_emails"] == ["approver1@example.com"]
    assert payload["approval_link_ttl_minutes"] == 15


def test_workspace_can_store_two_approval_emails() -> None:
    workspace_id = uuid4()
    client, _ = _build_client(workspace_id)

    response = client.post(
        f"/v1/dashboard/workspaces/{workspace_id}/approval-settings",
        headers=_dashboard_auth_headers(),
        json={
            "approval_emails": ["approver1@example.com", "approver2@example.com"],
            "approval_link_ttl_minutes": 30,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["approval_emails"] == [
        "approver1@example.com",
        "approver2@example.com",
    ]
    assert payload["approval_link_ttl_minutes"] == 30


def test_more_than_two_approval_emails_is_rejected() -> None:
    workspace_id = uuid4()
    client, _ = _build_client(workspace_id)

    response = client.post(
        f"/v1/dashboard/workspaces/{workspace_id}/approval-settings",
        headers=_dashboard_auth_headers(),
        json={
            "approval_emails": [
                "approver1@example.com",
                "approver2@example.com",
                "approver3@example.com",
            ],
            "approval_link_ttl_minutes": 15,
        },
    )

    assert response.status_code == 422


def test_invalid_approval_email_is_rejected() -> None:
    workspace_id = uuid4()
    client, _ = _build_client(workspace_id)

    response = client.post(
        f"/v1/dashboard/workspaces/{workspace_id}/approval-settings",
        headers=_dashboard_auth_headers(),
        json={
            "approval_emails": ["not-an-email"],
            "approval_link_ttl_minutes": 15,
        },
    )

    assert response.status_code == 422


def test_duplicate_approval_emails_are_rejected() -> None:
    workspace_id = uuid4()
    client, _ = _build_client(workspace_id)

    response = client.post(
        f"/v1/dashboard/workspaces/{workspace_id}/approval-settings",
        headers=_dashboard_auth_headers(),
        json={
            "approval_emails": ["dup@example.com", "dup@example.com"],
            "approval_link_ttl_minutes": 15,
        },
    )

    assert response.status_code == 422


def test_workspace_approval_settings_custom_ttl_is_saved() -> None:
    workspace_id = uuid4()
    client, _ = _build_client(workspace_id)

    update_response = client.post(
        f"/v1/dashboard/workspaces/{workspace_id}/approval-settings",
        headers=_dashboard_auth_headers(),
        json={
            "approval_emails": ["approver@example.com"],
            "approval_link_ttl_minutes": 240,
        },
    )
    assert update_response.status_code == 200

    fetch_response = client.get(
        f"/v1/dashboard/workspaces/{workspace_id}/approval-settings",
        headers=_dashboard_auth_headers(),
    )
    assert fetch_response.status_code == 200
    assert fetch_response.json()["approval_link_ttl_minutes"] == 240


def test_workspace_approval_ttl_below_minimum_is_rejected() -> None:
    workspace_id = uuid4()
    client, _ = _build_client(workspace_id)

    response = client.post(
        f"/v1/dashboard/workspaces/{workspace_id}/approval-settings",
        headers=_dashboard_auth_headers(),
        json={
            "approval_emails": ["approver@example.com"],
            "approval_link_ttl_minutes": 4,
        },
    )

    assert response.status_code == 422


def test_workspace_approval_ttl_above_maximum_is_rejected() -> None:
    workspace_id = uuid4()
    client, _ = _build_client(workspace_id)

    response = client.post(
        f"/v1/dashboard/workspaces/{workspace_id}/approval-settings",
        headers=_dashboard_auth_headers(),
        json={
            "approval_emails": ["approver@example.com"],
            "approval_link_ttl_minutes": 1441,
        },
    )

    assert response.status_code == 422


def test_non_member_cannot_update_approval_settings() -> None:
    workspace_id = uuid4()
    other_workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_workspace_key_hash(
        workspace_id=other_workspace_id,
        workspace_key_hash=hash_workspace_key("wsk_other_settings", PEPPER),
        name="Other Workspace",
    )
    repository.ensure_workspace_membership(
        workspace_id=other_workspace_id,
        user_id=UUID("bbbbbbbb-2222-2222-2222-222222222222"),
        role="owner",
    )

    response = client.post(
        f"/v1/dashboard/workspaces/{other_workspace_id}/approval-settings",
        headers=_dashboard_auth_headers(),
        json={
            "approval_emails": ["approver@example.com"],
            "approval_link_ttl_minutes": 15,
        },
    )

    assert response.status_code == 404


def test_workspace_member_can_list_pending_approvals() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    _ = _create_pending_run_via_intercept(
        client,
        repository,
        workspace_id,
        idempotency_key="pending-list-member",
    )

    response = client.get(
        f"/v1/dashboard/workspaces/{workspace_id}/pending-approvals",
        headers=_dashboard_auth_headers(),
    )

    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["action"] == "pay_vendor"
    assert "amount" in items[0]["payload_preview"]


def test_non_member_cannot_list_pending_approvals() -> None:
    workspace_id = uuid4()
    other_workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_workspace_key_hash(
        workspace_id=other_workspace_id,
        workspace_key_hash=hash_workspace_key("wsk_other_pending", PEPPER),
        name="Other Workspace",
    )
    repository.ensure_workspace_membership(
        workspace_id=other_workspace_id,
        user_id=UUID("bbbbbbbb-2222-2222-2222-222222222222"),
        role="owner",
    )

    response = client.get(
        f"/v1/dashboard/workspaces/{other_workspace_id}/pending-approvals",
        headers=_dashboard_auth_headers(),
    )

    assert response.status_code == 404


def test_dashboard_member_can_approve_pending_action_and_receipt_is_created() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    action_run_id = _create_pending_run_via_intercept(
        client,
        repository,
        workspace_id,
        idempotency_key="dashboard-approve",
    )

    response = client.post(
        f"/v1/dashboard/action-runs/{action_run_id}/approve",
        headers=_dashboard_auth_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["governance_status"] == "approved"
    assert payload["execution_status"] == "awaiting_execution_report"
    assert payload["executable"] is True
    assert payload["receipt"]["outcome"] == "approved"


def test_dashboard_member_can_reject_pending_action_and_receipt_is_created() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    action_run_id = _create_pending_run_via_intercept(
        client,
        repository,
        workspace_id,
        idempotency_key="dashboard-reject",
    )

    response = client.post(
        f"/v1/dashboard/action-runs/{action_run_id}/reject",
        headers=_dashboard_auth_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["governance_status"] == "rejected"
    assert payload["execution_status"] == "not_executed"
    assert payload["executable"] is False
    assert payload["receipt"]["outcome"] == "rejected"


def test_dashboard_member_can_block_pending_action_and_receipt_is_created() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    action_run_id = _create_pending_run_via_intercept(
        client,
        repository,
        workspace_id,
        idempotency_key="dashboard-block",
    )

    response = client.post(
        f"/v1/dashboard/action-runs/{action_run_id}/block",
        headers=_dashboard_auth_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["governance_status"] == "blocked"
    assert payload["execution_status"] == "not_executed"
    assert payload["executable"] is False
    assert payload["governance_reason"] == "manually_blocked_by_approver"
    assert payload["receipt"]["outcome"] == "blocked"


def test_non_member_cannot_approve_reject_or_block_pending_action() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    action_run_id = _create_pending_run_via_intercept(
        client,
        repository,
        workspace_id,
        idempotency_key="dashboard-non-member-decision",
    )

    other_user_headers = _dashboard_auth_headers(
        user_id=UUID("bbbbbbbb-2222-2222-2222-222222222222"),
        email="other@example.com",
    )

    approve_response = client.post(
        f"/v1/dashboard/action-runs/{action_run_id}/approve",
        headers=other_user_headers,
    )
    reject_response = client.post(
        f"/v1/dashboard/action-runs/{action_run_id}/reject",
        headers=other_user_headers,
    )
    block_response = client.post(
        f"/v1/dashboard/action-runs/{action_run_id}/block",
        headers=other_user_headers,
    )

    assert approve_response.status_code == 404
    assert reject_response.status_code == 404
    assert block_response.status_code == 404


def test_metrics_update_and_pending_item_disappears_after_dashboard_decision() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    action_run_id = _create_pending_run_via_intercept(
        client,
        repository,
        workspace_id,
        idempotency_key="dashboard-metrics-pending-update",
    )

    pending_before = client.get(
        f"/v1/dashboard/workspaces/{workspace_id}/pending-approvals",
        headers=_dashboard_auth_headers(),
    )
    assert pending_before.status_code == 200
    assert len(pending_before.json()) == 1

    metrics_before = client.get(
        f"/v1/dashboard/workspaces/{workspace_id}/metrics",
        headers=_dashboard_auth_headers(),
    )
    assert metrics_before.status_code == 200
    assert metrics_before.json()["pending_approval"] == 1
    assert metrics_before.json()["approved"] == 0

    decide_response = client.post(
        f"/v1/dashboard/action-runs/{action_run_id}/approve",
        headers=_dashboard_auth_headers(),
    )
    assert decide_response.status_code == 200

    pending_after = client.get(
        f"/v1/dashboard/workspaces/{workspace_id}/pending-approvals",
        headers=_dashboard_auth_headers(),
    )
    assert pending_after.status_code == 200
    assert pending_after.json() == []

    metrics_after = client.get(
        f"/v1/dashboard/workspaces/{workspace_id}/metrics",
        headers=_dashboard_auth_headers(),
    )
    assert metrics_after.status_code == 200
    assert metrics_after.json()["pending_approval"] == 0
    assert metrics_after.json()["approved"] == 1


def test_dashboard_decision_returns_conflict_for_finalized_action() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    action_run_id = _create_pending_run_via_intercept(
        client,
        repository,
        workspace_id,
        idempotency_key="dashboard-conflict-final",
    )

    first = client.post(
        f"/v1/dashboard/action-runs/{action_run_id}/approve",
        headers=_dashboard_auth_headers(),
    )
    second = client.post(
        f"/v1/dashboard/action-runs/{action_run_id}/reject",
        headers=_dashboard_auth_headers(),
    )

    assert first.status_code == 200
    assert second.status_code == 409
