-- Phase 5.6D approval completion

ALTER TABLE workspaces
ADD COLUMN IF NOT EXISTS approval_emails TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[];

ALTER TABLE workspaces
ADD COLUMN IF NOT EXISTS approval_link_ttl_minutes INTEGER NOT NULL DEFAULT 15;

UPDATE workspaces
SET approval_emails = ARRAY[]::TEXT[]
WHERE approval_emails IS NULL;

UPDATE workspaces
SET approval_link_ttl_minutes = 15
WHERE approval_link_ttl_minutes IS NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'workspaces_approval_link_ttl_minutes_check'
    ) THEN
        ALTER TABLE workspaces
        ADD CONSTRAINT workspaces_approval_link_ttl_minutes_check
        CHECK (approval_link_ttl_minutes >= 5 AND approval_link_ttl_minutes <= 1440);
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'workspaces_approval_emails_max_two_check'
    ) THEN
        ALTER TABLE workspaces
        ADD CONSTRAINT workspaces_approval_emails_max_two_check
        CHECK (COALESCE(cardinality(approval_emails), 0) <= 2);
    END IF;
END
$$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'action_run_decision_tokens_token_type_check'
    ) THEN
        ALTER TABLE action_run_decision_tokens
        DROP CONSTRAINT action_run_decision_tokens_token_type_check;
    END IF;

    ALTER TABLE action_run_decision_tokens
    ADD CONSTRAINT action_run_decision_tokens_token_type_check
    CHECK (token_type IN ('approve', 'reject', 'block'));
EXCEPTION
    WHEN duplicate_object THEN
        NULL;
END
$$;
