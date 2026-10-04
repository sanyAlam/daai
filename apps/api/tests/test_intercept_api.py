from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.config import Settings
from app.hashing import hash_api_key, hash_approval_token, hash_workspace_key
from app.main import create_app
from fakes import InMemoryGovernanceRepository

API_KEY = "test-api-key"
WORKSPACE_KEY = "wsk_test_workspace"
PEPPER = "test-pepper"


@dataclass
class PendingApprovalLinkCapture:
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
    expires_in_text: str
    expires_at: datetime


class CaptureApprovalLinkNotifier:
    def __init__(self) -> None:
        self.sent_links: list[PendingApprovalLinkCapture] = []

    def notify_pending_approval(self, links: object) -> None:
        approve_url = getattr(links, "approve_url")
        reject_url = getattr(links, "reject_url")
        block_url = getattr(links, "block_url")
        self.sent_links.append(
            PendingApprovalLinkCapture(
                workspace_id=getattr(links, "workspace_id"),
                workspace_name=getattr(links, "workspace_name"),
                workspace_client_name=getattr(links, "workspace_client_name"),
                action_run_id=getattr(links, "action_run_id"),
                approval_emails=list(getattr(links, "approval_emails")),
                action=getattr(links, "action"),
                governance_reason=getattr(links, "governance_reason"),
                payload_summary=getattr(links, "payload_summary"),
                approve_url=approve_url,
                reject_url=reject_url,
                block_url=block_url,
                expires_in_text=getattr(links, "expires_in_text"),
                expires_at=getattr(links, "expires_at"),
            )
        )

    def latest_approve_token(self) -> str:
        return self.sent_links[-1].approve_url.rsplit("/", 1)[1]

    def latest_reject_token(self) -> str:
        return self.sent_links[-1].reject_url.rsplit("/", 1)[1]

    def latest_block_token(self) -> str:
        return self.sent_links[-1].block_url.rsplit("/", 1)[1]


def _auth_headers(
    api_key: str = API_KEY,
    workspace_key: str = WORKSPACE_KEY,
) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "X-DAAI-Workspace-Key": workspace_key,
    }


def _build_client(workspace_id: UUID) -> tuple[TestClient, InMemoryGovernanceRepository]:
    repository = InMemoryGovernanceRepository()
    notifier = CaptureApprovalLinkNotifier()
    repository.add_workspace_key_hash(
        workspace_id=workspace_id,
        workspace_key_hash=hash_workspace_key(WORKSPACE_KEY, PEPPER),
    )
    repository.add_api_key_hash(
        workspace_id=workspace_id,
        key_hash=hash_api_key(API_KEY, PEPPER),
    )

    app = create_app(
        repository=repository,
        settings=Settings(
            database_url=None,
            api_key_pepper=PEPPER,
            workspace_key_pepper=PEPPER,
            approval_token_pepper=PEPPER,
            public_base_url="http://testserver",
            dashboard_base_url="http://dashboard.test",
        ),
        approval_link_notifier=notifier,
    )
    repository.approval_notifier = notifier
    return TestClient(app), repository


def test_unknown_action_is_blocked_and_receipt_created() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)

    response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={
            "action": "wire_transfer",
            "payload": {"amount": 25000},
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["governance_status"] == "blocked"
    assert data["execution_status"] == "not_executed"
    assert data["governance_reason"] == "unknown_action"
    assert data["receipt"]["outcome"] == "blocked"
    assert repository.action_run_count == 1
    assert repository.receipt_count == 1


def test_always_allow_action_creates_allowed_receipt() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="mark_invoice_paid",
        policy_type="always_allow",
    )

    response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={
            "action": "mark_invoice_paid",
            "payload": {"invoice_id": "INV-1025"},
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["governance_status"] == "allowed"
    assert data["execution_status"] == "awaiting_execution_report"
    assert data["executable"] is True
    assert data["receipt"]["outcome"] == "allowed"
    assert repository.receipt_count == 1


def test_amount_policy_pending_approval_creates_no_receipt() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="pay_vendor",
        policy_type="require_approval_above_amount",
        policy_config={"threshold": 5000, "amount_field": "amount"},
    )

    response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={
            "action": "pay_vendor",
            "payload": {"amount": 9000},
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["governance_status"] == "pending_approval"
    assert data["execution_status"] == "not_executed"
    assert data["receipt"] is None
    assert repository.receipt_count == 0

    notifier = repository.approval_notifier
    assert len(notifier.sent_links) == 1
    assert notifier.sent_links[0].approve_url.startswith("http://dashboard.test/approve/")
    assert notifier.sent_links[0].reject_url.startswith("http://dashboard.test/reject/")
    assert notifier.sent_links[0].block_url.startswith("http://dashboard.test/block/")
    assert notifier.sent_links[0].expires_in_text == "15 minutes"


def test_public_approve_updates_run_and_creates_receipt() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="pay_vendor",
        policy_type="require_approval_above_amount",
        policy_config={"threshold": 1000, "amount_field": "amount"},
    )

    intercept_response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={"action": "pay_vendor", "payload": {"amount": 9000}},
    )
    assert intercept_response.status_code == 200
    action_run_id = intercept_response.json()["action_run_id"]

    approve_token = repository.approval_notifier.latest_approve_token()
    approve_response = client.post(f"/v1/public/approve/{approve_token}")
    assert approve_response.status_code == 200
    approve_data = approve_response.json()
    assert approve_data["action_run_id"] == action_run_id
    assert approve_data["governance_status"] == "approved"
    assert approve_data["execution_status"] == "awaiting_execution_report"
    assert approve_data["governance_reason"] == "approved_by_human"
    assert approve_data["executable"] is True
    assert approve_data["receipt"]["outcome"] == "approved"

    status_response = client.get(
        f"/v1/sdk/action-runs/{action_run_id}/status",
        headers=_auth_headers(),
    )
    assert status_response.status_code == 200
    status_data = status_response.json()
    assert status_data["governance_status"] == "approved"
    assert status_data["execution_status"] == "awaiting_execution_report"
    assert status_data["executable"] is True
    assert status_data["receipt"]["outcome"] == "approved"


def test_public_reject_updates_run_and_creates_receipt() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="pay_vendor",
        policy_type="always_require_approval",
    )

    intercept_response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={"action": "pay_vendor", "payload": {"amount": 50}},
    )
    assert intercept_response.status_code == 200
    action_run_id = intercept_response.json()["action_run_id"]

    reject_token = repository.approval_notifier.latest_reject_token()
    reject_response = client.post(f"/v1/public/reject/{reject_token}")
    assert reject_response.status_code == 200
    reject_data = reject_response.json()
    assert reject_data["action_run_id"] == action_run_id
    assert reject_data["governance_status"] == "rejected"
    assert reject_data["execution_status"] == "not_executed"
    assert reject_data["governance_reason"] == "rejected_by_human"
    assert reject_data["executable"] is False
    assert reject_data["receipt"]["outcome"] == "rejected"

    status_response = client.get(
        f"/v1/sdk/action-runs/{action_run_id}/status",
        headers=_auth_headers(),
    )
    assert status_response.status_code == 200
    status_data = status_response.json()
    assert status_data["governance_status"] == "rejected"
    assert status_data["executable"] is False
    assert status_data["receipt"]["outcome"] == "rejected"


def test_public_block_updates_run_and_creates_receipt() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="pay_vendor",
        policy_type="always_require_approval",
    )

    intercept_response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={"action": "pay_vendor", "payload": {"amount": 50}},
    )
    assert intercept_response.status_code == 200
    action_run_id = intercept_response.json()["action_run_id"]

    block_token = repository.approval_notifier.latest_block_token()
    block_response = client.post(f"/v1/public/block/{block_token}")
    assert block_response.status_code == 200
    block_data = block_response.json()
    assert block_data["action_run_id"] == action_run_id
    assert block_data["governance_status"] == "blocked"
    assert block_data["execution_status"] == "not_executed"
    assert block_data["governance_reason"] == "manually_blocked_by_approver"
    assert block_data["executable"] is False
    assert block_data["receipt"]["outcome"] == "blocked"

    status_response = client.get(
        f"/v1/sdk/action-runs/{action_run_id}/status",
        headers=_auth_headers(),
    )
    assert status_response.status_code == 200
    status_data = status_response.json()
    assert status_data["governance_status"] == "blocked"
    assert status_data["executable"] is False
    assert status_data["receipt"]["outcome"] == "blocked"


def test_public_approve_reject_invalid_token() -> None:
    workspace_id = uuid4()
    client, _ = _build_client(workspace_id)

    approve_response = client.post("/v1/public/approve/not-a-real-token")
    reject_response = client.post("/v1/public/reject/not-a-real-token")
    block_response = client.post("/v1/public/block/not-a-real-token")

    assert approve_response.status_code == 404
    assert reject_response.status_code == 404
    assert block_response.status_code == 404


def test_public_approve_token_expires() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="pay_vendor",
        policy_type="always_require_approval",
    )

    intercept_response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={"action": "pay_vendor", "payload": {"amount": 1}},
    )
    assert intercept_response.status_code == 200

    approve_token = repository.approval_notifier.latest_approve_token()
    approve_hash = hash_approval_token(approve_token, PEPPER)
    repository._decision_tokens_by_hash[approve_hash].expires_at = datetime.now(
        timezone.utc
    ) - timedelta(seconds=1)

    approve_response = client.post(f"/v1/public/approve/{approve_token}")
    assert approve_response.status_code == 404
    assert approve_response.json()["error"] == "invalid_or_expired_token"


def test_public_approve_token_cannot_be_reused() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="pay_vendor",
        policy_type="always_require_approval",
    )

    intercept_response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={"action": "pay_vendor", "payload": {"amount": 100}},
    )
    assert intercept_response.status_code == 200

    approve_token = repository.approval_notifier.latest_approve_token()
    first_response = client.post(f"/v1/public/approve/{approve_token}")
    second_response = client.post(f"/v1/public/approve/{approve_token}")

    assert first_response.status_code == 200
    assert second_response.status_code == 404
    assert second_response.json()["error"] == "invalid_or_expired_token"


def test_public_reject_after_approve_is_rejected_as_already_final() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="pay_vendor",
        policy_type="always_require_approval",
    )

    intercept_response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={"action": "pay_vendor", "payload": {"amount": 100}},
    )
    assert intercept_response.status_code == 200

    approve_token = repository.approval_notifier.latest_approve_token()
    reject_token = repository.approval_notifier.latest_reject_token()
    approve_response = client.post(f"/v1/public/approve/{approve_token}")
    reject_response = client.post(f"/v1/public/reject/{reject_token}")

    assert approve_response.status_code == 200
    assert reject_response.status_code == 404
    assert reject_response.json()["error"] == "invalid_or_expired_token"


def test_pending_approval_token_expiry_uses_workspace_default_ttl() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="pay_vendor",
        policy_type="always_require_approval",
    )

    response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={"action": "pay_vendor", "payload": {"amount": 9000}},
    )
    assert response.status_code == 200

    notifier = repository.approval_notifier
    assert notifier.sent_links[-1].expires_in_text == "15 minutes"
    approve_token = notifier.latest_approve_token()
    approve_hash = hash_approval_token(approve_token, PEPPER)
    token_record = repository._decision_tokens_by_hash[approve_hash]
    remaining_seconds = (token_record.expires_at - datetime.now(timezone.utc)).total_seconds()
    assert 12 * 60 <= remaining_seconds <= 15 * 60 + 10


def test_pending_approval_token_expiry_uses_workspace_custom_ttl() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="pay_vendor",
        policy_type="always_require_approval",
    )
    repository.update_workspace_approval_settings(
        workspace_id=workspace_id,
        approval_emails=["approver@example.com"],
        approval_link_ttl_minutes=60,
    )

    response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={"action": "pay_vendor", "payload": {"amount": 9000}},
    )
    assert response.status_code == 200

    notifier = repository.approval_notifier
    assert notifier.sent_links[-1].expires_in_text == "1 hour"
    assert notifier.sent_links[-1].approval_emails == ["approver@example.com"]

    approve_token = notifier.latest_approve_token()
    approve_hash = hash_approval_token(approve_token, PEPPER)
    token_record = repository._decision_tokens_by_hash[approve_hash]
    remaining_seconds = (token_record.expires_at - datetime.now(timezone.utc)).total_seconds()
    assert 55 * 60 <= remaining_seconds <= 60 * 60 + 10


def test_pending_approval_tokens_are_stored_hashed() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="pay_vendor",
        policy_type="always_require_approval",
    )

    response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={"action": "pay_vendor", "payload": {"amount": 9000}},
    )
    assert response.status_code == 200

    notifier = repository.approval_notifier
    approve_token = notifier.latest_approve_token()
    reject_token = notifier.latest_reject_token()
    block_token = notifier.latest_block_token()

    assert approve_token not in repository._decision_tokens_by_hash
    assert reject_token not in repository._decision_tokens_by_hash
    assert block_token not in repository._decision_tokens_by_hash
    assert hash_approval_token(approve_token, PEPPER) in repository._decision_tokens_by_hash
    assert hash_approval_token(reject_token, PEPPER) in repository._decision_tokens_by_hash
    assert hash_approval_token(block_token, PEPPER) in repository._decision_tokens_by_hash


def test_pending_approval_without_configured_email_does_not_crash() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="pay_vendor",
        policy_type="always_require_approval",
    )

    response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={"action": "pay_vendor", "payload": {"amount": 9000}},
    )

    assert response.status_code == 200
    assert response.json()["governance_status"] == "pending_approval"
    notifier = repository.approval_notifier
    assert notifier.sent_links[-1].approval_emails == []


def test_idempotency_returns_existing_run() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="mark_invoice_paid",
        policy_type="always_allow",
    )

    payload = {
        "action": "mark_invoice_paid",
        "payload": {"invoice_id": "INV-1025"},
        "idempotency_key": "invoice-reminder:INV-1025",
    }

    first = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json=payload,
    )
    second = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json=payload,
    )

    assert first.status_code == 200
    assert second.status_code == 200

    first_data = first.json()
    second_data = second.json()

    assert first_data["action_run_id"] == second_data["action_run_id"]
    assert second_data["idempotent_replay"] is True
    assert repository.action_run_count == 1
    assert repository.receipt_count == 1


def test_idempotency_conflict_rejects_different_payload_without_mutation() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="mark_invoice_paid",
        policy_type="always_allow",
    )

    first = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={
            "action": "mark_invoice_paid",
            "payload": {"invoice_id": "INV-1025", "amount": 100},
            "idempotency_key": "invoice-reminder:INV-1025",
        },
    )
    conflict = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={
            "action": "mark_invoice_paid",
            "payload": {"invoice_id": "INV-1025", "amount": 200},
            "idempotency_key": "invoice-reminder:INV-1025",
        },
    )

    assert first.status_code == 200
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == {
        "code": "idempotency_conflict",
        "message": "This idempotency key was already used with a different payload.",
    }
    runs = repository.list_action_runs(workspace_id=workspace_id)
    assert repository.action_run_count == 1
    assert repository.receipt_count == 1
    assert runs[0].id == UUID(first.json()["action_run_id"])
    assert runs[0].payload == {"invoice_id": "INV-1025", "amount": 100}


def test_idempotency_hash_uses_canonical_json_key_ordering() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="mark_invoice_paid",
        policy_type="always_allow",
    )

    first = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={
            "action": "mark_invoice_paid",
            "payload": {
                "invoice": {"id": "INV-1025", "amount": 100},
                "metadata": {"source": "admin_agent", "attempt": 1},
            },
            "idempotency_key": "invoice-reminder:canonical",
        },
    )
    second = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={
            "idempotency_key": "invoice-reminder:canonical",
            "payload": {
                "metadata": {"attempt": 1, "source": "admin_agent"},
                "invoice": {"amount": 100, "id": "INV-1025"},
            },
            "action": "mark_invoice_paid",
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["action_run_id"] == first.json()["action_run_id"]
    assert second.json()["idempotent_replay"] is True
    assert repository.action_run_count == 1


def test_different_idempotency_key_creates_new_run_normally() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="mark_invoice_paid",
        policy_type="always_allow",
    )

    first = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={
            "action": "mark_invoice_paid",
            "payload": {"invoice_id": "INV-1025"},
            "idempotency_key": "invoice-reminder:INV-1025:first",
        },
    )
    second = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={
            "action": "mark_invoice_paid",
            "payload": {"invoice_id": "INV-1025"},
            "idempotency_key": "invoice-reminder:INV-1025:second",
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["action_run_id"] != second.json()["action_run_id"]
    assert second.json()["idempotent_replay"] is False
    assert repository.action_run_count == 2
    assert repository.receipt_count == 2


def test_invalid_api_key_is_rejected() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="mark_invoice_paid",
        policy_type="always_allow",
    )

    response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(api_key="wrong-key"),
        json={
            "action": "mark_invoice_paid",
            "payload": {},
        },
    )

    assert response.status_code == 401


def test_action_run_status_endpoint_uses_locked_sdk_path() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="mark_invoice_paid",
        policy_type="always_allow",
    )

    intercept_response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={
            "action": "mark_invoice_paid",
            "payload": {"invoice_id": "INV-1025"},
        },
    )
    assert intercept_response.status_code == 200

    action_run_id = intercept_response.json()["action_run_id"]
    status_response = client.get(
        f"/v1/sdk/action-runs/{action_run_id}/status",
        headers=_auth_headers(),
    )
    assert status_response.status_code == 200
    data = status_response.json()
    assert data["action_run_id"] == action_run_id
    assert data["governance_status"] == "allowed"
    assert data["executable"] is True


def test_invalid_workspace_key_is_rejected() -> None:
    workspace_id = uuid4()
    client, _ = _build_client(workspace_id)

    response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(workspace_key="wsk_invalid"),
        json={
            "action": "pay_vendor",
            "payload": {"amount": 100},
        },
    )

    assert response.status_code == 401


def test_report_executed_endpoint_updates_execution_status() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="pay_vendor",
        policy_type="always_allow",
    )

    intercept_response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={
            "action": "pay_vendor",
            "payload": {"amount": 1000},
            "idempotency_key": "run-report-executed",
        },
    )
    assert intercept_response.status_code == 200
    action_run_id = intercept_response.json()["action_run_id"]

    report_response = client.post(
        f"/v1/sdk/action-runs/{action_run_id}/report-executed",
        headers=_auth_headers(),
        json={"execution_result": {"provider_id": "pay_123"}},
    )
    assert report_response.status_code == 200
    report_data = report_response.json()
    assert report_data["execution_status"] == "executed"
    assert report_data["idempotent_replay"] is False
    assert report_data["execution_error"] is None
    assert report_data["execution_reported_at"] is not None

    status_response = client.get(
        f"/v1/sdk/action-runs/{action_run_id}/status",
        headers=_auth_headers(),
    )
    assert status_response.status_code == 200
    assert status_response.json()["execution_status"] == "executed"


def test_report_failed_endpoint_updates_execution_status() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="pay_vendor",
        policy_type="always_allow",
    )

    intercept_response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={
            "action": "pay_vendor",
            "payload": {"amount": 1000},
            "idempotency_key": "run-report-failed",
        },
    )
    assert intercept_response.status_code == 200
    action_run_id = intercept_response.json()["action_run_id"]

    report_response = client.post(
        f"/v1/sdk/action-runs/{action_run_id}/report-failed",
        headers=_auth_headers(),
        json={
            "execution_error": "gateway_timeout",
            "execution_result": {"provider_code": "504"},
        },
    )
    assert report_response.status_code == 200
    report_data = report_response.json()
    assert report_data["execution_status"] == "failed"
    assert report_data["idempotent_replay"] is False
    assert report_data["execution_error"] == "gateway_timeout"
    assert report_data["execution_reported_at"] is not None

    status_response = client.get(
        f"/v1/sdk/action-runs/{action_run_id}/status",
        headers=_auth_headers(),
    )
    assert status_response.status_code == 200
    assert status_response.json()["execution_status"] == "failed"


def test_report_executed_is_idempotent_for_same_run() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="pay_vendor",
        policy_type="always_allow",
    )

    intercept_response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={"action": "pay_vendor", "payload": {"amount": 1000}},
    )
    assert intercept_response.status_code == 200
    action_run_id = intercept_response.json()["action_run_id"]

    first = client.post(
        f"/v1/sdk/action-runs/{action_run_id}/report-executed",
        headers=_auth_headers(),
        json={"execution_result": {"provider_id": "pay_124"}},
    )
    second = client.post(
        f"/v1/sdk/action-runs/{action_run_id}/report-executed",
        headers=_auth_headers(),
        json={"execution_result": {"provider_id": "pay_124"}},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["action_run_id"] == second.json()["action_run_id"]
    assert second.json()["idempotent_replay"] is True


def test_report_executed_conflicts_for_blocked_run() -> None:
    workspace_id = uuid4()
    client, _ = _build_client(workspace_id)

    intercept_response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={"action": "wire_transfer", "payload": {"amount": 9999}},
    )
    assert intercept_response.status_code == 200
    action_run_id = intercept_response.json()["action_run_id"]

    report_response = client.post(
        f"/v1/sdk/action-runs/{action_run_id}/report-executed",
        headers=_auth_headers(),
        json={"execution_result": {"provider_id": "should-not-run"}},
    )
    assert report_response.status_code == 409


def test_report_failed_conflicts_for_blocked_run() -> None:
    workspace_id = uuid4()
    client, _ = _build_client(workspace_id)

    intercept_response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={"action": "wire_transfer", "payload": {"amount": 9999}},
    )
    assert intercept_response.status_code == 200
    action_run_id = intercept_response.json()["action_run_id"]

    report_response = client.post(
        f"/v1/sdk/action-runs/{action_run_id}/report-failed",
        headers=_auth_headers(),
        json={
            "execution_error": "should-not-run",
            "execution_result": {"provider_code": "blocked"},
        },
    )
    assert report_response.status_code == 409


def test_report_executed_conflicts_for_pending_approval_run() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="pay_vendor",
        policy_type="require_approval_above_amount",
        policy_config={"threshold": 1000, "amount_field": "amount"},
    )

    intercept_response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={"action": "pay_vendor", "payload": {"amount": 9000}},
    )
    assert intercept_response.status_code == 200
    assert intercept_response.json()["governance_status"] == "pending_approval"
    action_run_id = intercept_response.json()["action_run_id"]

    report_response = client.post(
        f"/v1/sdk/action-runs/{action_run_id}/report-executed",
        headers=_auth_headers(),
        json={"execution_result": {"provider_id": "should-not-run"}},
    )
    assert report_response.status_code == 409


def test_report_failed_conflicts_for_pending_approval_run() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="pay_vendor",
        policy_type="require_approval_above_amount",
        policy_config={"threshold": 1000, "amount_field": "amount"},
    )

    intercept_response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={"action": "pay_vendor", "payload": {"amount": 9000}},
    )
    assert intercept_response.status_code == 200
    assert intercept_response.json()["governance_status"] == "pending_approval"
    action_run_id = intercept_response.json()["action_run_id"]

    report_response = client.post(
        f"/v1/sdk/action-runs/{action_run_id}/report-failed",
        headers=_auth_headers(),
        json={
            "execution_error": "should-not-run",
            "execution_result": {"provider_code": "blocked"},
        },
    )
    assert report_response.status_code == 409


def test_report_failed_is_idempotent_for_same_run() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="pay_vendor",
        policy_type="always_allow",
    )

    intercept_response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={"action": "pay_vendor", "payload": {"amount": 1000}},
    )
    assert intercept_response.status_code == 200
    action_run_id = intercept_response.json()["action_run_id"]

    first = client.post(
        f"/v1/sdk/action-runs/{action_run_id}/report-failed",
        headers=_auth_headers(),
        json={
            "execution_error": "gateway_timeout",
            "execution_result": {"provider_code": "504"},
        },
    )
    second = client.post(
        f"/v1/sdk/action-runs/{action_run_id}/report-failed",
        headers=_auth_headers(),
        json={
            "execution_error": "gateway_timeout",
            "execution_result": {"provider_code": "504"},
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["idempotent_replay"] is True


def test_report_failed_conflicts_after_executed_report() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="pay_vendor",
        policy_type="always_allow",
    )

    intercept_response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={"action": "pay_vendor", "payload": {"amount": 1000}},
    )
    assert intercept_response.status_code == 200
    action_run_id = intercept_response.json()["action_run_id"]

    report_executed = client.post(
        f"/v1/sdk/action-runs/{action_run_id}/report-executed",
        headers=_auth_headers(),
        json={"execution_result": {"provider_id": "pay_124"}},
    )
    assert report_executed.status_code == 200

    report_failed = client.post(
        f"/v1/sdk/action-runs/{action_run_id}/report-failed",
        headers=_auth_headers(),
        json={
            "execution_error": "gateway_timeout",
            "execution_result": {"provider_code": "504"},
        },
    )
    assert report_failed.status_code == 409


def test_report_executed_conflicts_after_failed_report() -> None:
    workspace_id = uuid4()
    client, repository = _build_client(workspace_id)
    repository.add_registered_action(
        workspace_id=workspace_id,
        action_name="pay_vendor",
        policy_type="always_allow",
    )

    intercept_response = client.post(
        "/v1/sdk/intercept",
        headers=_auth_headers(),
        json={"action": "pay_vendor", "payload": {"amount": 1000}},
    )
    assert intercept_response.status_code == 200
    action_run_id = intercept_response.json()["action_run_id"]

    report_failed = client.post(
        f"/v1/sdk/action-runs/{action_run_id}/report-failed",
        headers=_auth_headers(),
        json={
            "execution_error": "gateway_timeout",
            "execution_result": {"provider_code": "504"},
        },
    )
    assert report_failed.status_code == 200

    report_executed = client.post(
        f"/v1/sdk/action-runs/{action_run_id}/report-executed",
        headers=_auth_headers(),
        json={"execution_result": {"provider_id": "pay_124"}},
    )
    assert report_executed.status_code == 409
