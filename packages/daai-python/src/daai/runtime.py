from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol
from uuid import UUID

from daai.client import DaaiClient
from daai.models import ExecutionStatus, GovernanceStatus


@dataclass(frozen=True)
class PendingAction:
    action_run_id: UUID
    action: str
    payload: dict[str, Any]
    idempotency_key: str | None
    created_at: datetime


@dataclass(frozen=True)
class ActionTicket:
    action_run_id: UUID
    action: str
    payload: dict[str, Any]
    idempotency_key: str | None
    governance_status: GovernanceStatus
    execution_status: ExecutionStatus
    governance_reason: str
    executable: bool
    idempotent_replay: bool
    stored_for_later: bool


class PendingStore(Protocol):
    def put(self, pending_action: PendingAction) -> None: ...

    def list_pending(self) -> list[PendingAction]: ...

    def remove(self, action_run_id: UUID | str) -> None: ...


class InMemoryPendingStore:
    def __init__(self) -> None:
        self._pending: dict[str, PendingAction] = {}

    def put(self, pending_action: PendingAction) -> None:
        self._pending[str(pending_action.action_run_id)] = pending_action

    def list_pending(self) -> list[PendingAction]:
        return sorted(
            self._pending.values(),
            key=lambda item: item.created_at,
        )

    def remove(self, action_run_id: UUID | str) -> None:
        self._pending.pop(str(action_run_id), None)


class SQLitePendingStore:
    def __init__(self, db_path: str | Path = "daai_pending_actions.sqlite3") -> None:
        self._db_path = str(db_path)
        self._ensure_schema()

    def put(self, pending_action: PendingAction) -> None:
        payload_json = json.dumps(pending_action.payload, separators=(",", ":"))

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO pending_actions (
                    action_run_id,
                    action,
                    payload_json,
                    idempotency_key,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(action_run_id) DO UPDATE SET
                    action = excluded.action,
                    payload_json = excluded.payload_json,
                    idempotency_key = excluded.idempotency_key,
                    created_at = excluded.created_at
                """,
                (
                    str(pending_action.action_run_id),
                    pending_action.action,
                    payload_json,
                    pending_action.idempotency_key,
                    pending_action.created_at.isoformat(),
                ),
            )
            conn.commit()

    def list_pending(self) -> list[PendingAction]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT action_run_id, action, payload_json, idempotency_key, created_at
                FROM pending_actions
                ORDER BY created_at ASC
                """
            ).fetchall()

        pending: list[PendingAction] = []
        for row in rows:
            pending.append(
                PendingAction(
                    action_run_id=UUID(row["action_run_id"]),
                    action=row["action"],
                    payload=_parse_payload_json(row["payload_json"]),
                    idempotency_key=row["idempotency_key"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
            )

        return pending

    def remove(self, action_run_id: UUID | str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM pending_actions WHERE action_run_id = ?",
                (str(action_run_id),),
            )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pending_actions (
                    action_run_id TEXT PRIMARY KEY,
                    action TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    idempotency_key TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()


class PendingActionManager:
    def __init__(self, client: DaaiClient, pending_store: PendingStore) -> None:
        self._client = client
        self._pending_store = pending_store

    def propose(
        self,
        action: str,
        payload: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> ActionTicket:
        action_payload = payload or {}
        response = self._client.intercept(
            action=action,
            payload=action_payload,
            idempotency_key=idempotency_key,
        )

        stored_for_later = response.governance_status == GovernanceStatus.PENDING_APPROVAL
        if stored_for_later:
            self._pending_store.put(
                PendingAction(
                    action_run_id=response.action_run_id,
                    action=action,
                    payload=action_payload,
                    idempotency_key=idempotency_key,
                    created_at=datetime.now(timezone.utc),
                )
            )

        return ActionTicket(
            action_run_id=response.action_run_id,
            action=action,
            payload=action_payload,
            idempotency_key=idempotency_key,
            governance_status=response.governance_status,
            execution_status=response.execution_status,
            governance_reason=response.governance_reason,
            executable=response.executable,
            idempotent_replay=response.idempotent_replay,
            stored_for_later=stored_for_later,
        )


ActionExecutor = Callable[[dict[str, Any]], Any]


class DaaiActionRunner:
    def __init__(self, client: DaaiClient, pending_store: PendingStore) -> None:
        self._client = client
        self._pending_store = pending_store
        self._executors: dict[str, ActionExecutor] = {}

    def when_executable(
        self,
        action: str,
        run: ActionExecutor,
    ) -> None:
        self._executors[action] = run

    def run_pending_once(self) -> int:
        executed_count = 0
        pending_actions = self._pending_store.list_pending()

        for pending in pending_actions:
            status = self._client.status(pending.action_run_id)

            if status.governance_status in (
                GovernanceStatus.REJECTED,
                GovernanceStatus.BLOCKED,
            ):
                self._pending_store.remove(pending.action_run_id)
                continue

            if not status.executable:
                continue

            if status.execution_status in (
                ExecutionStatus.EXECUTED,
                ExecutionStatus.FAILED,
            ):
                self._pending_store.remove(pending.action_run_id)
                continue

            executor = self._executors.get(pending.action)
            if executor is None:
                continue

            try:
                result = executor(pending.payload)
                execution_result = _normalize_execution_result(result)
                self._client.report_executed(
                    action_run_id=pending.action_run_id,
                    execution_result=execution_result,
                )
                executed_count += 1
            except Exception as exc:
                self._client.report_failed(
                    action_run_id=pending.action_run_id,
                    execution_error=f"{type(exc).__name__}: {exc}",
                )
            finally:
                self._pending_store.remove(pending.action_run_id)

        return executed_count


def _parse_payload_json(value: str) -> dict[str, Any]:
    parsed = json.loads(value)
    if isinstance(parsed, dict):
        return parsed
    raise ValueError("pending payload must deserialize to an object")


def _normalize_execution_result(result: Any) -> dict[str, Any]:
    if result is None:
        return {}
    if isinstance(result, dict):
        return result
    return {"result": result}
