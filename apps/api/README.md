# DAAI API (Phase 3)

FastAPI governance engine for cooperative interception of registered actions.

## Run API

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

## SDK Endpoints

- `POST /v1/sdk/intercept`
- `GET /v1/sdk/action-runs/{action_run_id}/status`
- `POST /v1/sdk/action-runs/{action_run_id}/report-executed`
- `POST /v1/sdk/action-runs/{action_run_id}/report-failed`

## Public Approval Endpoints

- `POST /v1/public/approve/{token}`
- `POST /v1/public/reject/{token}`

## Dashboard Read Endpoints

- `GET /v1/dashboard/workspaces`
- `POST /v1/dashboard/workspaces`
- `GET /v1/dashboard/workspaces/{workspace_id}`
- `GET /v1/dashboard/workspaces/{workspace_id}/actions`
- `POST /v1/dashboard/workspaces/{workspace_id}/actions`
- `POST /v1/workspaces/{workspace_id}/actions/suggest-policy`
- `GET /v1/dashboard/workspaces/{workspace_id}/runs`
- `GET /v1/dashboard/workspaces/{workspace_id}/runs/{action_run_id}`

Dashboard auth contract:
- `Authorization: Bearer <SUPABASE_ACCESS_TOKEN>`

SDK auth contract (unchanged):
- `Authorization: Bearer <DAAI_API_KEY>`
- `X-DAAI-Workspace-Key: <DAAI_WORKSPACE_KEY>`

## Local Postgres Dev Setup

1. Start local Postgres from repo root:

```bash
docker compose up -d postgres
docker compose ps
```

2. Create local env file:

```bash
cd apps/api
cp .env.example .env
```

3. Apply schema:

```bash
cd /Users/sanyalam/Documents/daai-console
docker compose exec -T postgres psql -U daai -d daai_console < apps/api/sql/001_phase1_governance.sql
docker compose exec -T postgres psql -U daai -d daai_console < apps/api/sql/002_phase3_human_approval.sql
docker compose exec -T postgres psql -U daai -d daai_console < apps/api/sql/003_phase5_dashboard_auth.sql
docker compose exec -T postgres psql -U daai -d daai_console < apps/api/sql/004_phase5_workspace_onboarding.sql
docker compose exec -T postgres psql -U daai -d daai_console < apps/api/sql/005_phase5_key_management.sql
docker compose exec -T postgres psql -U daai -d daai_console < apps/api/sql/006_phase5_6d_approval_completion.sql
docker compose exec -T postgres psql -U daai -d daai_console < apps/api/sql/007_self_serve_action_registration.sql
docker compose exec -T postgres psql -U daai -d daai_console < apps/api/sql/008_idempotency_payload_hash.sql
docker compose exec -T postgres psql -U daai -d daai_console < apps/api/sql/009_policy_suggestions.sql
```

4. Export API env and run server:

```bash
cd /Users/sanyalam/Documents/daai-console/apps/api
set -a
source .env
set +a
uvicorn app.main:app --reload
```

## Demo Seed Fixture

```bash
cd apps/api
set -a
source .env
set +a
python scripts/seed_phase1_demo.py
```

This seed now creates:
- Workspace: `Demo Finance Workspace` (client: `Demo Finance Client`)
- Registered actions: `pay_vendor`, `send_invoice_reminder`, `mark_invoice_paid`, `wire_transfer`
- Sample runs across governance/execution states with receipts for final governance outcomes

The script prints dashboard env placeholders plus SDK smoke-test credentials:

```bash
DAAI_API_BASE_URL=http://127.0.0.1:8000
DAAI_SUPABASE_URL=...
DAAI_SUPABASE_ANON_KEY=...
DAAI_SDK_API_KEY=...
DAAI_SDK_WORKSPACE_KEY=...
```

Required env:
- `DAAI_DATABASE_URL`
- `DAAI_SUPABASE_URL` (project URL, used for issuer validation and JWKS verification)
- `DAAI_SUPABASE_JWT_SECRET` (legacy JWT secret for HS256 projects; for `sb_secret_...` / `sb_publishable_...` setups, this value is also used for `/auth/v1/user` fallback verification)

Optional env:
- `DAAI_API_KEY_PEPPER` (defaults to `dev-only-change-me`)
- `DAAI_WORKSPACE_KEY_PEPPER` (defaults to `dev-only-change-me`)
- `DAAI_APPROVAL_TOKEN_PEPPER` (defaults to `dev-only-change-me`)
- `DAAI_APPROVAL_TOKEN_TTL_SECONDS` (defaults to `86400`)
- `DAAI_PUBLIC_BASE_URL` (defaults to `http://127.0.0.1:8000`)
- `DAAI_DASHBOARD_BASE_URL` (defaults to `http://127.0.0.1:3000`; approval emails link to `/approve/{token}`, `/reject/{token}`, `/block/{token}` on this base URL)
- `DAAI_APPROVAL_EMAIL_PROVIDER` (`log` or `resend`; defaults to `log`)
- `DAAI_APPROVAL_EMAIL_FROM` (sender used for approval emails; defaults to `no-reply@daai.local`)
- `DAAI_RESEND_API_KEY` (required when `DAAI_APPROVAL_EMAIL_PROVIDER=resend`)
- `DAAI_OPEN_AI_API_KEY` (server-side key for setup-time policy suggestions)
- `DAAI_POLICY_MODEL` (defaults to `gpt-5.4-mini`)
- `DAAI_DEV_APPROVAL_LINK_LOGGING_ENABLED` (defaults to `true`)
- `DAAI_DEV_AUTO_LINK_SEEDED_WORKSPACE` (defaults to `true`)
- `DAAI_DEV_SEEDED_WORKSPACE_ID` (defaults to `11111111-1111-1111-1111-111111111111`)
- `DAAI_DEMO_API_KEY` (if omitted, a random key is generated and printed)
- `DAAI_DEMO_WORKSPACE_KEY` (if omitted, a random key is generated and printed)
- `DAAI_DEMO_DASHBOARD_USER_ID` (optional; links seeded workspace to this Supabase user UUID)
- `DAAI_DEMO_DASHBOARD_USER_EMAIL` (optional profile email for linked user)

## Quick Live Intercept Check

After seeding, use the printed `workspace_key` and `api_key`:

```bash
curl -sS -X POST http://127.0.0.1:8000/v1/sdk/intercept \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <seeded_api_key>" \
  -H "X-DAAI-Workspace-Key: <seeded_workspace_key>" \
  -d '{
    "action": "pay_vendor",
    "payload": {"amount": 9000, "vendor_id": "VENDOR-42"},
    "idempotency_key": "demo:pay_vendor:VENDOR-42:9000"
  }'
```
