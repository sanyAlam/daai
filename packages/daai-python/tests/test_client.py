from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID, uuid4

import httpx
import pytest

from daai import (
    DaaiApiError,
    DaaiClient,
    DaaiConflictError,
    DaaiNotFoundError,
    DaaiUnauthorizedError,
    DaaiValidationError,
    ExecutionStatus,
    GovernanceStatus,
)
from daai.errors import DaaiError


def _build_client(handler: httpx.MockTransport) -> DaaiClient:
    http_client = httpx.Client(
        base_url="https://api.example.com",
        transport=handler,
    )
    return DaaiClient(
        base_url="https://api.example.com",
        api_key="test-api-key",
        workspace_key="wsk_test_workspace",
        http_client=http_client,
    )


@pytest.mark.parametrize("flag", [None, "false", "true", 1, False])
def test_status_requires_explicit_boolean_execution_authority(flag: object) -> None:
    run_id = str(uuid4())
    body = {
        "action_run_id": run_id, "action": "send_invoice_reminder",
        "governance_status": "approved", "execution_status": "awaiting_execution_report",
        "governance_reason": "approved_by_human", "receipt": None,
        "created_at": "2026-05-08T12:20:30Z", "decided_at": None,
    }
    if flag is not None:
        body["executable"] = flag
    client = _build_client(httpx.MockTransport(lambda _: httpx.Response(200, json=body)))
    assert client.status(run_id).executable is False


def _assert_auth_headers(request: httpx.Request) -> None:
    assert request.headers["Authorization"] == "Bearer test-api-key"
    assert request.headers["X-DAAI-Workspace-Key"] == "wsk_test_workspace"


def test_intercept_sends_expected_contract_and_parses_response() -> None:
    run_id = str(uuid4())
    receipt_id = str(uuid4())

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/sdk/intercept"
        _assert_auth_headers(request)

        body = json.loads(request.content.decode("utf-8"))
        assert body == {
            "action": "pay_vendor",
            "payload": {"amount": 9000},
            "idempotency_key": "invoice-reminder:INV-1025",
        }

        return httpx.Response(
            status_code=200,
            json={
                "action_run_id": run_id,
                "governance_status": "pending_approval",
                "execution_status": "not_executed",
                "governance_reason": "approval_required_above_threshold",
                "executable": False,
                "idempotent_replay": True,
                "receipt": {
                    "id": receipt_id,
                    "outcome": "pending_approval",
                    "reason": "approval_required_above_threshold",
                    "policy_type": "require_approval_above_amount",
                    "policy_snapshot": {"threshold": 5000},
                    "created_at": "2026-05-08T12:20:30Z",
                },
            },
        )

    client = _build_client(httpx.MockTransport(handler))

    response = client.intercept(
        action="pay_vendor",
        payload={"amount": 9000},
        idempotency_key="invoice-reminder:INV-1025",
    )

    assert response.action_run_id == UUID(run_id)
    assert response.governance_status == GovernanceStatus.PENDING_APPROVAL
    assert response.execution_status == ExecutionStatus.NOT_EXECUTED
    assert response.executable is False
    assert response.idempotent_replay is True
    assert response.receipt is not None
    assert response.receipt.id == UUID(receipt_id)
    assert response.receipt.created_at == datetime.fromisoformat(
        "2026-05-08T12:20:30+00:00"
    )


def test_intercept_defaults_payload_and_omits_idempotency_key() -> None:
    run_id = str(uuid4())

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        assert body == {
            "action": "mark_invoice_paid",
            "payload": {},
        }
        return httpx.Response(
            status_code=200,
            json={
                "action_run_id": run_id,
                "governance_status": "allowed",
                "execution_status": "awaiting_execution_report",
                "governance_reason": "always_allow",
                "executable": True,
                "idempotent_replay": False,
                "receipt": None,
            },
        )

    client = _build_client(httpx.MockTransport(handler))
    response = client.intercept(action="mark_invoice_paid")
    assert response.action_run_id == UUID(run_id)
    assert response.governance_status == GovernanceStatus.ALLOWED
    assert response.execution_status == ExecutionStatus.AWAITING_EXECUTION_REPORT


def test_status_reads_locked_endpoint_and_parses_typed_fields() -> None:
    run_id = str(uuid4())

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == f"/v1/sdk/action-runs/{run_id}/status"
        _assert_auth_headers(request)
        return httpx.Response(
            status_code=200,
            json={
                "action_run_id": run_id,
                "action": "mark_invoice_paid",
                "governance_status": "allowed",
                "execution_status": "executed",
                "governance_reason": "always_allow",
                "executable": True,
                "receipt": None,
                "created_at": "2026-05-08T12:00:00+00:00",
                "decided_at": "2026-05-08T12:00:01+00:00",
            },
        )

    client = _build_client(httpx.MockTransport(handler))
    response = client.status(action_run_id=run_id)
    assert response.action_run_id == UUID(run_id)
    assert response.execution_status == ExecutionStatus.EXECUTED
    assert response.executable is True
    assert response.created_at == datetime.fromisoformat("2026-05-08T12:00:00+00:00")
    assert response.decided_at == datetime.fromisoformat("2026-05-08T12:00:01+00:00")


def test_report_executed_sends_expected_payload() -> None:
    run_id = str(uuid4())

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == f"/v1/sdk/action-runs/{run_id}/report-executed"
        _assert_auth_headers(request)
        body = json.loads(request.content.decode("utf-8"))
        assert body == {"execution_result": {"provider_id": "pay_123"}}
        return httpx.Response(
            status_code=200,
            json={
                "action_run_id": run_id,
                "execution_status": "executed",
                "execution_error": None,
                "execution_reported_at": "2026-05-08T12:21:30+00:00",
                "idempotent_replay": False,
            },
        )

    client = _build_client(httpx.MockTransport(handler))
    response = client.report_executed(
        action_run_id=run_id,
        execution_result={"provider_id": "pay_123"},
    )

    assert response.execution_status == ExecutionStatus.EXECUTED
    assert response.execution_error is None
    assert response.idempotent_replay is False


def test_report_failed_sends_expected_payload() -> None:
    run_id = str(uuid4())

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == f"/v1/sdk/action-runs/{run_id}/report-failed"
        _assert_auth_headers(request)
        body = json.loads(request.content.decode("utf-8"))
        assert body == {
            "execution_error": "gateway_timeout",
            "execution_result": {"provider_code": "504"},
        }
        return httpx.Response(
            status_code=200,
            json={
                "action_run_id": run_id,
                "execution_status": "failed",
                "execution_error": "gateway_timeout",
                "execution_reported_at": "2026-05-08T12:21:30+00:00",
                "idempotent_replay": True,
            },
        )

    client = _build_client(httpx.MockTransport(handler))
    response = client.report_failed(
        action_run_id=run_id,
        execution_error="gateway_timeout",
        execution_result={"provider_code": "504"},
    )

    assert response.execution_status == ExecutionStatus.FAILED
    assert response.execution_error == "gateway_timeout"
    assert response.idempotent_replay is True


@pytest.mark.parametrize(
    ("status_code", "error_cls"),
    [
        (401, DaaiUnauthorizedError),
        (404, DaaiNotFoundError),
        (409, DaaiConflictError),
        (422, DaaiValidationError),
        (500, DaaiApiError),
    ],
)
def test_errors_are_mapped_to_explicit_exception_types(
    status_code: int,
    error_cls: type[DaaiError],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=status_code,
            json={"detail": "boom"},
        )

    client = _build_client(httpx.MockTransport(handler))

    with pytest.raises(error_cls) as exc_info:
        client.intercept(action="pay_vendor", payload={"amount": 1})

    exc = exc_info.value
    assert exc.status_code == status_code
    assert exc.body == {"detail": "boom"}
    assert "boom" in exc.message


def test_structured_conflict_error_uses_detail_message() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=409,
            json={
                "detail": {
                    "code": "idempotency_conflict",
                    "message": "This idempotency key was already used with a different payload.",
                },
            },
        )

    client = _build_client(httpx.MockTransport(handler))

    with pytest.raises(DaaiConflictError) as exc_info:
        client.intercept(action="pay_vendor", payload={"amount": 1})

    exc = exc_info.value
    assert exc.message == "This idempotency key was already used with a different payload."
    assert exc.body["detail"]["code"] == "idempotency_conflict"


def test_transport_errors_raise_daai_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("network unavailable", request=request)

    client = _build_client(httpx.MockTransport(handler))

    with pytest.raises(DaaiError):
        client.status(action_run_id=uuid4())
