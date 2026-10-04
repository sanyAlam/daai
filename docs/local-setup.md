# Local setup

## Verified quick start: isolated workflow demonstration

Follow the root README with Python 3.11. `examples/local_demo.py` calls actual
SDK methods and FastAPI routes through Starlette's in-process test transport.
It uses the existing in-memory repository, captures synthetic approval links,
and simulates invoice reminders with a local function returning a dictionary.
No listener, database, Supabase account, network call, or email is required.

The demo asserts allowed, pending, approved, rejected, blocked and unknown
actions; prevents execution before approval; checks idempotent replay and
invalid/reused tokens; reports simulated execution; and checks the receipt.
All state disappears at process exit. Remove `.venv` to clean the dependencies.

## Full API and dashboard: bring your own development configuration

This path describes the existing architecture. A new PostgreSQL/Supabase
installation was not tested end to end for this source release. Do not interpret
the in-memory demo as evidence that these integrations have been verified.

Use an isolated development Supabase project for its PostgreSQL database and
Auth. The plain PostgreSQL compose service alone is insufficient: later SQL
migrations reference `auth.users` and Supabase roles. Do not apply them to a
production database.

1. Apply `apps/api/sql/001_*.sql` through `010_*.sql` in filename order to your
   development Supabase database. These are the original schema migrations.
2. Copy `apps/api/.env.example` to `apps/api/.env` and fill your own values.
   Required for the API: `DAAI_DATABASE_URL` and three distinct random secrets
   in `DAAI_API_KEY_PEPPER`, `DAAI_WORKSPACE_KEY_PEPPER`, and
   `DAAI_APPROVAL_TOKEN_PEPPER`. Dashboard auth additionally needs
   `DAAI_SUPABASE_URL` and the documented JWT verification configuration.
3. Use local origins: `DAAI_PUBLIC_BASE_URL=http://127.0.0.1:8000`,
   `DAAI_DASHBOARD_BASE_URL=http://localhost:3000`, and
   `DAAI_CORS_ORIGINS=http://localhost:3000`.
4. For local-only approval capture, set `DAAI_APPROVAL_EMAIL_PROVIDER=log` and
   explicitly enable `DAAI_DEV_APPROVAL_LINK_LOGGING_ENABLED=true`. These logs
   contain synthetic bearer decision links; keep them private. No email API
   key is required. Disable logging and auto-link shortcuts outside local dev.
5. Run `uvicorn app.main:app --app-dir apps/api --env-file apps/api/.env --host
   127.0.0.1 --port 8000` from the repository root. The optional `.env` loader
   requires `python -m pip install python-dotenv`.
6. Copy `apps/dashboard/.env.local.example` to `apps/dashboard/.env.local`,
   configure your Supabase URL and publishable/anon key, and set
   `DAAI_API_BASE_URL=http://127.0.0.1:8000`. Privileged database/JWT secrets
   must never be `NEXT_PUBLIC_` variables.
7. Set the Supabase Auth site URL to `http://localhost:3000` and allow the local
   signup/reset redirects. Create a development user, sign in, create a workspace
   and key, and register an action through the dashboard. Do not use old DAAI
   credentials or retired custom domains.
8. Run `npm ci` then `npm run dev` in `apps/dashboard`. Open localhost:3000.

Optional integrations: Resend for delivery and OpenAI for setup suggestions.
They are not required for the safe demo and can incur charges if configured.
The full application's defaults are not a production deployment recipe.
Dispose of the isolated development project or sample workspace after testing;
keep production data separate.
