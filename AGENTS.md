# AGENTS.md — DAAI Console

## Project identity

DAAI Console is a Python-first action governance platform for AI consultants.

The MVP proves one thing:

An AI consultant can add DAAI to a client’s AI automation so risky registered agent actions are intercepted before execution, governed by policy, approved or rejected by the client when needed, and recorded with receipts.

## Core product boundary

DAAI does not magically intercept arbitrary code.

DAAI performs cooperative pre-execution interception for registered actions.

Developer app owns:
- Real execution
- Local business logic
- Executor functions
- External integrations
- Cron/worker trigger

DAAI owns:
- Proposal
- Deterministic policy evaluation
- Approval flow
- Status tracking
- Governance receipts
- Execution result tracking

Never execute user callbacks inside intercept().

## Repo structure

Use this monorepo structure:

daai-console/
  apps/
    api/          # FastAPI backend
    dashboard/    # Next.js dashboard
  packages/
    daai-python/  # Python SDK
  docs/
    mvp.md
    architecture.md

## Locked stack

Frontend:
- Next.js
- Tailwind
- Vercel

Backend:
- Python
- FastAPI
- GCP Cloud Run

Database/Auth:
- Supabase Postgres
- Supabase Auth

SDK:
- Python first

Email:
- Resend, Postmark, or SendGrid

## Implementation priority

Build by technical depth, not by feature surface.

### Phase 1 — Governance engine

Build:
- FastAPI skeleton
- Supabase connection
- Tables
- Registered action lookup
- Deterministic policy evaluator
- Action run creation
- Governance receipt for allowed/blocked actions

Do not build dashboard polish yet.

### Phase 2 — Python SDK low-level client

Build:
- DaaiClient
- intercept()
- status()
- report_executed()
- report_failed()
- Typed response objects
- Tests

### Phase 3 — Human approval flow

Build:
- Approval tokens
- Reject tokens
- Approval/rejection API
- Approval email
- Simple approve/reject pages
- Governance receipt after approval/rejection

### Phase 4 — SDK runtime layer

Build:
- PendingActionManager
- DaaiActionRunner
- SQLitePendingStore
- InMemoryPendingStore
- runner.when_executable()
- runner.run_pending_once()

### Phase 5 — Minimal dashboard

Build:
- Workspace setup
- Registered actions
- Action run list
- Action run detail
- Receipt section inside action run detail

Do not build separate receipt pages in early MVP.

### Phase 6 — Deployment and hardening

Build:
- Hashed API keys
- Hashed approval tokens
- Idempotency keys
- Rate limiting
- Production env config
- Cloud Run deploy
- Vercel deploy

## Non-negotiable rules

1. Keep the MVP small.
2. Do not add MCP integration.
3. Do not add WhatsApp approval.
4. Do not add Slack approval.
5. Do not add webhook continuation yet.
6. Do not add enterprise RBAC.
7. Do not build a complex policy engine.
8. Do not call LLMs during runtime policy evaluation.
9. Do not execute risky actions inside intercept().
10. Do not store plaintext API keys.

## Status model

Use two separate concepts.

### Governance status

- allowed
- pending_approval
- approved
- rejected
- blocked

### Execution status

- not_executed
- awaiting_execution_report
- executed
- failed

Do not mix governance status with execution status.

## Policy model

MVP policy types:

- always_allow
- always_require_approval
- require_approval_above_amount
- always_block

Delay log_only unless specifically requested.

Runtime policy evaluation must be deterministic.

LLM can suggest policies only during setup, but the developer must confirm before activation.

## Idempotency

intercept() and manager.propose() must support an idempotency_key.

Example:

idempotency_key = "invoice-reminder:INV-1025"

Backend rule:

Same workspace + action + idempotency key returns the existing action run instead of creating a duplicate.

This prevents duplicate approval emails and duplicate execution.

## Python SDK rules

Required classes:
- DaaiClient
- PendingActionManager
- DaaiActionRunner
- SQLitePendingStore
- InMemoryPendingStore

Locked runner API:

runner.when_executable(
    action="mark_invoice_paid",
    run=mark_invoice_paid_executor,
)

runner.run_pending_once()

The safe path should be the easiest path.

## Backend rules

FastAPI owns:
- API key validation
- Workspace key validation
- Registered action lookup
- Policy evaluation
- Action run lifecycle
- Approval token generation/validation
- Email sending
- Receipt generation
- Execution result update

Every workspace query must enforce workspace isolation.

API keys must be stored hashed.

Approval tokens must be stored hashed.

Approval/rejection tokens must be:
- Random
- One-time use
- Expiry-based
- Bound to action run
- Free of sensitive data in the URL

## Dashboard rules

Keep dashboard minimal.

Early MVP pages:
- /
- /login
- /dashboard
- /dashboard/workspaces/[workspaceId]/setup
- /dashboard/workspaces/[workspaceId]/actions
- /dashboard/workspaces/[workspaceId]/runs
- /dashboard/workspaces/[workspaceId]/runs/[actionRunId]
- /approve/[token]
- /reject/[token]

Show receipt information inside action run detail.

Avoid separate receipt pages until later.

## Testing rules

Prioritize tests around the golden path:

SDK propose
→ backend evaluates policy
→ approval email/token created
→ client approves
→ SDK runner sees executable
→ local executor runs
→ SDK reports executed
→ receipt updates

Backend tests must cover:
- Policy evaluation
- Unknown action blocked
- Allowed action creates receipt
- Approval-required action creates token
- Approve token updates status
- Reject token updates status
- Status endpoint returns executable correctly
- Report executed updates execution fields
- Report failed updates execution fields
- Idempotency key prevents duplicate action runs

SDK tests must cover:
- Response parsing
- Pending action storage
- SQLite persistence
- Runner only executes approved/allowed actions
- Runner never executes rejected/blocked actions
- Execution success is reported
- Execution failure is reported

## Coding style

Prefer:
- Simple code
- Clear names
- Small modules
- Explicit types
- Deterministic behavior
- Boring, reliable architecture

Avoid:
- Clever abstractions
- Premature plugin systems
- Broad platform features
- Speculative future architecture
- Unnecessary dependencies

## Product tone

DAAI should feel:
- Trustworthy
- Practical
- Developer-friendly
- Audit-ready
- Calm and professional

Avoid hype.

Do not describe DAAI as fully autonomous agent security.

Describe it as:

A cooperative governance layer for registered agent actions.

## Current build target

The first working demo should prove:

An AI finance/admin agent proposes a risky action, DAAI pauses it, the client approves by email, the Python runner executes it, and the dashboard shows the full action story with a receipt.
