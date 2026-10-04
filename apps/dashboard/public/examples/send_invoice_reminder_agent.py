#!/usr/bin/env python3
"""DAAI test agent for a governed send_invoice_reminder action.

This script does not send a real email. It proposes a registered action to DAAI,
prints the governance decision, and only simulates execution when executable is true.
"""

from __future__ import annotations

import os
from typing import Any

from daai import DaaiClient


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def send_invoice_reminder(payload: dict[str, Any]) -> dict[str, str]:
    print(
        "Simulated email: reminder for "
        f"{payload['invoice_id']} to {payload['customer_email']}"
    )
    return {"result_summary": "Invoice reminder email simulated successfully."}


def main() -> None:
    client = DaaiClient(
        api_key=require_env("DAAI_API_KEY"),
        workspace_key=require_env("DAAI_WORKSPACE_KEY"),
        base_url=os.environ.get("DAAI_BASE_URL", "http://127.0.0.1:8000"),
    )

    payload = {
        "actor": "finance_agent",
        "invoice_id": "INV-1025",
        "customer_name": "ABC Pty Ltd",
        "customer_email": "accounts@example.com",
        "amount": 1250,
        "reasoning": "Invoice is overdue and no reply has been received.",
        "source": {
            "type": "finance_admin_agent",
            "ref": "INV-1025",
        },
    }

    result = client.intercept(
        action="send_invoice_reminder",
        payload=payload,
        idempotency_key="invoice-reminder:INV-1025",
    )

    print(f"Action run: {result.action_run_id}")
    print(f"Governance status: {result.governance_status}")
    print(f"Execution status: {result.execution_status}")
    print(f"Executable: {result.executable}")
    print(f"Reason: {result.governance_reason}")

    if not result.executable:
        print("DAAI says do not execute yet. Approve, reject, or review in the dashboard.")
        return

    execution_result = send_invoice_reminder(payload)
    client.report_executed(
        result.action_run_id,
        execution_result=execution_result,
    )
    print("Execution reported to DAAI.")


if __name__ == "__main__":
    main()
