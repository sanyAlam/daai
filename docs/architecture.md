# Architecture (Phase 1)

DAAI Console Phase 1 provides a cooperative governance backend.

Flow:
1. Developer app calls `POST /v1/sdk/intercept` with `Authorization: Bearer <DAAI_API_KEY>`, `X-DAAI-Workspace-Key: <DAAI_WORKSPACE_KEY>`, action, payload, and optional idempotency key.
2. API resolves workspace from hashed workspace key and validates workspace-scoped hashed API key.
3. API looks up registered action policy.
4. Deterministic evaluator returns governance decision.
5. API stores action run with separate governance and execution status.
6. API writes governance receipt for `allowed` or `blocked` outcomes.
7. SDK checks status via `GET /v1/sdk/action-runs/{action_run_id}/status`.

Execution remains in the developer app and is outside `intercept()`.
