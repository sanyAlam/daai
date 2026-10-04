# DAAI Console: an explicit boundary before agent execution

Sany Alam built DAAI Console as an independent Python-first project in 2026.
The repository contains the backend, Python SDK, dashboard, database migrations,
tests, and deployment work. The original hosted beta has been discontinued.
This release preserves the implementation as an engineering portfolio archive.

## Problem

An automation can produce a plausible action while lacking authority to perform
it. A client needs a clear record of what was proposed, which rule applied,
whether a human approved it, and whether the application reported execution.
DAAI places an explicit cooperative gate before registered application actions.

## Design choices

**Deterministic policy at runtime.** Four small policy types keep decisions
explainable. Optional model suggestions belong to configuration time and must
be confirmed. They never authorize runtime execution.

**Governance is different from execution.** Approval means an action may run,
not that it ran successfully. Separate states make pending approvals and
execution failures visible in the same action story and receipt.

**The executor stays with the application.** The SDK submits proposals and polls
decisions. A runner calls application-supplied functions only when executable.
DAAI never receives the application's external-service credentials.

**Replay must match payload identity.** The backend scopes idempotency to
workspace and action and rejects conflicting payloads. Tests exercise replay
without duplicate runs and conflicting requests without mutation.

**Human decisions must be bound to one run.** Hashed, random, expiring decision
tokens avoid reusable credentials in the database. Tests cover invalid,
expired, reused, and conflicting decisions.

## Evidence and trade-offs

The safe demo executes actual SDK and FastAPI paths with synthetic data and
in-memory persistence. Unit coverage also exercises workspace authorization,
quotas, failure reporting, pending stores, and executor gating. These checks
do not establish PostgreSQL concurrency guarantees or production performance.
The full dashboard requires a separately configured Supabase Auth environment.

Cooperation is the main trust assumption: a developer can bypass the gate.
Execution reports are client-supplied, and an external side effect can happen
before its result is reported. Exactly-once external execution is not promised.
The project favors a narrow, inspectable workflow over a general security
platform. No customer counts, scale, uptime, or measured business gains are
claimed.

## Current presentation

The public domain serves a static source showcase and local demo walkthrough.
It does not host a writable admin console or resume the previous paid service.
