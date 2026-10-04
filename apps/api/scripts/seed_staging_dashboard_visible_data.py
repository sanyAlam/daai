from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request
from uuid import UUID, uuid4

from psycopg import connect
from psycopg.types.json import Jsonb

APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.hashing import hash_workspace_key

WORKSPACE_NAME = "Email Smoke Test Workspace"
CLIENT_NAME = "Email Smoke Test Client"
DEFAULT_APPROVER_EMAIL = "sanyalam2k20@gmail.com"


@dataclass(frozen=True)
class ActionSeed:
    action_name: str
    title: str
    description: str
    risk_level: str
    policy_type: str = "always_require_approval"

    def policy_config(self) -> dict[str, str]:
        return {
            "title": self.title,
            "description": self.description,
            "risk_level": self.risk_level,
        }


@dataclass(frozen=True)
class RunSeed:
    label: str
    action_name: str
    idempotency_key: str
    governance_status: str
    execution_status: str
    governance_reason: str
    payload: dict[str, Any]
    execution_result: dict[str, Any]
    execution_error: str | None
    execution_reported_at: datetime | None
    executed_at: datetime | None
    failed_at: datetime | None
    requested_at: datetime
    decided_at: datetime
    created_at: datetime
    receipt_outcome: str | None
    receipt_reason: str | None


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _first_nonempty(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value and value.strip():
            return value.strip()
    return None


def _require_env(*names: str) -> str:
    value = _first_nonempty(*names)
    if value is None:
        joined = ", ".join(names)
        raise RuntimeError(f"missing required env variable ({joined})")
    return value


def _json_request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    timeout: int = 30,
) -> tuple[int, dict[str, Any]]:
    req_headers = dict(headers or {})
    data: bytes | None = None

    if payload is not None:
        req_headers.setdefault("Content-Type", "application/json")
        data = json.dumps(payload).encode("utf-8")

    req = urllib_request.Request(
        url=url,
        data=data,
        headers=req_headers,
        method=method,
    )
    try:
        with urllib_request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            parsed = json.loads(raw) if raw else {}
            if not isinstance(parsed, dict):
                parsed = {"data": parsed}
            return response.status, parsed
    except urllib_error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"detail": raw}
        if not isinstance(parsed, dict):
            parsed = {"data": parsed}
        return exc.code, parsed


def _detail(body: dict[str, Any]) -> str:
    detail = body.get("detail")
    if isinstance(detail, str) and detail:
        return detail
    return json.dumps(body)


def _decode_user_id_from_jwt(access_token: str) -> UUID:
    parts = access_token.split(".")
    if len(parts) != 3:
        raise RuntimeError("supabase access token format is invalid")
    payload_segment = parts[1]
    padding = "=" * ((4 - (len(payload_segment) % 4)) % 4)
    payload_bytes = base64.urlsafe_b64decode(payload_segment + padding)
    payload = json.loads(payload_bytes.decode("utf-8"))
    user_id_raw = payload.get("sub")
    if not isinstance(user_id_raw, str):
        raise RuntimeError("supabase access token is missing subject")
    return UUID(user_id_raw)


def _login_and_get_user_id(
    *,
    supabase_url: str,
    supabase_anon_key: str,
    login_email: str,
    login_password: str,
) -> tuple[str, UUID]:
    status, body = _json_request(
        "POST",
        f"{supabase_url.rstrip('/')}/auth/v1/token?grant_type=password",
        headers={
            "apikey": supabase_anon_key,
            "Content-Type": "application/json",
        },
        payload={
            "email": login_email,
            "password": login_password,
        },
    )
    if status != 200:
        raise RuntimeError(f"staging login failed ({status}): {_detail(body)}")

    access_token = body.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise RuntimeError("staging login succeeded but access_token is missing")

    user_obj = body.get("user")
    if isinstance(user_obj, dict) and isinstance(user_obj.get("id"), str):
        return access_token, UUID(user_obj["id"])

    return access_token, _decode_user_id_from_jwt(access_token)


def _build_seed_runs(now: datetime) -> list[RunSeed]:
    pending_created = now - timedelta(minutes=8)
    executed_created = now - timedelta(minutes=6)
    blocked_created = now - timedelta(minutes=4)
    executed_reported = now - timedelta(minutes=5)

    return [
        RunSeed(
            label="pending_approval",
            action_name="send_invoice_reminder",
            idempotency_key="seed:staging:pending:send_invoice_reminder:SEED-INV-001",
            governance_status="pending_approval",
            execution_status="not_executed",
            governance_reason="policy_requires_approval",
            payload={
                "actor": "staging_seed_agent",
                "invoice_id": "SEED-INV-001",
                "customer_name": "Seed Customer One",
                "customer_email": "customer@example.com",
                "amount": 1250,
                "source": {
                    "type": "staging_seed",
                    "ref": "dashboard-visibility",
                },
            },
            execution_result={},
            execution_error=None,
            execution_reported_at=None,
            executed_at=None,
            failed_at=None,
            requested_at=pending_created,
            decided_at=pending_created,
            created_at=pending_created,
            receipt_outcome=None,
            receipt_reason=None,
        ),
        RunSeed(
            label="allowed_executed",
            action_name="escalate_overdue_invoice",
            idempotency_key="seed:staging:allowed-executed:escalate_overdue_invoice:SEED-INV-002",
            governance_status="allowed",
            execution_status="executed",
            governance_reason="seeded_allowed_execution",
            payload={
                "actor": "staging_seed_agent",
                "invoice_id": "SEED-INV-002",
                "customer_name": "Seed Customer Two",
                "days_overdue": 14,
                "source": {
                    "type": "staging_seed",
                    "ref": "dashboard-visibility",
                },
            },
            execution_result={
                "result_summary": "Escalation created for manager review.",
            },
            execution_error=None,
            execution_reported_at=executed_reported,
            executed_at=executed_reported,
            failed_at=None,
            requested_at=executed_created,
            decided_at=executed_created,
            created_at=executed_created,
            receipt_outcome="allowed",
            receipt_reason="seeded_allowed_execution",
        ),
        RunSeed(
            label="blocked",
            action_name="mark_invoice_paid",
            idempotency_key="seed:staging:blocked:mark_invoice_paid:SEED-INV-003",
            governance_status="blocked",
            execution_status="not_executed",
            governance_reason="seeded_blocked_for_review",
            payload={
                "actor": "staging_seed_agent",
                "invoice_id": "SEED-INV-003",
                "payment_reference": "PAY-003",
                "source": {
                    "type": "staging_seed",
                    "ref": "dashboard-visibility",
                },
            },
            execution_result={},
            execution_error=None,
            execution_reported_at=None,
            executed_at=None,
            failed_at=None,
            requested_at=blocked_created,
            decided_at=blocked_created,
            created_at=blocked_created,
            receipt_outcome="blocked",
            receipt_reason="seeded_blocked_for_review",
        ),
    ]


def main() -> int:
    _load_env_file(REPO_ROOT / ".env.staging.local")
    _load_env_file(APP_ROOT / ".env.smoke.email")

    database_url = _require_env("DAAI_DATABASE_URL")
    supabase_url = _require_env("DAAI_SUPABASE_URL")
    supabase_anon_key = _require_env("DAAI_SUPABASE_ANON_KEY")
    workspace_key_pepper = _require_env("DAAI_WORKSPACE_KEY_PEPPER")

    login_email = _require_env(
        "DAAI_STAGING_LOGIN_EMAIL",
        "DAAI_SMOKE_DASHBOARD_EMAIL",
    )
    login_password = _require_env(
        "DAAI_STAGING_LOGIN_PASSWORD",
        "DAAI_SMOKE_DASHBOARD_PASSWORD",
    )
    approver_email = (
        _first_nonempty("DAAI_STAGING_APPROVER_EMAIL") or DEFAULT_APPROVER_EMAIL
    ).lower()

    _, user_id = _login_and_get_user_id(
        supabase_url=supabase_url,
        supabase_anon_key=supabase_anon_key,
        login_email=login_email,
        login_password=login_password,
    )

    actions = [
        ActionSeed(
            action_name="send_invoice_reminder",
            title="Send invoice reminder",
            description="Sends a payment reminder to an overdue invoice customer.",
            risk_level="medium",
        ),
        ActionSeed(
            action_name="mark_invoice_paid",
            title="Mark invoice paid",
            description="Marks an invoice as paid after payment confirmation.",
            risk_level="high",
        ),
        ActionSeed(
            action_name="escalate_overdue_invoice",
            title="Escalate overdue invoice",
            description="Escalates an overdue invoice to a manager.",
            risk_level="medium",
        ),
    ]

    now = datetime.now(timezone.utc)
    run_seeds = _build_seed_runs(now)

    workspace_created = False
    profile_upserted = False
    membership_exists = False
    workspace_id: UUID
    action_results: list[dict[str, Any]] = []
    run_results: list[dict[str, Any]] = []
    receipt_results: list[dict[str, Any]] = []

    with connect(database_url) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO profiles (id, email, created_at, updated_at)
                    VALUES (%s, %s, NOW(), NOW())
                    ON CONFLICT (id) DO UPDATE
                    SET email = COALESCE(EXCLUDED.email, profiles.email),
                        updated_at = NOW()
                    """,
                    (user_id, login_email.lower()),
                )
                profile_upserted = True

                cur.execute(
                    """
                    SELECT id, workspace_key_hash
                    FROM workspaces
                    WHERE name = %s
                    ORDER BY created_at ASC
                    LIMIT 1
                    """,
                    (WORKSPACE_NAME,),
                )
                workspace_row = cur.fetchone()

                generated_workspace_key_hash = hash_workspace_key(
                    workspace_key=f"daai_wk_seed_{uuid4().hex}",
                    pepper=workspace_key_pepper,
                )

                if workspace_row is None:
                    workspace_id = uuid4()
                    cur.execute(
                        """
                        INSERT INTO workspaces (
                            id,
                            workspace_key_hash,
                            name,
                            client_name,
                            status,
                            approval_emails,
                            approval_link_ttl_minutes,
                            created_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                        """,
                        (
                            workspace_id,
                            generated_workspace_key_hash,
                            WORKSPACE_NAME,
                            CLIENT_NAME,
                            "active",
                            [approver_email],
                            15,
                        ),
                    )
                    workspace_created = True
                else:
                    workspace_id = workspace_row[0]
                    existing_workspace_key_hash = workspace_row[1]
                    cur.execute(
                        """
                        UPDATE workspaces
                        SET name = %s,
                            client_name = %s,
                            status = 'active',
                            approval_emails = %s,
                            approval_link_ttl_minutes = %s,
                            workspace_key_hash = COALESCE(workspace_key_hash, %s)
                        WHERE id = %s
                        """,
                        (
                            WORKSPACE_NAME,
                            CLIENT_NAME,
                            [approver_email],
                            15,
                            generated_workspace_key_hash
                            if existing_workspace_key_hash is None
                            else existing_workspace_key_hash,
                            workspace_id,
                        ),
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
                    ON CONFLICT (workspace_id, user_id) DO UPDATE
                    SET role = EXCLUDED.role
                    """,
                    (uuid4(), workspace_id, user_id, "owner"),
                )

                cur.execute(
                    """
                    SELECT 1
                    FROM workspace_members
                    WHERE workspace_id = %s
                      AND user_id = %s
                    LIMIT 1
                    """,
                    (workspace_id, user_id),
                )
                membership_exists = cur.fetchone() is not None

                action_ids: dict[str, UUID] = {}
                action_policy_configs: dict[str, dict[str, str]] = {}
                for action in actions:
                    cur.execute(
                        """
                        SELECT id
                        FROM registered_actions
                        WHERE workspace_id = %s
                          AND action_name = %s
                        LIMIT 1
                        """,
                        (workspace_id, action.action_name),
                    )
                    existing_action_row = cur.fetchone()
                    existed = existing_action_row is not None

                    cur.execute(
                        """
                        INSERT INTO registered_actions (
                            id,
                            workspace_id,
                            action_name,
                            policy_type,
                            policy_config,
                            created_at
                        )
                        VALUES (%s, %s, %s, %s, %s, NOW())
                        ON CONFLICT (workspace_id, action_name) DO UPDATE
                        SET policy_type = EXCLUDED.policy_type,
                            policy_config = EXCLUDED.policy_config
                        RETURNING id
                        """,
                        (
                            uuid4(),
                            workspace_id,
                            action.action_name,
                            action.policy_type,
                            Jsonb(action.policy_config()),
                        ),
                    )
                    action_id = cur.fetchone()[0]
                    action_ids[action.action_name] = action_id
                    action_policy_configs[action.action_name] = action.policy_config()
                    action_results.append(
                        {
                            "action_name": action.action_name,
                            "policy_type": action.policy_type,
                            "action_id": str(action_id),
                            "created": not existed,
                        }
                    )

                for run in run_seeds:
                    cur.execute(
                        """
                        SELECT id
                        FROM action_runs
                        WHERE workspace_id = %s
                          AND action_name = %s
                          AND idempotency_key = %s
                        LIMIT 1
                        """,
                        (workspace_id, run.action_name, run.idempotency_key),
                    )
                    existing_run_row = cur.fetchone()
                    run_existed = existing_run_row is not None

                    policy_snapshot = {
                        "policy_type": "always_require_approval",
                        "policy_config": action_policy_configs[run.action_name],
                        "seed_label": run.label,
                    }

                    if existing_run_row is None:
                        action_run_id = uuid4()
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
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                            )
                            """,
                            (
                                action_run_id,
                                workspace_id,
                                action_ids[run.action_name],
                                run.action_name,
                                run.idempotency_key,
                                run.governance_status,
                                run.execution_status,
                                run.governance_reason,
                                Jsonb(run.payload),
                                Jsonb(policy_snapshot),
                                Jsonb(run.execution_result),
                                run.execution_error,
                                run.execution_reported_at,
                                run.executed_at,
                                run.failed_at,
                                run.requested_at,
                                run.decided_at,
                                run.created_at,
                            ),
                        )
                    else:
                        action_run_id = existing_run_row[0]
                        cur.execute(
                            """
                            UPDATE action_runs
                            SET registered_action_id = %s,
                                governance_status = %s,
                                execution_status = %s,
                                governance_reason = %s,
                                payload = %s,
                                policy_snapshot = %s,
                                execution_result = %s,
                                execution_error = %s,
                                execution_reported_at = %s,
                                executed_at = %s,
                                failed_at = %s,
                                requested_at = %s,
                                decided_at = %s,
                                updated_at = NOW()
                            WHERE id = %s
                            """,
                            (
                                action_ids[run.action_name],
                                run.governance_status,
                                run.execution_status,
                                run.governance_reason,
                                Jsonb(run.payload),
                                Jsonb(policy_snapshot),
                                Jsonb(run.execution_result),
                                run.execution_error,
                                run.execution_reported_at,
                                run.executed_at,
                                run.failed_at,
                                run.requested_at,
                                run.decided_at,
                                action_run_id,
                            ),
                        )
                    run_results.append(
                        {
                            "label": run.label,
                            "action_name": run.action_name,
                            "action_run_id": str(action_run_id),
                            "governance_status": run.governance_status,
                            "execution_status": run.execution_status,
                            "created": not run_existed,
                        }
                    )

                    if run.receipt_outcome is None or run.receipt_reason is None:
                        continue

                    cur.execute(
                        """
                        SELECT id
                        FROM governance_receipts
                        WHERE action_run_id = %s
                        LIMIT 1
                        """,
                        (action_run_id,),
                    )
                    existing_receipt = cur.fetchone()
                    receipt_existed = existing_receipt is not None

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
                        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                        ON CONFLICT (action_run_id) DO UPDATE
                        SET outcome = EXCLUDED.outcome,
                            reason = EXCLUDED.reason,
                            policy_type = EXCLUDED.policy_type,
                            policy_snapshot = EXCLUDED.policy_snapshot
                        RETURNING id
                        """,
                        (
                            uuid4(),
                            workspace_id,
                            action_run_id,
                            run.receipt_outcome,
                            run.receipt_reason,
                            "always_require_approval",
                            Jsonb(
                                {
                                    "policy_type": "always_require_approval",
                                    "seed_label": run.label,
                                }
                            ),
                        ),
                    )
                    receipt_id = cur.fetchone()[0]
                    receipt_results.append(
                        {
                            "action_run_id": str(action_run_id),
                            "receipt_id": str(receipt_id),
                            "outcome": run.receipt_outcome,
                            "created": not receipt_existed,
                        }
                    )

    result = {
        "staging_login_succeeded": True,
        "user_id": str(user_id),
        "profile_upserted": profile_upserted,
        "workspace_name": WORKSPACE_NAME,
        "workspace_id": str(workspace_id),
        "workspace_created": workspace_created,
        "workspace_membership_exists": membership_exists,
        "approver_email": approver_email,
        "actions": action_results,
        "runs": run_results,
        "receipts": receipt_results,
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
