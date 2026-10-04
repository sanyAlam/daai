-- Phase 1 governance schema

CREATE TABLE IF NOT EXISTS workspaces (
    id UUID PRIMARY KEY,
    workspace_key_hash CHAR(64) UNIQUE,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE workspaces
ADD COLUMN IF NOT EXISTS workspace_key_hash CHAR(64);

CREATE UNIQUE INDEX IF NOT EXISTS workspaces_workspace_key_hash_idx
ON workspaces (workspace_key_hash)
WHERE workspace_key_hash IS NOT NULL;

CREATE TABLE IF NOT EXISTS workspace_api_keys (
    id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    key_hash CHAR(64) NOT NULL,
    label TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS workspace_api_keys_workspace_hash_idx
ON workspace_api_keys (workspace_id, key_hash)
WHERE revoked_at IS NULL;

CREATE TABLE IF NOT EXISTS registered_actions (
    id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    action_name TEXT NOT NULL,
    policy_type TEXT NOT NULL CHECK (
        policy_type IN (
            'always_allow',
            'always_require_approval',
            'require_approval_above_amount',
            'always_block'
        )
    ),
    policy_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(workspace_id, action_name)
);

CREATE TABLE IF NOT EXISTS action_runs (
    id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    registered_action_id UUID REFERENCES registered_actions(id) ON DELETE SET NULL,
    action_name TEXT NOT NULL,
    idempotency_key TEXT,
    idempotency_payload_hash CHAR(64),
    governance_status TEXT NOT NULL CHECK (
        governance_status IN (
            'allowed',
            'pending_approval',
            'approved',
            'rejected',
            'blocked'
        )
    ),
    execution_status TEXT NOT NULL CHECK (
        execution_status IN (
            'not_executed',
            'awaiting_execution_report',
            'executed',
            'failed'
        )
    ),
    governance_reason TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    policy_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    execution_result JSONB NOT NULL DEFAULT '{}'::jsonb,
    execution_error TEXT,
    execution_reported_at TIMESTAMPTZ,
    executed_at TIMESTAMPTZ,
    failed_at TIMESTAMPTZ,
    requested_at TIMESTAMPTZ NOT NULL,
    decided_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE action_runs
ADD COLUMN IF NOT EXISTS execution_result JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE action_runs
ADD COLUMN IF NOT EXISTS execution_error TEXT;

ALTER TABLE action_runs
ADD COLUMN IF NOT EXISTS execution_reported_at TIMESTAMPTZ;

ALTER TABLE action_runs
ADD COLUMN IF NOT EXISTS executed_at TIMESTAMPTZ;

ALTER TABLE action_runs
ADD COLUMN IF NOT EXISTS failed_at TIMESTAMPTZ;

ALTER TABLE action_runs
ADD COLUMN IF NOT EXISTS idempotency_payload_hash CHAR(64);

CREATE UNIQUE INDEX IF NOT EXISTS action_runs_idempotency_unique_idx
ON action_runs (workspace_id, action_name, idempotency_key)
WHERE idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS action_runs_workspace_created_idx
ON action_runs (workspace_id, created_at DESC);

CREATE TABLE IF NOT EXISTS governance_receipts (
    id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    action_run_id UUID NOT NULL REFERENCES action_runs(id) ON DELETE CASCADE,
    outcome TEXT NOT NULL CHECK (outcome IN ('allowed', 'blocked', 'approved', 'rejected')),
    reason TEXT NOT NULL,
    policy_type TEXT NOT NULL,
    policy_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(action_run_id)
);

CREATE INDEX IF NOT EXISTS governance_receipts_workspace_created_idx
ON governance_receipts (workspace_id, created_at DESC);
