from app.domain import GovernanceStatus
from app.policy import evaluate_policy


def test_require_approval_above_amount_allows_below_threshold() -> None:
    decision = evaluate_policy(
        policy_type="require_approval_above_amount",
        policy_config={"threshold": 5000, "amount_field": "amount"},
        payload={"amount": 1200},
    )

    assert decision.governance_status == GovernanceStatus.ALLOWED
    assert decision.governance_reason == "policy_amount_within_threshold"


def test_require_approval_above_amount_requires_approval_when_missing_amount() -> None:
    decision = evaluate_policy(
        policy_type="require_approval_above_amount",
        policy_config={"threshold": 5000, "amount_field": "invoice.total"},
        payload={"invoice": {}},
    )

    assert decision.governance_status == GovernanceStatus.PENDING_APPROVAL
    assert decision.governance_reason == "policy_amount_missing_requires_approval"


def test_log_only_allows_action() -> None:
    decision = evaluate_policy(
        policy_type="log_only",
        policy_config={},
        payload={"note_id": "NOTE-1"},
    )

    assert decision.governance_status == GovernanceStatus.ALLOWED
    assert decision.governance_reason == "policy_log_only"


def test_external_recipient_policy_requires_approval_from_explicit_signal() -> None:
    decision = evaluate_policy(
        policy_type="require_approval_when_external_recipient",
        policy_config={},
        payload={"external_recipient": True},
    )

    assert decision.governance_status == GovernanceStatus.PENDING_APPROVAL
    assert decision.governance_reason == "policy_external_recipient_requires_approval"


def test_new_recipient_policy_requires_approval_from_explicit_signal() -> None:
    decision = evaluate_policy(
        policy_type="require_approval_when_new_recipient",
        policy_config={},
        payload={"is_new_recipient": True},
    )

    assert decision.governance_status == GovernanceStatus.PENDING_APPROVAL
    assert decision.governance_reason == "policy_new_recipient_requires_approval"


def test_not_reversible_policy_requires_approval_from_reversible_false() -> None:
    decision = evaluate_policy(
        policy_type="require_approval_when_not_reversible",
        policy_config={},
        payload={"reversible": False},
    )

    assert decision.governance_status == GovernanceStatus.PENDING_APPROVAL
    assert decision.governance_reason == "policy_not_reversible_requires_approval"


def test_destructive_policy_requires_approval_from_explicit_signal() -> None:
    decision = evaluate_policy(
        policy_type="require_approval_when_destructive",
        policy_config={},
        payload={"destructive": True},
    )

    assert decision.governance_status == GovernanceStatus.PENDING_APPROVAL
    assert decision.governance_reason == "policy_destructive_requires_approval"
