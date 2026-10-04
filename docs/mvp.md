# DAAI MVP

This repository starts with Phase 1: governance engine.

Scope currently implemented:
- FastAPI backend skeleton in `apps/api`
- Supabase/Postgres schema for workspaces, API keys, registered actions, action runs, and receipts
- Registered action lookup
- Deterministic policy evaluation
- Intercept/proposal flow that creates action runs
- Governance receipts for allowed/blocked outcomes
