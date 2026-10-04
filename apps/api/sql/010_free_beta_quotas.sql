-- Free beta quota and abuse-protection schema

ALTER TABLE profiles
ADD COLUMN IF NOT EXISTS plan TEXT NOT NULL DEFAULT 'free';

UPDATE profiles
SET plan = 'free'
WHERE plan IS NULL OR plan = '';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'profiles_plan_check'
    ) THEN
        ALTER TABLE profiles
        ADD CONSTRAINT profiles_plan_check
        CHECK (plan IN ('free'));
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS approval_email_events (
    id UUID PRIMARY KEY,
    owner_user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    action_run_id UUID NOT NULL REFERENCES action_runs(id) ON DELETE CASCADE,
    email_count INTEGER NOT NULL CHECK (email_count > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS approval_email_events_owner_created_idx
ON approval_email_events (owner_user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS approval_email_events_workspace_created_idx
ON approval_email_events (workspace_id, created_at DESC);

CREATE TABLE IF NOT EXISTS rate_limit_events (
    id UUID PRIMARY KEY,
    key_type TEXT NOT NULL,
    key_value_hash CHAR(64) NOT NULL,
    endpoint TEXT NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    window_seconds INTEGER NOT NULL CHECK (window_seconds > 0),
    request_count INTEGER NOT NULL DEFAULT 0 CHECK (request_count >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (
        key_type,
        key_value_hash,
        endpoint,
        window_start,
        window_seconds
    )
);

CREATE INDEX IF NOT EXISTS rate_limit_events_updated_idx
ON rate_limit_events (updated_at DESC);
