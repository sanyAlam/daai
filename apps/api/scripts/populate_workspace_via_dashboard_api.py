from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _require_env(*names: str) -> str:
    for name in names:
        value = os.environ.get(name)
        if value and value.strip():
            return value.strip()
    joined = ", ".join(names)
    raise RuntimeError(f"missing required env: {joined}")


def _json_request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    timeout: int = 30,
) -> tuple[int, dict[str, Any] | list[Any]]:
    req_headers = dict(headers or {})
    data: bytes | None = None

    if payload is not None:
        req_headers.setdefault("Content-Type", "application/json")
        data = json.dumps(payload).encode("utf-8")

    req = urllib_request.Request(
        url=url,
        method=method,
        headers=req_headers,
        data=data,
    )
    try:
        with urllib_request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            body = json.loads(raw) if raw else {}
            return response.status, body
    except urllib_error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        try:
            body = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            body = {"detail": raw}
        return exc.code, body


def _error_detail(body: dict[str, Any] | list[Any]) -> str:
    if isinstance(body, dict):
        for key in ("detail", "msg", "error_description", "error", "message"):
            value = body.get(key)
            if isinstance(value, str) and value:
                return value
        return json.dumps(body)
    return json.dumps(body)


def _login(
    *,
    supabase_url: str,
    supabase_anon_key: str,
    email: str,
    password: str,
) -> tuple[str, str]:
    status, body = _json_request(
        "POST",
        f"{supabase_url.rstrip('/')}/auth/v1/token?grant_type=password",
        headers={
            "apikey": supabase_anon_key,
            "Content-Type": "application/json",
        },
        payload={
            "email": email,
            "password": password,
        },
    )
    if status != 200 or not isinstance(body, dict):
        raise RuntimeError(f"login failed ({status}): {_error_detail(body)}")

    access_token = body.get("access_token")
    user_obj = body.get("user")
    user_id = user_obj.get("id") if isinstance(user_obj, dict) else None
    if not isinstance(access_token, str) or not access_token:
        raise RuntimeError("login succeeded but access_token is missing")
    if not isinstance(user_id, str) or not user_id:
        raise RuntimeError("login succeeded but user id is missing")
    return access_token, user_id


def main() -> int:
    _load_env_file(REPO_ROOT / ".env.staging.local")
    _load_env_file(REPO_ROOT / "apps/api/.env.smoke.email")

    parser = argparse.ArgumentParser(
        description="Populate workspace visibility via dashboard APIs only.",
    )
    parser.add_argument(
        "--api-base-url",
        default=os.environ.get("DAAI_API_BASE_URL", "http://127.0.0.1:8000"),
    )
    parser.add_argument(
        "--workspace-name",
        default="Email Smoke Test Workspace",
    )
    parser.add_argument(
        "--client-name",
        default="Email Smoke Test Client",
    )
    parser.add_argument(
        "--approver-email",
        default=os.environ.get("DAAI_STAGING_APPROVER_EMAIL", "sanyalam2k20@gmail.com"),
    )
    parser.add_argument(
        "--email",
        default=_require_env("DAAI_STAGING_LOGIN_EMAIL", "DAAI_SMOKE_DASHBOARD_EMAIL"),
    )
    parser.add_argument(
        "--password",
        default=_require_env("DAAI_STAGING_LOGIN_PASSWORD", "DAAI_SMOKE_DASHBOARD_PASSWORD"),
    )
    parser.add_argument(
        "--supabase-url",
        default=_require_env("DAAI_SUPABASE_URL"),
    )
    parser.add_argument(
        "--supabase-anon-key",
        default=_require_env("DAAI_SUPABASE_ANON_KEY"),
    )
    args = parser.parse_args()

    approver_email = args.approver_email.strip().lower()
    if not approver_email:
        raise RuntimeError("approver email is required")

    token, user_id = _login(
        supabase_url=args.supabase_url,
        supabase_anon_key=args.supabase_anon_key,
        email=args.email,
        password=args.password,
    )
    auth_headers = {"Authorization": f"Bearer {token}"}

    status, ws_payload = _json_request(
        "GET",
        f"{args.api_base_url.rstrip('/')}/v1/dashboard/workspaces",
        headers=auth_headers,
    )
    if status != 200 or not isinstance(ws_payload, list):
        raise RuntimeError(f"workspace list failed ({status}): {_error_detail(ws_payload)}")

    workspace = None
    for item in ws_payload:
        if isinstance(item, dict) and item.get("name") == args.workspace_name:
            workspace = item
            break

    workspace_created = False
    if workspace is None:
        create_status, create_payload = _json_request(
            "POST",
            f"{args.api_base_url.rstrip('/')}/v1/dashboard/workspaces",
            headers=auth_headers,
            payload={
                "workspace_name": args.workspace_name,
                "client_name": args.client_name,
            },
        )
        if create_status != 200 or not isinstance(create_payload, dict):
            raise RuntimeError(
                f"workspace create failed ({create_status}): {_error_detail(create_payload)}"
            )
        workspace = create_payload
        workspace_created = True

    workspace_id = workspace.get("id") if isinstance(workspace, dict) else None
    if not isinstance(workspace_id, str) or not workspace_id:
        raise RuntimeError("workspace id missing after ensure")

    settings_status, settings_payload = _json_request(
        "POST",
        f"{args.api_base_url.rstrip('/')}/v1/dashboard/workspaces/{workspace_id}/approval-settings",
        headers=auth_headers,
        payload={
            "approval_emails": [approver_email],
            "approval_link_ttl_minutes": 15,
        },
    )
    if settings_status != 200:
        raise RuntimeError(
            f"approval settings update failed ({settings_status}): {_error_detail(settings_payload)}"
        )

    actions_status, actions_payload = _json_request(
        "GET",
        f"{args.api_base_url.rstrip('/')}/v1/dashboard/workspaces/{workspace_id}/actions",
        headers=auth_headers,
    )
    runs_status, runs_payload = _json_request(
        "GET",
        f"{args.api_base_url.rstrip('/')}/v1/dashboard/workspaces/{workspace_id}/runs?page=1&page_size=50",
        headers=auth_headers,
    )

    action_names: list[str] = []
    if actions_status == 200 and isinstance(actions_payload, list):
        action_names = [
            item.get("action_name")
            for item in actions_payload
            if isinstance(item, dict) and isinstance(item.get("action_name"), str)
        ]

    output = {
        "login_succeeded": True,
        "user_id": user_id,
        "workspace_id": workspace_id,
        "workspace_name": args.workspace_name,
        "workspace_created": workspace_created,
        "approver_email": approver_email,
        "actions_endpoint_status": actions_status,
        "runs_endpoint_status": runs_status,
        "actions_visible": action_names,
        "actions_policy_create_supported_by_dashboard_api": False,
        "note": "Current API exposes action list/read but not action/policy create endpoints.",
    }
    if isinstance(runs_payload, dict):
        output["runs_total"] = runs_payload.get("total")
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
