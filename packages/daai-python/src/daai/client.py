from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import httpx

from daai.errors import (
    DaaiApiError,
    DaaiConflictError,
    DaaiError,
    DaaiNotFoundError,
    DaaiUnauthorizedError,
    DaaiValidationError,
)
from daai.models import (
    ActionRunStatusResponse,
    ExecutionReportResponse,
    ExecutionStatus,
    GovernanceReceipt,
    GovernanceStatus,
    InterceptResponse,
)


class DaaiClient:
    """Low-level DAAI API client for cooperative action governance."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        workspace_key: str,
        timeout_seconds: float = 10.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._workspace_key = workspace_key
        self._owns_client = http_client is None

        if http_client is not None:
            self._http = http_client
            return

        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
        )

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def __enter__(self) -> "DaaiClient":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def intercept(
        self,
        action: str,
        payload: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> InterceptResponse:
        body: dict[str, Any] = {
            "action": action,
            "payload": payload or {},
        }
        if idempotency_key is not None:
            body["idempotency_key"] = idempotency_key

        data = self._request("POST", "/v1/sdk/intercept", json=body)
        return InterceptResponse(
            action_run_id=UUID(data["action_run_id"]),
            governance_status=GovernanceStatus(data["governance_status"]),
            execution_status=ExecutionStatus(data["execution_status"]),
            governance_reason=data["governance_reason"],
            executable=data.get("executable") is True,
            idempotent_replay=bool(data["idempotent_replay"]),
            receipt=_parse_receipt(data.get("receipt")),
        )

    def status(self, action_run_id: UUID | str) -> ActionRunStatusResponse:
        run_id = str(action_run_id)
        data = self._request("GET", f"/v1/sdk/action-runs/{run_id}/status")
        governance_status = GovernanceStatus(data["governance_status"])
        executable = data.get("executable") is True

        return ActionRunStatusResponse(
            action_run_id=UUID(data["action_run_id"]),
            action=data["action"],
            governance_status=governance_status,
            execution_status=ExecutionStatus(data["execution_status"]),
            governance_reason=data["governance_reason"],
            executable=bool(executable),
            receipt=_parse_receipt(data.get("receipt")),
            created_at=_parse_datetime(data["created_at"]),
            decided_at=_parse_datetime(data["decided_at"])
            if data.get("decided_at") is not None
            else None,
        )

    def report_executed(
        self,
        action_run_id: UUID | str,
        execution_result: dict[str, Any] | None = None,
    ) -> ExecutionReportResponse:
        run_id = str(action_run_id)
        data = self._request(
            "POST",
            f"/v1/sdk/action-runs/{run_id}/report-executed",
            json={"execution_result": execution_result or {}},
        )
        return _parse_execution_report(data)

    def report_failed(
        self,
        action_run_id: UUID | str,
        execution_error: str,
        execution_result: dict[str, Any] | None = None,
    ) -> ExecutionReportResponse:
        run_id = str(action_run_id)
        data = self._request(
            "POST",
            f"/v1/sdk/action-runs/{run_id}/report-failed",
            json={
                "execution_error": execution_error,
                "execution_result": execution_result or {},
            },
        )
        return _parse_execution_report(data)

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        headers = kwargs.pop("headers", {})
        headers.update(
            {
                "Authorization": f"Bearer {self._api_key}",
                "X-DAAI-Workspace-Key": self._workspace_key,
            }
        )

        try:
            response = self._http.request(method=method, url=path, headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise DaaiError(message=str(exc)) from exc

        if response.is_success:
            data = response.json()
            if not isinstance(data, dict):
                raise DaaiApiError(
                    message="unexpected response payload",
                    status_code=response.status_code,
                    body=data,
                )
            return data

        self._raise_api_error(response)
        raise RuntimeError("unreachable")

    def _raise_api_error(self, response: httpx.Response) -> None:
        body: Any
        detail: str

        try:
            body = response.json()
        except ValueError:
            body = response.text

        if isinstance(body, dict):
            raw_detail = body.get(
                "detail",
                body.get(
                    "message",
                    body.get("error", f"request failed with {response.status_code}"),
                ),
            )
            if isinstance(raw_detail, dict):
                detail = str(
                    raw_detail.get(
                        "message",
                        raw_detail.get("code", f"request failed with {response.status_code}"),
                    )
                )
            else:
                detail = str(raw_detail)
        else:
            detail = str(body) if body else f"request failed with {response.status_code}"

        exception_class: type[DaaiApiError]
        if response.status_code == 401:
            exception_class = DaaiUnauthorizedError
        elif response.status_code == 404:
            exception_class = DaaiNotFoundError
        elif response.status_code == 409:
            exception_class = DaaiConflictError
        elif response.status_code == 422:
            exception_class = DaaiValidationError
        else:
            exception_class = DaaiApiError

        raise exception_class(
            message=detail,
            status_code=response.status_code,
            body=body,
        )


def _parse_execution_report(data: dict[str, Any]) -> ExecutionReportResponse:
    reported_at_raw = data.get("execution_reported_at")
    reported_at = (
        _parse_datetime(reported_at_raw) if reported_at_raw is not None else None
    )
    return ExecutionReportResponse(
        action_run_id=UUID(data["action_run_id"]),
        execution_status=ExecutionStatus(data["execution_status"]),
        execution_error=data.get("execution_error"),
        execution_reported_at=reported_at,
        idempotent_replay=bool(data["idempotent_replay"]),
    )


def _parse_receipt(raw: dict[str, Any] | None) -> GovernanceReceipt | None:
    if raw is None:
        return None

    return GovernanceReceipt(
        id=UUID(raw["id"]),
        outcome=raw["outcome"],
        reason=raw["reason"],
        policy_type=raw["policy_type"],
        policy_snapshot=raw["policy_snapshot"],
        created_at=_parse_datetime(raw["created_at"]),
    )


def _parse_datetime(value: str) -> datetime:
    # FastAPI/Pydantic can emit UTC as a trailing "Z"; Python 3.9
    # fromisoformat expects "+00:00", so normalize first.
    if value.endswith("Z"):
        value = f"{value[:-1]}+00:00"
    return datetime.fromisoformat(value)
