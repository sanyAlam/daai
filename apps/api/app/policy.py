from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from app.domain import GovernanceStatus, PolicyDecision, PolicyType


class PolicyEvaluationError(ValueError):
    """Raised when a stored policy cannot be evaluated deterministically."""


def evaluate_policy(
    policy_type: str,
    policy_config: dict[str, Any],
    payload: dict[str, Any],
) -> PolicyDecision:
    if policy_type == PolicyType.LOG_ONLY.value:
        return PolicyDecision(
            governance_status=GovernanceStatus.ALLOWED,
            governance_reason="policy_log_only",
            policy_snapshot={
                "policy_type": policy_type,
                "policy_config": policy_config,
            },
        )

    if policy_type == PolicyType.ALWAYS_ALLOW.value:
        return PolicyDecision(
            governance_status=GovernanceStatus.ALLOWED,
            governance_reason="policy_always_allow",
            policy_snapshot={
                "policy_type": policy_type,
                "policy_config": policy_config,
            },
        )

    if policy_type == PolicyType.ALWAYS_BLOCK.value:
        return PolicyDecision(
            governance_status=GovernanceStatus.BLOCKED,
            governance_reason="policy_always_block",
            policy_snapshot={
                "policy_type": policy_type,
                "policy_config": policy_config,
            },
        )

    if policy_type == PolicyType.ALWAYS_REQUIRE_APPROVAL.value:
        return PolicyDecision(
            governance_status=GovernanceStatus.PENDING_APPROVAL,
            governance_reason="policy_requires_approval",
            policy_snapshot={
                "policy_type": policy_type,
                "policy_config": policy_config,
            },
        )

    if policy_type == PolicyType.REQUIRE_APPROVAL_ABOVE_AMOUNT.value:
        threshold = _read_decimal(policy_config.get("threshold"))
        amount_field = policy_config.get("amount_field", "amount")
        amount_value = _read_from_payload(payload, amount_field)
        amount = _read_decimal(amount_value)

        if threshold is None:
            raise PolicyEvaluationError("threshold is required for amount-based policy")

        if amount is None:
            return PolicyDecision(
                governance_status=GovernanceStatus.PENDING_APPROVAL,
                governance_reason="policy_amount_missing_requires_approval",
                policy_snapshot={
                    "policy_type": policy_type,
                    "policy_config": policy_config,
                    "evaluated_amount_field": amount_field,
                    "evaluated_amount": None,
                    "threshold": str(threshold),
                },
            )

        if amount > threshold:
            status = GovernanceStatus.PENDING_APPROVAL
            reason = "policy_amount_above_threshold"
        else:
            status = GovernanceStatus.ALLOWED
            reason = "policy_amount_within_threshold"

        return PolicyDecision(
            governance_status=status,
            governance_reason=reason,
            policy_snapshot={
                "policy_type": policy_type,
                "policy_config": policy_config,
                "evaluated_amount_field": amount_field,
                "evaluated_amount": str(amount),
                "threshold": str(threshold),
            },
        )

    if policy_type == PolicyType.REQUIRE_APPROVAL_WHEN_EXTERNAL_RECIPIENT.value:
        signal_field = _external_recipient_signal_field(payload)
        return _signal_policy_decision(
            policy_type=policy_type,
            policy_config=policy_config,
            signal_field=signal_field,
            pending_reason="policy_external_recipient_requires_approval",
            allowed_reason="policy_external_recipient_not_detected",
        )

    if policy_type == PolicyType.REQUIRE_APPROVAL_WHEN_NEW_RECIPIENT.value:
        signal_field = _first_true_field(
            payload,
            ["is_new_recipient", "new_recipient", "recipient_is_new"],
        )
        return _signal_policy_decision(
            policy_type=policy_type,
            policy_config=policy_config,
            signal_field=signal_field,
            pending_reason="policy_new_recipient_requires_approval",
            allowed_reason="policy_new_recipient_not_detected",
        )

    if policy_type == PolicyType.REQUIRE_APPROVAL_WHEN_NOT_REVERSIBLE.value:
        signal_field = _first_true_field(payload, ["not_reversible"])
        if signal_field is None and payload.get("reversible") is False:
            signal_field = "reversible"
        return _signal_policy_decision(
            policy_type=policy_type,
            policy_config=policy_config,
            signal_field=signal_field,
            pending_reason="policy_not_reversible_requires_approval",
            allowed_reason="policy_not_reversible_not_detected",
        )

    if policy_type == PolicyType.REQUIRE_APPROVAL_WHEN_DESTRUCTIVE.value:
        signal_field = _first_true_field(payload, ["destructive", "is_destructive"])
        return _signal_policy_decision(
            policy_type=policy_type,
            policy_config=policy_config,
            signal_field=signal_field,
            pending_reason="policy_destructive_requires_approval",
            allowed_reason="policy_destructive_not_detected",
        )

    raise PolicyEvaluationError(f"unsupported policy type: {policy_type}")


def _read_from_payload(payload: dict[str, Any], field: str) -> Any:
    if "." not in field:
        return payload.get(field)

    current: Any = payload
    for key in field.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _read_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None

    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _signal_policy_decision(
    policy_type: str,
    policy_config: dict[str, Any],
    signal_field: str | None,
    pending_reason: str,
    allowed_reason: str,
) -> PolicyDecision:
    signal_detected = signal_field is not None
    return PolicyDecision(
        governance_status=(
            GovernanceStatus.PENDING_APPROVAL
            if signal_detected
            else GovernanceStatus.ALLOWED
        ),
        governance_reason=pending_reason if signal_detected else allowed_reason,
        policy_snapshot={
            "policy_type": policy_type,
            "policy_config": policy_config,
            "evaluated_signal_field": signal_field,
            "evaluated_signal_detected": signal_detected,
        },
    )


def _external_recipient_signal_field(payload: dict[str, Any]) -> str | None:
    signal_field = _first_true_field(payload, ["external_recipient"])
    if signal_field is not None:
        return signal_field

    for field in [
        "recipient_email",
        "customer_email",
        "supplier_email",
        "to_email",
        "email",
    ]:
        value = payload.get(field)
        if isinstance(value, str) and "@" in value and value.strip():
            return field
    return None


def _first_true_field(payload: dict[str, Any], fields: list[str]) -> str | None:
    for field in fields:
        if payload.get(field) is True:
            return field
    return None
