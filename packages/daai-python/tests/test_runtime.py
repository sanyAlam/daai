from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from daai import (
    ActionRunStatusResponse,
    DaaiActionRunner,
    ExecutionReportResponse,
    ExecutionStatus,
    GovernanceStatus,
    InMemoryPendingStore,
    InterceptResponse,
    PendingAction,
    PendingActionManager,
    SQLitePendingStore,
)


class FakeDaaiClient:
    def __init__(self) -> None:
        self.intercept_responses: dict[str, InterceptResponse] = {}
        self.status_responses: dict[str, ActionRunStatusResponse] = {}
        self.intercept_calls: list[tuple[str, dict[str, object], str | None]] = []
        self.report_executed_calls: list[tuple[UUID, dict[str, object]]] = []
        self.report_failed_calls: list[tuple[UUID, str, dict[str, object]]] = []

    def intercept(
        self,
        action: str,
        payload: dict[str, object] | None = None,
        idempotency_key: str | None = None,
    ) -> InterceptResponse:
        self.intercept_calls.append((action, payload or {}, idempotency_key))
        return self.intercept_responses[action]

    def status(self, action_run_id: UUID | str) -> ActionRunStatusResponse:
        return self.status_responses[str(action_run_id)]

    def report_executed(
        self,
        action_run_id: UUID | str,
        execution_result: dict[str, object] | None = None,
    ) -> ExecutionReportResponse:
        run_id = UUID(str(action_run_id))
        payload = execution_result or {}
        self.report_executed_calls.append((run_id, payload))
        return ExecutionReportResponse(
            action_run_id=run_id,
            execution_status=ExecutionStatus.EXECUTED,
            execution_error=None,
            execution_reported_at=datetime.now(timezone.utc),
            idempotent_replay=False,
        )

    def report_failed(
        self,
        action_run_id: UUID | str,
        execution_error: str,
        execution_result: dict[str, object] | None = None,
    ) -> ExecutionReportResponse:
        run_id = UUID(str(action_run_id))
        payload = execution_result or {}
        self.report_failed_calls.append((run_id, execution_error, payload))
        return ExecutionReportResponse(
            action_run_id=run_id,
            execution_status=ExecutionStatus.FAILED,
            execution_error=execution_error,
            execution_reported_at=datetime.now(timezone.utc),
            idempotent_replay=False,
        )


def test_pending_action_stored_on_pending_approval() -> None:
    run_id = uuid4()
    client = FakeDaaiClient()
    client.intercept_responses["pay_vendor"] = _build_intercept_response(
        run_id=run_id,
        governance_status=GovernanceStatus.PENDING_APPROVAL,
        execution_status=ExecutionStatus.NOT_EXECUTED,
        executable=False,
    )
    store = InMemoryPendingStore()
    manager = PendingActionManager(client=client, pending_store=store)

    ticket = manager.propose(
        action="pay_vendor",
        payload={"amount": 9000},
        idempotency_key="invoice-reminder:INV-1025",
    )

    pending = store.list_pending()
    assert len(pending) == 1
    assert pending[0].action_run_id == run_id
    assert pending[0].action == "pay_vendor"
    assert pending[0].payload == {"amount": 9000}
    assert ticket.stored_for_later is True
    assert client.intercept_calls == [
        ("pay_vendor", {"amount": 9000}, "invoice-reminder:INV-1025")
    ]


def test_sqlite_store_persists_pending_actions_between_instances(tmp_path: Path) -> None:
    run_id = uuid4()
    db_path = tmp_path / "pending.sqlite3"

    client = FakeDaaiClient()
    client.intercept_responses["pay_vendor"] = _build_intercept_response(
        run_id=run_id,
        governance_status=GovernanceStatus.PENDING_APPROVAL,
        execution_status=ExecutionStatus.NOT_EXECUTED,
        executable=False,
    )

    first_store = SQLitePendingStore(db_path=db_path)
    manager = PendingActionManager(client=client, pending_store=first_store)
    manager.propose(action="pay_vendor", payload={"amount": 12.34})

    second_store = SQLitePendingStore(db_path=db_path)
    pending = second_store.list_pending()
    assert len(pending) == 1
    assert pending[0].action_run_id == run_id
    assert pending[0].payload == {"amount": 12.34}


def test_approved_action_executes_when_runner_polls_executable_status() -> None:
    run_id = uuid4()
    client = FakeDaaiClient()
    client.status_responses[str(run_id)] = _build_status_response(
        run_id=run_id,
        action="mark_invoice_paid",
        governance_status=GovernanceStatus.APPROVED,
        execution_status=ExecutionStatus.NOT_EXECUTED,
        executable=True,
    )

    store = InMemoryPendingStore()
    store.put(
        PendingAction(
            action_run_id=run_id,
            action="mark_invoice_paid",
            payload={"invoice_id": "INV-1025"},
            idempotency_key="invoice-reminder:INV-1025",
            created_at=datetime.now(timezone.utc),
        )
    )

    executed_payloads: list[dict[str, object]] = []

    def mark_invoice_paid_executor(payload: dict[str, object]) -> dict[str, object]:
        executed_payloads.append(payload)
        return {"provider_id": "pay_123"}

    runner = DaaiActionRunner(client=client, pending_store=store)
    runner.when_executable(action="mark_invoice_paid", run=mark_invoice_paid_executor)

    executed_count = runner.run_pending_once()

    assert executed_count == 1
    assert executed_payloads == [{"invoice_id": "INV-1025"}]
    assert client.report_executed_calls == [(run_id, {"provider_id": "pay_123"})]
    assert client.report_failed_calls == []
    assert store.list_pending() == []


def test_rejected_action_is_never_executed() -> None:
    run_id = uuid4()
    client = FakeDaaiClient()
    client.status_responses[str(run_id)] = _build_status_response(
        run_id=run_id,
        action="pay_vendor",
        governance_status=GovernanceStatus.REJECTED,
        execution_status=ExecutionStatus.NOT_EXECUTED,
        executable=False,
    )

    store = InMemoryPendingStore()
    store.put(
        PendingAction(
            action_run_id=run_id,
            action="pay_vendor",
            payload={"amount": 9000},
            idempotency_key="invoice-reminder:INV-1025",
            created_at=datetime.now(timezone.utc),
        )
    )

    called = False

    def executor(_: dict[str, object]) -> dict[str, object]:
        nonlocal called
        called = True
        return {}

    runner = DaaiActionRunner(client=client, pending_store=store)
    runner.when_executable(action="pay_vendor", run=executor)

    executed_count = runner.run_pending_once()

    assert executed_count == 0
    assert called is False
    assert client.report_executed_calls == []
    assert client.report_failed_calls == []
    assert store.list_pending() == []


def test_blocked_action_is_never_executed() -> None:
    run_id = uuid4()
    client = FakeDaaiClient()
    client.status_responses[str(run_id)] = _build_status_response(
        run_id=run_id,
        action="pay_vendor",
        governance_status=GovernanceStatus.BLOCKED,
        execution_status=ExecutionStatus.NOT_EXECUTED,
        executable=False,
    )

    store = InMemoryPendingStore()
    store.put(
        PendingAction(
            action_run_id=run_id,
            action="pay_vendor",
            payload={"amount": 9000},
            idempotency_key="invoice-reminder:INV-1025",
            created_at=datetime.now(timezone.utc),
        )
    )

    called = False

    def executor(_: dict[str, object]) -> dict[str, object]:
        nonlocal called
        called = True
        return {}

    runner = DaaiActionRunner(client=client, pending_store=store)
    runner.when_executable(action="pay_vendor", run=executor)

    executed_count = runner.run_pending_once()

    assert executed_count == 0
    assert called is False
    assert client.report_executed_calls == []
    assert client.report_failed_calls == []
    assert store.list_pending() == []


def test_executor_success_calls_report_executed() -> None:
    run_id = uuid4()
    client = FakeDaaiClient()
    client.status_responses[str(run_id)] = _build_status_response(
        run_id=run_id,
        action="pay_vendor",
        governance_status=GovernanceStatus.APPROVED,
        execution_status=ExecutionStatus.NOT_EXECUTED,
        executable=True,
    )
    store = InMemoryPendingStore()
    store.put(
        PendingAction(
            action_run_id=run_id,
            action="pay_vendor",
            payload={"amount": 10},
            idempotency_key=None,
            created_at=datetime.now(timezone.utc),
        )
    )

    runner = DaaiActionRunner(client=client, pending_store=store)
    runner.when_executable(action="pay_vendor", run=lambda payload: payload)
    runner.run_pending_once()

    assert client.report_executed_calls == [(run_id, {"amount": 10})]
    assert client.report_failed_calls == []


def test_executor_failure_calls_report_failed() -> None:
    run_id = uuid4()
    client = FakeDaaiClient()
    client.status_responses[str(run_id)] = _build_status_response(
        run_id=run_id,
        action="pay_vendor",
        governance_status=GovernanceStatus.APPROVED,
        execution_status=ExecutionStatus.NOT_EXECUTED,
        executable=True,
    )
    store = InMemoryPendingStore()
    store.put(
        PendingAction(
            action_run_id=run_id,
            action="pay_vendor",
            payload={"amount": 10},
            idempotency_key=None,
            created_at=datetime.now(timezone.utc),
        )
    )

    def failing_executor(_: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("gateway_timeout")

    runner = DaaiActionRunner(client=client, pending_store=store)
    runner.when_executable(action="pay_vendor", run=failing_executor)
    runner.run_pending_once()

    assert client.report_executed_calls == []
    assert len(client.report_failed_calls) == 1
    report_failed_call = client.report_failed_calls[0]
    assert report_failed_call[0] == run_id
    assert "RuntimeError: gateway_timeout" == report_failed_call[1]


def _build_intercept_response(
    run_id: UUID,
    governance_status: GovernanceStatus,
    execution_status: ExecutionStatus,
    executable: bool,
) -> InterceptResponse:
    return InterceptResponse(
        action_run_id=run_id,
        governance_status=governance_status,
        execution_status=execution_status,
        governance_reason="policy_decision",
        executable=executable,
        idempotent_replay=False,
        receipt=None,
    )


def _build_status_response(
    run_id: UUID,
    action: str,
    governance_status: GovernanceStatus,
    execution_status: ExecutionStatus,
    executable: bool,
) -> ActionRunStatusResponse:
    now = datetime.now(timezone.utc)
    return ActionRunStatusResponse(
        action_run_id=run_id,
        action=action,
        governance_status=governance_status,
        execution_status=execution_status,
        governance_reason="policy_decision",
        executable=executable,
        receipt=None,
        created_at=now,
        decided_at=now,
    )
