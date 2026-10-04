-- Phase 5 self-serve action registration

ALTER TABLE registered_actions
ADD COLUMN IF NOT EXISTS title TEXT NOT NULL DEFAULT '';

ALTER TABLE registered_actions
ADD COLUMN IF NOT EXISTS description TEXT NOT NULL DEFAULT '';

ALTER TABLE registered_actions
ADD COLUMN IF NOT EXISTS risk_level TEXT NOT NULL DEFAULT 'medium';

ALTER TABLE registered_actions
ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

UPDATE registered_actions
SET title = INITCAP(REPLACE(action_name, '_', ' '))
WHERE title = '';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'registered_actions_risk_level_check'
    ) THEN
        ALTER TABLE registered_actions
        ADD CONSTRAINT registered_actions_risk_level_check
        CHECK (risk_level IN ('low', 'medium', 'high', 'critical'));
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS registered_actions_workspace_active_idx
ON registered_actions (workspace_id, is_active, action_name);
