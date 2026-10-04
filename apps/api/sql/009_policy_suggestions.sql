-- Setup-time policy suggestions and deterministic conditional policy types

ALTER TABLE registered_actions
DROP CONSTRAINT IF EXISTS registered_actions_policy_type_check;

ALTER TABLE registered_actions
ADD CONSTRAINT registered_actions_policy_type_check
CHECK (
    policy_type IN (
        'log_only',
        'always_allow',
        'always_require_approval',
        'require_approval_above_amount',
        'always_block',
        'require_approval_when_external_recipient',
        'require_approval_when_new_recipient',
        'require_approval_when_not_reversible',
        'require_approval_when_destructive'
    )
);
