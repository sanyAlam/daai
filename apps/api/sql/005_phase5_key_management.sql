-- Phase 5.6B key management

ALTER TABLE workspace_api_keys
ADD COLUMN IF NOT EXISTS name TEXT;

ALTER TABLE workspace_api_keys
ADD COLUMN IF NOT EXISTS key_prefix TEXT;

ALTER TABLE workspace_api_keys
ADD COLUMN IF NOT EXISTS created_by UUID;

ALTER TABLE workspace_api_keys
ADD COLUMN IF NOT EXISTS last_used_at TIMESTAMPTZ;

UPDATE workspace_api_keys
SET name = COALESCE(NULLIF(name, ''), COALESCE(NULLIF(label, ''), 'API key'))
WHERE name IS NULL
   OR name = '';

UPDATE workspace_api_keys
SET key_prefix = COALESCE(NULLIF(key_prefix, ''), 'daai_sk_')
WHERE key_prefix IS NULL
   OR key_prefix = '';

CREATE INDEX IF NOT EXISTS workspace_api_keys_workspace_created_idx
ON workspace_api_keys (workspace_id, created_at DESC);

CREATE INDEX IF NOT EXISTS workspace_api_keys_created_by_idx
ON workspace_api_keys (created_by);
