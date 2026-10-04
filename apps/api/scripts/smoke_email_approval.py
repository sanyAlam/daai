from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request
from uuid import uuid4

from psycopg import connect
from psycopg.types.json import Jsonb

APP_ROOT = Path(__file__).resolve().parents[1]


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


# Load standard local env + smoke env defaults.
_load_env_file(APP_ROOT / ".env")
_load_env_file(APP_ROOT / ".env.smoke.email")


@dataclass
class HttpResult:
    status: int
    body: dict[str, Any]


class SmokeError(RuntimeError):
    pass


def _json_request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    timeout: int = 20,
) -> HttpResult:
    req_headers = dict(headers or {})
    data: bytes | None = None

    if payload is not None:
        req_headers.setdefault("Content-Type", "application/json")
        data = json.dumps(payload).encode("utf-8")

    req = urllib_request.Request(
        url,
        data=data,
        headers=req_headers,
        method=method,
    )

    try:
        with urllib_request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            body = json.loads(raw) if raw else {}
            if not isinstance(body, dict):
                body = {"data": body}
            return HttpResult(status=response.status, body=body)
    except urllib_error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"detail": raw}
        if not isinstance(parsed, dict):
            parsed = {"data": parsed}
        return HttpResult(status=exc.code, body=parsed)
    except urllib_error.URLError as exc:
        raise SmokeError(f"network error calling {url}: {exc.reason}") from exc


def _detail(result: HttpResult) -> str:
    detail = result.body.get("detail")
    if isinstance(detail, str) and detail:
        return detail
    return json.dumps(result.body)


def _require_env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None or not value.strip():
        raise SmokeError(f"missing required env: {name}")
    return value.strip()


def _parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _dashboard_request(
    method: str,
    api_base_url: str,
    access_token: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> HttpResult:
    return _json_request(
        method,
        f"{api_base_url.rstrip('/')}{path}",
        headers={"Authorization": f"Bearer {access_token}"},
        payload=payload,
    )


def _sdk_intercept(
    api_base_url: str,
    sdk_api_key: str,
    workspace_key: str,
    action: str,
    amount: int,
    idempotency_key: str,
) -> HttpResult:
    return _json_request(
        "POST",
        f"{api_base_url.rstrip('/')}/v1/sdk/intercept",
        headers={
            "Authorization": f"Bearer {sdk_api_key}",
            "X-DAAI-Workspace-Key": workspace_key,
        },
        payload={
            "action": action,
            "payload": {
                "amount": amount,
                "vendor_id": f"SMOKE-{uuid4().hex[:8].upper()}",
            },
            "idempotency_key": idempotency_key,
        },
    )


def _sdk_status(
    api_base_url: str,
    sdk_api_key: str,
    workspace_key: str,
    action_run_id: str,
) -> HttpResult:
    return _json_request(
        "GET",
        f"{api_base_url.rstrip('/')}/v1/sdk/action-runs/{action_run_id}/status",
        headers={
            "Authorization": f"Bearer {sdk_api_key}",
            "X-DAAI-Workspace-Key": workspace_key,
        },
    )


def _sign_in_dashboard_user(
    supabase_url: str,
    supabase_anon_key: str,
    email: str,
    password: str,
) -> str:
    result = _json_request(
        "POST",
        f"{supabase_url.rstrip('/')}/auth/v1/token?grant_type=password",
        headers={
            "apikey": supabase_anon_key,
            "Content-Type": "application/json",
        },
        payload={"email": email, "password": password},
    )
    if result.status != 200:
        raise SmokeError(
            f"dashboard login failed ({result.status}): {_detail(result)}"
        )

    access_token = result.body.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise SmokeError("dashboard login succeeded but access_token is missing")
    return access_token


def _ensure_registered_action(
    database_url: str,
    workspace_id: str,
    action_name: str,
) -> None:
    with connect(database_url) as conn:
        with conn.cursor() as cur:
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
                ON CONFLICT (workspace_id, action_name)
                DO UPDATE SET
                    policy_type = EXCLUDED.policy_type,
                    policy_config = EXCLUDED.policy_config
                """,
                (
                    str(uuid4()),
                    workspace_id,
                    action_name,
                    "always_require_approval",
                    Jsonb({}),
                ),
            )
        conn.commit()


def _poll_until_decided(
    *,
    api_base_url: str,
    sdk_api_key: str,
    workspace_key: str,
    action_run_id: str,
    timeout_seconds: int,
    poll_interval_seconds: int,
) -> HttpResult:
    deadline = time.time() + timeout_seconds
    while True:
        status_result = _sdk_status(
            api_base_url,
            sdk_api_key,
            workspace_key,
            action_run_id,
        )
        if status_result.status != 200:
            raise SmokeError(
                f"status endpoint failed ({status_result.status}): {_detail(status_result)}"
            )

        governance_status = status_result.body.get("governance_status")
        if governance_status != "pending_approval":
            return status_result

        if time.time() >= deadline:
            raise SmokeError(
                f"timeout waiting for approval decision (run_id={action_run_id})"
            )

        print(
            f"  still pending approval... checking again in {poll_interval_seconds}s",
            flush=True,
        )
        time.sleep(poll_interval_seconds)


def _validate_final_state(result: HttpResult, expected_decision: str | None) -> None:
    governance_status = result.body.get("governance_status")
    execution_status = result.body.get("execution_status")
    executable = result.body.get("executable")

    valid_decisions = {"approved", "rejected", "blocked"}
    if governance_status not in valid_decisions:
        raise SmokeError(
            "expected governance_status in approved/rejected/blocked, got "
            f"{governance_status!r}"
        )

    if expected_decision and governance_status != expected_decision:
        raise SmokeError(
            f"expected final decision {expected_decision}, got {governance_status}"
        )

    if governance_status == "approved":
        if execution_status != "awaiting_execution_report" or executable is not True:
            raise SmokeError(
                "approved run must be executable=true and execution_status=awaiting_execution_report"
            )
    else:
        if execution_status != "not_executed" or executable is not False:
            raise SmokeError(
                f"{governance_status} run must be executable=false and execution_status=not_executed"
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Smoke test real email approval flow using dashboard login + SDK intercept.",
    )
    parser.add_argument(
        "--email",
        default=os.environ.get("DAAI_SMOKE_DASHBOARD_EMAIL", ""),
        help="Supabase dashboard user email",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("DAAI_SMOKE_DASHBOARD_PASSWORD", ""),
        help="Supabase dashboard user password",
    )
    parser.add_argument(
        "--api-base-url",
        default=os.environ.get("DAAI_SMOKE_API_BASE_URL", "http://127.0.0.1:8000"),
        help="DAAI API base URL",
    )
    parser.add_argument(
        "--workspace-id",
        default=os.environ.get("DAAI_SMOKE_WORKSPACE_ID", ""),
        help="Existing workspace id (optional). If omitted, script creates a new workspace.",
    )
    parser.add_argument(
        "--workspace-key",
        default=os.environ.get("DAAI_SMOKE_WORKSPACE_KEY", ""),
        help="Existing workspace key. Required when using --workspace-id unless --regenerate-workspace-key is set.",
    )
    parser.add_argument(
        "--workspace-name",
        default="Email Approval Smoke Workspace",
        help="Workspace name when creating a new workspace",
    )
    parser.add_argument(
        "--client-name",
        default="Email Approval Smoke Client",
        help="Client name when creating a new workspace",
    )
    parser.add_argument(
        "--approval-emails",
        default=os.environ.get("DAAI_SMOKE_APPROVAL_EMAILS", ""),
        help="Comma-separated approval emails to set before intercept (optional)",
    )
    parser.add_argument(
        "--approval-ttl-minutes",
        type=int,
        default=int(os.environ.get("DAAI_SMOKE_APPROVAL_TTL_MINUTES", "15")),
        help="Approval link TTL in minutes (5-1440)",
    )
    parser.add_argument(
        "--action-name",
        default="pay_vendor",
        help="Action name to intercept",
    )
    parser.add_argument(
        "--amount",
        type=int,
        default=9000,
        help="Payload amount used for intercept",
    )
    parser.add_argument(
        "--expected-decision",
        choices=["approved", "rejected", "blocked"],
        default=None,
        help="Fail if final decision differs from this value",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=600,
        help="How long to wait for email click before failing",
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=int,
        default=4,
        help="Status poll interval",
    )
    parser.add_argument(
        "--regenerate-workspace-key",
        action="store_true",
        help="When using existing workspace, regenerate workspace key if no key is provided.",
    )
    parser.add_argument(
        "--no-action-upsert",
        action="store_true",
        help="Skip DB upsert for registered action",
    )
    parser.add_argument(
        "--allow-missing-approval-emails",
        action="store_true",
        help="Allow run to continue even if no approval emails are configured on workspace.",
    )

    args = parser.parse_args()
    dashboard_access_token = ""
    api_key_id: str | None = None

    try:
        supabase_url = _require_env("DAAI_SUPABASE_URL")
        supabase_anon_key = _require_env("DAAI_SUPABASE_ANON_KEY")
        database_url = os.environ.get("DAAI_DATABASE_URL", "").strip()

        if not args.email or not args.password:
            raise SmokeError(
                "missing dashboard credentials. Provide --email/--password or set DAAI_SMOKE_DASHBOARD_EMAIL + DAAI_SMOKE_DASHBOARD_PASSWORD"
            )

        if args.approval_ttl_minutes < 5 or args.approval_ttl_minutes > 1440:
            raise SmokeError("approval ttl must be between 5 and 1440 minutes")

        print("[1/8] Logging in to Supabase dashboard auth...", flush=True)
        dashboard_access_token = _sign_in_dashboard_user(
            supabase_url=supabase_url,
            supabase_anon_key=supabase_anon_key,
            email=args.email,
            password=args.password,
        )

        workspace_id = args.workspace_id.strip()
        workspace_key = args.workspace_key.strip()

        print("[2/8] Preparing workspace...", flush=True)
        if not workspace_id:
            create_workspace = _dashboard_request(
                "POST",
                args.api_base_url,
                dashboard_access_token,
                "/v1/dashboard/workspaces",
                payload={
                    "workspace_name": args.workspace_name,
                    "client_name": args.client_name,
                },
            )
            if create_workspace.status != 200:
                raise SmokeError(
                    "workspace creation failed "
                    f"({create_workspace.status}): {_detail(create_workspace)}"
                )

            workspace_id_value = create_workspace.body.get("id")
            workspace_key_value = create_workspace.body.get("workspace_key")
            if not isinstance(workspace_id_value, str) or not workspace_id_value:
                raise SmokeError("workspace creation response missing id")
            if not isinstance(workspace_key_value, str) or not workspace_key_value:
                raise SmokeError("workspace creation response missing workspace_key")

            workspace_id = workspace_id_value
            workspace_key = workspace_key_value
            print(f"  created workspace: {workspace_id}", flush=True)
        else:
            workspace_lookup = _dashboard_request(
                "GET",
                args.api_base_url,
                dashboard_access_token,
                f"/v1/dashboard/workspaces/{workspace_id}",
            )
            if workspace_lookup.status != 200:
                raise SmokeError(
                    "workspace lookup failed "
                    f"({workspace_lookup.status}): {_detail(workspace_lookup)}"
                )

            if not workspace_key:
                if not args.regenerate_workspace_key:
                    raise SmokeError(
                        "workspace key is required for existing workspace. Set --workspace-key or DAAI_SMOKE_WORKSPACE_KEY, or use --regenerate-workspace-key"
                    )

                regenerate = _dashboard_request(
                    "POST",
                    args.api_base_url,
                    dashboard_access_token,
                    f"/v1/dashboard/workspaces/{workspace_id}/regenerate-key",
                    payload={},
                )
                if regenerate.status != 200:
                    raise SmokeError(
                        "workspace key regeneration failed "
                        f"({regenerate.status}): {_detail(regenerate)}"
                    )
                regenerated_workspace_key = regenerate.body.get("workspace_key")
                if not isinstance(regenerated_workspace_key, str) or not regenerated_workspace_key:
                    raise SmokeError("regenerate-key response missing workspace_key")
                workspace_key = regenerated_workspace_key
                print("  regenerated workspace key for smoke run", flush=True)

        approval_emails = _parse_csv(args.approval_emails)
        if approval_emails:
            print("[3/8] Saving approval email settings...", flush=True)
            save_settings = _dashboard_request(
                "POST",
                args.api_base_url,
                dashboard_access_token,
                f"/v1/dashboard/workspaces/{workspace_id}/approval-settings",
                payload={
                    "approval_emails": approval_emails,
                    "approval_link_ttl_minutes": args.approval_ttl_minutes,
                },
            )
            if save_settings.status != 200:
                raise SmokeError(
                    "saving approval settings failed "
                    f"({save_settings.status}): {_detail(save_settings)}"
                )
        else:
            print("[3/8] Reading existing approval email settings...", flush=True)

        settings = _dashboard_request(
            "GET",
            args.api_base_url,
            dashboard_access_token,
            f"/v1/dashboard/workspaces/{workspace_id}/approval-settings",
        )
        if settings.status != 200:
            raise SmokeError(
                "loading approval settings failed "
                f"({settings.status}): {_detail(settings)}"
            )

        configured_emails = settings.body.get("approval_emails")
        if not isinstance(configured_emails, list):
            configured_emails = []
        configured_emails = [value for value in configured_emails if isinstance(value, str)]

        if not configured_emails:
            message = (
                "no approval emails configured on this workspace. "
                "Add 1-2 emails in dashboard or pass --approval-emails."
            )
            if args.allow_missing_approval_emails:
                print(f"  WARNING: {message}", flush=True)
            else:
                raise SmokeError(message)
        else:
            print(
                "  approval emails configured: " + ", ".join(configured_emails),
                flush=True,
            )

        print("[4/8] Creating temporary SDK API key for smoke run...", flush=True)
        created_key = _dashboard_request(
            "POST",
            args.api_base_url,
            dashboard_access_token,
            "/v1/dashboard/api-keys",
            payload={
                "workspace_id": workspace_id,
                "name": f"email-smoke-{uuid4().hex[:8]}",
            },
        )
        if created_key.status != 200:
            raise SmokeError(
                f"api key creation failed ({created_key.status}): {_detail(created_key)}"
            )

        api_key_id_value = created_key.body.get("id")
        sdk_api_key = created_key.body.get("raw_api_key")
        if not isinstance(api_key_id_value, str) or not api_key_id_value:
            raise SmokeError("api key response missing id")
        if not isinstance(sdk_api_key, str) or not sdk_api_key:
            raise SmokeError("api key response missing raw_api_key")
        api_key_id = api_key_id_value

        if not args.no_action_upsert:
            if not database_url:
                raise SmokeError(
                    "DAAI_DATABASE_URL is required to upsert registered action. Set --no-action-upsert if action already exists."
                )
            print("[5/8] Ensuring action policy requires approval...", flush=True)
            _ensure_registered_action(
                database_url=database_url,
                workspace_id=workspace_id,
                action_name=args.action_name,
            )
        else:
            print("[5/8] Skipping action upsert (--no-action-upsert)", flush=True)

        print("[6/8] Triggering pending approval intercept...", flush=True)
        intercept_result = _sdk_intercept(
            api_base_url=args.api_base_url,
            sdk_api_key=sdk_api_key,
            workspace_key=workspace_key,
            action=args.action_name,
            amount=args.amount,
            idempotency_key=f"email-smoke:{uuid4()}",
        )
        if intercept_result.status != 200:
            raise SmokeError(
                "intercept failed "
                f"({intercept_result.status}): {_detail(intercept_result)}"
            )

        run_id = intercept_result.body.get("action_run_id")
        governance_status = intercept_result.body.get("governance_status")
        if not isinstance(run_id, str) or not run_id:
            raise SmokeError("intercept response missing action_run_id")
        if governance_status != "pending_approval":
            raise SmokeError(
                "expected pending_approval after intercept, got "
                f"{governance_status!r}. body={json.dumps(intercept_result.body)}"
            )

        print("[7/8] Pending run created.", flush=True)
        print(f"  action_run_id: {run_id}", flush=True)
        print(
            "  open your email now and click one link: Approve / Reject / Block",
            flush=True,
        )
        print(
            f"  polling status for up to {args.timeout_seconds}s...",
            flush=True,
        )

        decided = _poll_until_decided(
            api_base_url=args.api_base_url,
            sdk_api_key=sdk_api_key,
            workspace_key=workspace_key,
            action_run_id=run_id,
            timeout_seconds=args.timeout_seconds,
            poll_interval_seconds=args.poll_interval_seconds,
        )

        print("[8/8] Decision received:", flush=True)
        print(json.dumps(decided.body, indent=2), flush=True)
        _validate_final_state(decided, expected_decision=args.expected_decision)

        clicked_url = ""
        if sys.stdin.isatty():
            clicked_url = input(
                "Optional: paste the exact clicked email link to verify one-time reuse (or press Enter to skip): "
            ).strip()
        else:
            print(
                "  non-interactive run: skipping optional one-time reuse prompt",
                flush=True,
            )
        if clicked_url:
            parsed = urllib_parse.urlparse(clicked_url)
            if not parsed.path:
                raise SmokeError("invalid URL pasted for one-time reuse check")
            reuse = _json_request(
                "POST",
                f"{args.api_base_url.rstrip('/')}{parsed.path}",
            )
            if reuse.status not in {409, 410}:
                raise SmokeError(
                    "expected reused/expired link to return 409 or 410, got "
                    f"{reuse.status}: {_detail(reuse)}"
                )
            print(
                f"  reuse check passed with status {reuse.status}",
                flush=True,
            )

        print("SUCCESS: email approval smoke test passed.", flush=True)
        return 0

    except SmokeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        if dashboard_access_token and api_key_id:
            revoke = _dashboard_request(
                "POST",
                args.api_base_url,
                dashboard_access_token,
                f"/v1/dashboard/api-keys/{api_key_id}/revoke",
            )
            if revoke.status == 200:
                print("  cleaned up temporary API key", flush=True)
            else:
                print(
                    f"  WARNING: failed to revoke temporary API key ({revoke.status}): {_detail(revoke)}",
                    flush=True,
                )


if __name__ == "__main__":
    raise SystemExit(main())
