-- Phase 5.6A.1 workspace onboarding fields

ALTER TABLE workspaces
ADD COLUMN IF NOT EXISTS client_name TEXT;

ALTER TABLE workspaces
ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'active';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'workspaces_status_check'
    ) THEN
        ALTER TABLE workspaces
        ADD CONSTRAINT workspaces_status_check
        CHECK (status IN ('active', 'archived'));
    END IF;
END
$$;
