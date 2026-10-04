"""Exercise real governance routes locally; persistence and execution are synthetic."""
from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api/tests"))

from fastapi.testclient import TestClient

from app.config import Settings
from app.hashing import hash_api_key, hash_workspace_key
from app.main import create_app
from daai import DaaiActionRunner, DaaiClient, InMemoryPendingStore, PendingActionManager
from fakes import InMemoryGovernanceRepository


class LocalApprovalCapture:
    def __init__(self) -> None:
        self.links: list[object] = []

    def notify_pending_approval(self, links: object) -> None:
        self.links.append(links)

    def token(self, decision: str) -> str:
        return getattr(self.links[-1], f"{decision}_url").rsplit("/", 1)[1]


def main() -> None:
    workspace_id = UUID("11111111-1111-1111-1111-111111111111")
    api_key, workspace_key, pepper = "synthetic-api-key", "synthetic-workspace-key", "demo-only"
    repository = InMemoryGovernanceRepository()
    repository.add_workspace_key_hash(workspace_id, hash_workspace_key(workspace_key, pepper))
    repository.add_api_key_hash(workspace_id, hash_api_key(api_key, pepper))
    for action, policy in (
        ("remind_allowed", "always_allow"),
        ("remind_approved", "always_require_approval"),
        ("remind_rejected", "always_require_approval"),
        ("remind_blocked", "always_block"),
    ):
        repository.add_registered_action(workspace_id, action, policy)

    capture = LocalApprovalCapture()
    app = create_app(
        repository=repository,
        settings=Settings(
            database_url=None, supabase_url=None, supabase_jwt_secret=None,
            api_key_pepper=pepper, workspace_key_pepper=pepper,
            approval_token_pepper=pepper, resend_api_key=None, open_ai_api_key=None,
            public_base_url="http://testserver", dashboard_base_url="http://testserver",
            approval_email_provider="log", dev_approval_link_logging_enabled=False,
            dev_auto_link_seeded_workspace=False, admin_emails="", cors_origins="",
        ),
        approval_link_notifier=capture,
    )
    executed: list[str] = []

    def local_executor(payload: dict) -> dict:
        executed.append(payload["invoice_id"])
        return {"simulation": True, "invoice_id": payload["invoice_id"]}

    print("DAAI Console | isolated local demonstration")
    print("Real SDK + FastAPI logic; in-memory storage; simulated executor; no email.")
    with TestClient(app) as http:
        client = DaaiClient("http://testserver", api_key, workspace_key, http_client=http)
        store = InMemoryPendingStore()
        manager = PendingActionManager(client, store)
        runner = DaaiActionRunner(client, store)
        for action in ("remind_allowed", "remind_approved", "remind_rejected", "remind_blocked"):
            runner.when_executable(action=action, run=local_executor)

        allowed = manager.propose("remind_allowed", {"invoice_id": "DEMO-001"}, "demo:allowed")
        assert allowed.executable
        client.report_executed(allowed.action_run_id, local_executor(allowed.payload))
        assert runner.run_pending_once() == 0
        assert client.status(allowed.action_run_id).execution_status.value == "executed"
        print("1. Allowed       -> simulated execution reported")

        pending = manager.propose("remind_approved", {"invoice_id": "DEMO-002"}, "demo:approved")
        assert not pending.executable and runner.run_pending_once() == 0
        print("2. Pending       -> executor held; no side effect")
        approval_token = capture.token("approve")
        response = http.post(f"/v1/public/approve/{approval_token}")
        assert response.status_code == 200
        assert runner.run_pending_once() == 1
        state = client.status(pending.action_run_id)
        assert state.governance_status.value == "approved"
        assert state.execution_status.value == "executed" and state.receipt is not None
        assert state.receipt.outcome == "approved"
        print("3. Approved      -> local executor ran; receipt available")

        rejected = manager.propose("remind_rejected", {"invoice_id": "DEMO-003"}, "demo:rejected")
        assert http.post(f"/v1/public/reject/{capture.token('reject')}").status_code == 200
        assert runner.run_pending_once() == 0
        assert not client.status(rejected.action_run_id).executable
        print("4. Rejected      -> executor never ran")

        blocked = manager.propose("remind_blocked", {"invoice_id": "DEMO-004"}, "demo:blocked")
        unknown = client.intercept("unregistered_action", {"invoice_id": "DEMO-005"})
        assert not blocked.executable and not unknown.executable
        assert runner.run_pending_once() == 0
        print("5. Blocked       -> blocked and unknown actions did not run")

        replay = client.intercept("remind_approved", {"invoice_id": "DEMO-002"}, "demo:approved")
        assert replay.action_run_id == pending.action_run_id and replay.idempotent_replay
        assert http.post(f"/v1/public/approve/{approval_token}").status_code == 404
        assert http.post("/v1/public/approve/invalid-demo-token").status_code == 404
        assert executed == ["DEMO-001", "DEMO-002"]
        print("6. Replay/tokens -> same run returned; reused/invalid tokens refused")
        print("PASS: 2 simulated executions; no premature execution; state discarded.")


if __name__ == "__main__":
    main()
