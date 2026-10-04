from __future__ import annotations

import os
import secrets
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from dotenv import load_dotenv
from psycopg import Cursor, connect
from psycopg.types.json import Jsonb

# Allow running the script from repo root or apps/api.
APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

# Load apps/api/.env automatically for local dev runs.
load_dotenv(APP_ROOT / ".env")

from app.hashing import hash_api_key, hash_workspace_key

DEMO_WORKSPACE_ID = UUID("11111111-1111-1111-1111-111111111111")
DEMO_CLIENT_NAME = "Demo Finance Client"
DEMO_WORKSPACE_NAME = "Demo Finance Workspace"
DEMO_API_KEY_LABEL = "demo-seed-key"

DEMO_ACTIONS: dict[str, dict[str, Any]] = {
    "pay_vendor": {
        "id": UUID("aaaaaaaa-0000-0000-0000-000000000001"),
        "policy_type": "require_approval_above_amount",
        "policy_config": {"threshold": 5000, "amount_field": "amount"},
    },
    "send_invoice_reminder": {
        "id": UUID("aaaaaaaa-0000-0000-0000-000000000002"),
        "policy_type": "always_allow",
        "policy_config": {},
    },
    "mark_invoice_paid": {
        "id": UUID("aaaaaaaa-0000-0000-0000-000000000003"),
        "policy_type": "always_require_approval",
        "policy_config": {},
    },
    "wire_transfer": {
        "id": UUID("aaaaaaaa-0000-0000-0000-000000000004"),
        "policy_type": "always_block",
        "policy_config": {},
    },
}


@dataclass(frozen=True)
class DemoRun:
    id: UUID
    action_name: str
    governance_status: str
    execution_status: str
    governance_reason: str
    payload: dict[str, Any]
    policy_snapshot: dict[str, Any]
    idempotency_key: str
    execution_result: dict[str, Any]
    execution_error: str | None
    created_offset_minutes: int
    decided_offset_minutes: int
    execution_reported_offset_minutes: int | None


DEMO_RUNS: list[DemoRun] = [
    DemoRun(
        id=UUID("bbbbbbbb-0000-0000-0000-000000000001"),
        action_name="send_invoice_reminder",
        governance_status="allowed",
        execution_status="awaiting_execution_report",
        governance_reason="policy_always_allow",
        payload={
            "client_name": DEMO_CLIENT_NAME,
            "invoice_id": "INV-1001",
            "recipient": "ap@vendor-one.com",
        },
        policy_snapshot={"policy_type": "always_allow", "policy_config": {}},
        idempotency_key="demo:allowed-awaiting:reminder:INV-1001",
        execution_result={},
        execution_error=None,
        created_offset_minutes=80,
        decided_offset_minutes=80,
        execution_reported_offset_minutes=None,
    ),
    DemoRun(
        id=UUID("bbbbbbbb-0000-0000-0000-000000000002"),
        action_name="send_invoice_reminder",
        governance_status="allowed",
        execution_status="executed",
        governance_reason="policy_always_allow",
        payload={
            "client_name": DEMO_CLIENT_NAME,
            "invoice_id": "INV-1002",
            "recipient": "ops@vendor-two.com",
        },
        policy_snapshot={"policy_type": "always_allow", "policy_config": {}},
        idempotency_key="demo:allowed-executed:reminder:INV-1002",
        execution_result={"provider": "sendgrid", "message_id": "sg_demo_1002"},
        execution_error=None,
        created_offset_minutes=70,
        decided_offset_minutes=70,
        execution_reported_offset_minutes=68,
    ),
    DemoRun(
        id=UUID("bbbbbbbb-0000-0000-0000-000000000003"),
        action_name="pay_vendor",
        governance_status="pending_approval",
        execution_status="not_executed",
        governance_reason="policy_amount_above_threshold",
        payload={
            "client_name": DEMO_CLIENT_NAME,
            "vendor_id": "VENDOR-41",
            "amount": 9200,
            "currency": "USD",
        },
        policy_snapshot={
            "policy_type": "require_approval_above_amount",
            "policy_config": {"threshold": 5000, "amount_field": "amount"},
            "evaluated_amount_field": "amount",
            "evaluated_amount": "9200",
            "threshold": "5000",
        },
        idempotency_key="demo:pending-approval:pay-vendor:VENDOR-41",
        execution_result={},
        execution_error=None,
        created_offset_minutes=60,
        decided_offset_minutes=60,
        execution_reported_offset_minutes=None,
    ),
    DemoRun(
        id=UUID("bbbbbbbb-0000-0000-0000-000000000004"),
        action_name="mark_invoice_paid",
        governance_status="approved",
        execution_status="awaiting_execution_report",
        governance_reason="approved_by_human",
        payload={
            "client_name": DEMO_CLIENT_NAME,
            "invoice_id": "INV-1003",
            "paid_at": "2026-05-08T10:40:00Z",
        },
        policy_snapshot={"policy_type": "always_require_approval", "policy_config": {}},
        idempotency_key="demo:approved-awaiting:mark-paid:INV-1003",
        execution_result={},
        execution_error=None,
        created_offset_minutes=50,
        decided_offset_minutes=48,
        execution_reported_offset_minutes=None,
    ),
    DemoRun(
        id=UUID("bbbbbbbb-0000-0000-0000-000000000005"),
        action_name="mark_invoice_paid",
        governance_status="approved",
        execution_status="executed",
        governance_reason="approved_by_human",
        payload={
            "client_name": DEMO_CLIENT_NAME,
            "invoice_id": "INV-1004",
            "paid_at": "2026-05-08T10:45:00Z",
        },
        policy_snapshot={"policy_type": "always_require_approval", "policy_config": {}},
        idempotency_key="demo:approved-executed:mark-paid:INV-1004",
        execution_result={"ledger_entry_id": "led_1004"},
        execution_error=None,
        created_offset_minutes=40,
        decided_offset_minutes=38,
        execution_reported_offset_minutes=36,
    ),
    DemoRun(
        id=UUID("bbbbbbbb-0000-0000-0000-000000000006"),
        action_name="mark_invoice_paid",
        governance_status="rejected",
        execution_status="not_executed",
        governance_reason="rejected_by_human",
        payload={
            "client_name": DEMO_CLIENT_NAME,
            "invoice_id": "INV-1005",
            "paid_at": "2026-05-08T10:55:00Z",
        },
        policy_snapshot={"policy_type": "always_require_approval", "policy_config": {}},
        idempotency_key="demo:rejected:not-executed:mark-paid:INV-1005",
        execution_result={},
        execution_error=None,
        created_offset_minutes=30,
        decided_offset_minutes=28,
        execution_reported_offset_minutes=None,
    ),
    DemoRun(
        id=UUID("bbbbbbbb-0000-0000-0000-000000000007"),
        action_name="wire_transfer",
        governance_status="blocked",
        execution_status="not_executed",
        governance_reason="policy_always_block",
        payload={
            "client_name": DEMO_CLIENT_NAME,
            "amount": 20000,
            "destination": "EXT-ACCT-77",
        },
        policy_snapshot={"policy_type": "always_block", "policy_config": {}},
        idempotency_key="demo:blocked:not-executed:wire-transfer:20000",
        execution_result={},
        execution_error=None,
        created_offset_minutes=20,
        decided_offset_minutes=20,
        execution_reported_offset_minutes=None,
    ),
    DemoRun(
        id=UUID("bbbbbbbb-0000-0000-0000-000000000008"),
        action_name="send_invoice_reminder",
        governance_status="allowed",
        execution_status="failed",
        governance_reason="policy_always_allow",
        payload={
            "client_name": DEMO_CLIENT_NAME,
            "invoice_id": "INV-1006",
            "recipient": "billing@vendor-three.com",
        },
        policy_snapshot={"policy_type": "always_allow", "policy_config": {}},
        idempotency_key="demo:allowed-failed:reminder:INV-1006",
        execution_result={"provider": "sendgrid", "error_code": "timeout"},
        execution_error="smtp_timeout",
        created_offset_minutes=10,
        decided_offset_minutes=10,
        execution_reported_offset_minutes=8,
    ),
]


def _utc_offset(base_time: datetime, offset_minutes: int) -> datetime:
    return base_time - timedelta(minutes=offset_minutes)


def _insert_registered_actions(cur: Cursor[Any], workspace_id: UUID) -> None:
    for action_name, action in DEMO_ACTIONS.items():
        cur.execute(
            """
            INSERT INTO registered_actions (
                id,
                workspace_id,
                action_name,
                policy_type,
                policy_config
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                action["id"],
                workspace_id,
                action_name,
                action["policy_type"],
                Jsonb(action["policy_config"]),
            ),
        )


def _insert_action_runs_and_receipts(cur: Cursor[Any], workspace_id: UUID) -> None:
    now = datetime.now(timezone.utc)

    for index, run in enumerate(DEMO_RUNS, start=1):
        action_id = DEMO_ACTIONS[run.action_name]["id"]
        created_at = _utc_offset(now, run.created_offset_minutes)
        decided_at = _utc_offset(now, run.decided_offset_minutes)

        execution_reported_at = (
            _utc_offset(now, run.execution_reported_offset_minutes)
            if run.execution_reported_offset_minutes is not None
            else None
        )

        executed_at = execution_reported_at if run.execution_status == "executed" else None
        failed_at = execution_reported_at if run.execution_status == "failed" else None

        cur.execute(
            """
            INSERT INTO action_runs (
                id,
                workspace_id,
                registered_action_id,
                action_name,
                idempotency_key,
                governance_status,
                execution_status,
                governance_reason,
                payload,
                policy_snapshot,
                execution_result,
                execution_error,
                execution_reported_at,
                executed_at,
                failed_at,
                requested_at,
                decided_at,
                created_at,
                updated_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                run.id,
                workspace_id,
                action_id,
                run.action_name,
                run.idempotency_key,
                run.governance_status,
                run.execution_status,
                run.governance_reason,
                Jsonb(run.payload),
                Jsonb(run.policy_snapshot),
                Jsonb(run.execution_result),
                run.execution_error,
                execution_reported_at,
                executed_at,
                failed_at,
                created_at,
                decided_at,
                created_at,
                created_at,
            ),
        )

        if run.governance_status in {"allowed", "approved", "rejected", "blocked"}:
            cur.execute(
                """
                INSERT INTO governance_receipts (
                    id,
                    workspace_id,
                    action_run_id,
                    outcome,
                    reason,
                    policy_type,
                    policy_snapshot,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    UUID(f"cccccccc-0000-0000-0000-{index:012d}"),
                    workspace_id,
                    run.id,
                    run.governance_status,
                    run.governance_reason,
                    run.policy_snapshot.get("policy_type", "unknown_action"),
                    Jsonb(run.policy_snapshot),
                    decided_at,
                ),
            )


def main() -> int:
    database_url = os.getenv("DAAI_DATABASE_URL")
    if not database_url:
        print("DAAI_DATABASE_URL is required", file=sys.stderr)
        return 1

    api_key_pepper = os.getenv("DAAI_API_KEY_PEPPER", "dev-only-change-me")
    workspace_key_pepper = os.getenv("DAAI_WORKSPACE_KEY_PEPPER", "dev-only-change-me")
    dashboard_api_base_url = os.getenv("DAAI_PUBLIC_BASE_URL", "http://127.0.0.1:8000")
    dashboard_user_id_raw = os.getenv("DAAI_DEMO_DASHBOARD_USER_ID")
    dashboard_user_email = os.getenv("DAAI_DEMO_DASHBOARD_USER_EMAIL")
    dashboard_user_id: UUID | None = None
    if dashboard_user_id_raw:
        try:
            dashboard_user_id = UUID(dashboard_user_id_raw)
        except ValueError:
            print(
                "DAAI_DEMO_DASHBOARD_USER_ID must be a valid UUID",
                file=sys.stderr,
            )
            return 1

    demo_workspace_key = os.getenv("DAAI_DEMO_WORKSPACE_KEY") or secrets.token_urlsafe(24)
    demo_api_key = os.getenv("DAAI_DEMO_API_KEY") or secrets.token_urlsafe(24)

    demo_workspace_key_hash = hash_workspace_key(demo_workspace_key, workspace_key_pepper)
    demo_api_key_hash = hash_api_key(demo_api_key, api_key_pepper)

    with connect(database_url) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                # Workspace upsert.
                cur.execute(
                    """
                    INSERT INTO workspaces (id, workspace_key_hash, name, client_name, status)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (id)
                    DO UPDATE SET
                        name = EXCLUDED.name,
                        workspace_key_hash = EXCLUDED.workspace_key_hash,
                        client_name = EXCLUDED.client_name,
                        status = EXCLUDED.status
                    """,
                    (
                        DEMO_WORKSPACE_ID,
                        demo_workspace_key_hash,
                        DEMO_WORKSPACE_NAME,
                        DEMO_CLIENT_NAME,
                        "active",
                    ),
                )

                # Replace previous demo key by label.
                cur.execute(
                    """
                    UPDATE workspace_api_keys
                    SET revoked_at = NOW()
                    WHERE workspace_id = %s
                      AND label = %s
                      AND revoked_at IS NULL
                    """,
                    (DEMO_WORKSPACE_ID, DEMO_API_KEY_LABEL),
                )
                cur.execute(
                    """
                    INSERT INTO workspace_api_keys (id, workspace_id, key_hash, label)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (uuid4(), DEMO_WORKSPACE_ID, demo_api_key_hash, DEMO_API_KEY_LABEL),
                )

                if dashboard_user_id is not None:
                    cur.execute(
                        """
                        INSERT INTO profiles (id, email, created_at, updated_at)
                        VALUES (%s, %s, NOW(), NOW())
                        ON CONFLICT (id) DO UPDATE
                        SET email = COALESCE(EXCLUDED.email, profiles.email),
                            updated_at = NOW()
                        """,
                        (dashboard_user_id, dashboard_user_email),
                    )
                    cur.execute(
                        """
                        INSERT INTO workspace_members (
                            id,
                            workspace_id,
                            user_id,
                            role,
                            created_at
                        )
                        VALUES (%s, %s, %s, %s, NOW())
                        ON CONFLICT (workspace_id, user_id) DO NOTHING
                        """,
                        (uuid4(), DEMO_WORKSPACE_ID, dashboard_user_id, "owner"),
                    )

                # Idempotent reset for demo data only.
                cur.execute(
                    "DELETE FROM action_runs WHERE workspace_id = %s",
                    (DEMO_WORKSPACE_ID,),
                )
                cur.execute(
                    "DELETE FROM registered_actions WHERE workspace_id = %s",
                    (DEMO_WORKSPACE_ID,),
                )

                _insert_registered_actions(cur, DEMO_WORKSPACE_ID)
                _insert_action_runs_and_receipts(cur, DEMO_WORKSPACE_ID)

    print("Seed complete.")
    print(f"client_name={DEMO_CLIENT_NAME}")
    print(f"workspace_name={DEMO_WORKSPACE_NAME}")
    print(f"workspace_id={DEMO_WORKSPACE_ID}")
    print(f"workspace_key={demo_workspace_key}")
    print(f"api_key={demo_api_key}")
    if dashboard_user_id is not None:
        print(f"dashboard_user_id_linked={dashboard_user_id}")
    else:
        print("dashboard_user_id_linked=none")
    print("dashboard_env:")
    print(f"DAAI_API_BASE_URL={dashboard_api_base_url}")
    print("DAAI_SUPABASE_URL=<your_supabase_project_url>")
    print("DAAI_SUPABASE_ANON_KEY=<your_supabase_publishable_key>")
    print("sdk_test_credentials:")
    print(f"DAAI_SDK_API_KEY={demo_api_key}")
    print(f"DAAI_SDK_WORKSPACE_KEY={demo_workspace_key}")
    print("Note: only hashed keys are stored in the database.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
