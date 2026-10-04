# Release verification

Verified on 5 October 2026 using an isolated Python 3.11 environment and no
production credentials:

| Command | Actual outcome |
| --- | --- |
| `python -m pip install -e "apps/api[dev]" -e "packages/daai-python[dev]"` | Clean isolated install succeeded |
| `python examples/local_demo.py` | All workflow assertions passed; two simulated executions |
| `python -m pytest apps/api/tests -q` | 130 passed |
| `python -m pytest packages/daai-python/tests -q` | 24 passed |
| Companion SDK: `python -m pytest -q` | 25 passed |
| Dashboard: `npm run lint` | No errors or warnings |
| Dashboard: `npm run build` | Production compile and type checks passed with synthetic Supabase configuration |
| Dashboard: `npm audit --omit=dev` | Zero reported runtime vulnerabilities |

The API suite covers policy evaluation, approval expiry/reuse, workspace auth,
idempotency/payload conflict, quotas, execution reports, and receipts. The SDK
suites exercise parsing, storage, and executor gating; new regression cases
refuse missing or malformed execution permission.

Gitleaks 8.30.1 scanned the selected snapshot and original console/SDK history
with redacted reports. No secrets were reported in the selected public material.
Local environment secrets in the private checkout are excluded from the release.
The original private history is not being published. No real user data, approval
URLs, service-account files, or generated dashboard bundles are included.

The full npm audit retains seven high-severity development-tooling entries;
see SECURITY.md. Warnings also include short synthetic JWT keys in tests and
Starlette's evolving test transport. They do not use production credentials.

The demo substitutes persistence and email capture, and uses a simulated local
executor. It is not an external network deployment or a concurrency test.
Fresh Supabase database/auth setup, real email delivery, and an authenticated
browser workflow have not been verified in this release. The website is a
static showcase, not a public instance of the API or dashboard.
