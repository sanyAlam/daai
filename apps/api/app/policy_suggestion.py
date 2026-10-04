from __future__ import annotations

import json
import logging
from typing import Any, Protocol

from app.schemas import PolicySuggestionResponse, SuggestActionPolicyRequest


logger = logging.getLogger("daai.policy_suggestion")

ALLOWED_POLICY_TYPES = [
    "log_only",
    "always_allow",
    "always_require_approval",
    "require_approval_above_amount",
    "always_block",
    "require_approval_when_external_recipient",
    "require_approval_when_new_recipient",
    "require_approval_when_not_reversible",
    "require_approval_when_destructive",
]
ALLOWED_RISK_LEVELS = ["low", "medium", "high", "critical"]

SYSTEM_MESSAGE = """You are helping configure deterministic approval policies for DAAI Console. DAAI is a pre-execution governance layer for registered agent actions. You do not make runtime decisions. Your job is only to suggest a safe, simple, deterministic policy during setup. You must only return valid JSON matching the schema. Do not invent policy types. Prefer conservative policies when the action has financial, external communication, destructive, privacy, compliance, or hard-to-reverse impact."""


class PolicySuggester(Protocol):
    def suggest(self, request: SuggestActionPolicyRequest) -> PolicySuggestionResponse: ...


def fallback_policy_suggestion() -> PolicySuggestionResponse:
    return PolicySuggestionResponse(
        risk_level="medium",
        rule_type="always_require_approval",
        threshold_amount=None,
        approval_triggers=["manual_review_recommended"],
        risk_factors=["policy_suggestion_uncertain"],
        explanation=(
            "DAAI could not confidently generate a policy suggestion. Approval is "
            "recommended until this action is reviewed."
        ),
        client_facing_summary=(
            "This action should be reviewed before execution until a more specific "
            "policy is confirmed."
        ),
        receipt_summary_template=(
            "The agent proposed this action. Approval was required because the "
            "policy suggestion was uncertain."
        ),
        confidence="low",
    )


class OpenAIPolicySuggester:
    def __init__(
        self,
        api_key: str | None,
        model: str,
        client: Any | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._client = client

    def suggest(self, request: SuggestActionPolicyRequest) -> PolicySuggestionResponse:
        if self._client is None and not self._api_key:
            logger.info("policy suggestion skipped because OpenAI API key is missing")
            return fallback_policy_suggestion()

        try:
            client = self._client or self._build_client()
            response = client.responses.parse(
                model=self._model,
                input=[
                    {"role": "system", "content": SYSTEM_MESSAGE},
                    {"role": "user", "content": self._user_message(request)},
                ],
                text_format=PolicySuggestionResponse,
            )
            parsed = getattr(response, "output_parsed", None)
            if parsed is None:
                raise ValueError("OpenAI response did not include parsed policy output")
            if isinstance(parsed, PolicySuggestionResponse):
                return parsed
            return PolicySuggestionResponse.model_validate(parsed)
        except Exception:
            logger.warning(
                "policy suggestion failed; returning safe fallback",
                exc_info=True,
            )
            return fallback_policy_suggestion()

    def _build_client(self) -> Any:
        from openai import OpenAI

        return OpenAI(api_key=self._api_key)

    def _user_message(self, request: SuggestActionPolicyRequest) -> str:
        context = {
            "action_name": request.action_name,
            "title": request.title,
            "description": request.description,
            "stated_risk_level": request.risk_level,
            "approver_email_present": bool(request.approver_email),
            "setup_answers": request.setup_answers.model_dump(),
            "allowed_policy_types": ALLOWED_POLICY_TYPES,
            "allowed_risk_levels": ALLOWED_RISK_LEVELS,
        }
        return (
            "Suggest one safe deterministic setup-time policy for this registered "
            "action. Runtime evaluation must remain deterministic and must not call "
            "an LLM. Do not return arbitrary conditions.\n\n"
            "Policy mapping guidance:\n"
            "- If approval_preference is never_just_log, suggest log_only unless "
            "the action has high or critical risk.\n"
            "- If approval_preference is always_require_approval, suggest "
            "always_require_approval.\n"
            "- If approval_preference is only_above_money_threshold, suggest "
            "require_approval_above_amount.\n"
            "- Default threshold_amount to 500 unless the setup text supplies "
            "another amount.\n"
            "- If the action contacts external people, consider "
            "require_approval_when_external_recipient.\n"
            "- If the action uses a new recipient, customer, or supplier, consider "
            "require_approval_when_new_recipient.\n"
            "- If the action deletes, cancels, closes, or marks something final, "
            "consider require_approval_when_destructive.\n"
            "- If the action is hard to reverse, consider "
            "require_approval_when_not_reversible.\n"
            "- If the user indicates the action should not run yet, suggest "
            "always_block.\n"
            "- If uncertain, suggest always_require_approval.\n\n"
            f"Action context:\n{json.dumps(context, sort_keys=True)}"
        )
