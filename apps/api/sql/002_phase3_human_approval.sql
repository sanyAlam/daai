-- Phase 3 human approval schema

CREATE TABLE IF NOT EXISTS action_run_decision_tokens (
    id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    action_run_id UUID NOT NULL REFERENCES action_runs(id) ON DELETE CASCADE,
    token_type TEXT NOT NULL CHECK (token_type IN ('approve', 'reject')),
    token_hash CHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(action_run_id, token_type)
);

CREATE INDEX IF NOT EXISTS action_run_decision_tokens_token_hash_idx
ON action_run_decision_tokens (token_hash);

CREATE INDEX IF NOT EXISTS action_run_decision_tokens_workspace_run_idx
ON action_run_decision_tokens (workspace_id, action_run_id);
