-- Store the canonical request payload hash used for idempotency replay checks.

ALTER TABLE action_runs
ADD COLUMN IF NOT EXISTS idempotency_payload_hash CHAR(64);
