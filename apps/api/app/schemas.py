from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain import ExecutionStatus, GovernanceStatus


class InterceptRequest(BaseModel):
    action: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = Field(default=None, min_length=1, max_length=256)
    reasoning: Optional[str] = None
    source: Optional[dict[str, Any]] = None

    @model_validator(mode="before")
    @classmethod
    def accept_input_alias(cls, data: Any) -> Any:
        if isinstance(data, dict) and "payload" not in data and "input" in data:
            return {**data, "payload": data["input"]}
        return data


class GovernanceReceiptResponse(BaseModel):
    id: UUID
    outcome: str
    reason: str
    policy_type: str
    policy_snapshot: dict[str, Any]
    created_at: datetime


class InterceptResponse(BaseModel):
    action_run_id: UUID
    governance_status: GovernanceStatus
    execution_status: ExecutionStatus
    governance_reason: str
    executable: bool
    idempotent_replay: bool
    receipt: Optional[GovernanceReceiptResponse]


class ReportExecutedRequest(BaseModel):
    execution_result: dict[str, Any] = Field(default_factory=dict)


class ReportFailedRequest(BaseModel):
    execution_error: str = Field(min_length=1)
    execution_result: dict[str, Any] = Field(default_factory=dict)


class ExecutionReportResponse(BaseModel):
    action_run_id: UUID
    execution_status: ExecutionStatus
    execution_error: Optional[str]
    execution_reported_at: Optional[datetime]
    idempotent_replay: bool


class ActionRunStatusResponse(BaseModel):
    action_run_id: UUID
    action: str
    governance_status: GovernanceStatus
    execution_status: ExecutionStatus
    governance_reason: str
    executable: bool
    receipt: Optional[GovernanceReceiptResponse]
    created_at: datetime
    decided_at: Optional[datetime]


class PublicDecisionResponse(BaseModel):
    action_run_id: UUID
    governance_status: GovernanceStatus
    execution_status: ExecutionStatus
    governance_reason: str
    executable: bool
    receipt: GovernanceReceiptResponse


class DashboardWorkspaceResponse(BaseModel):
    id: UUID
    name: str
    created_at: datetime
    client_name: Optional[str] = None
    status: str = "active"


class CreateDashboardWorkspaceRequest(BaseModel):
    workspace_name: str = Field(min_length=1, max_length=160)
    client_name: str = Field(min_length=1, max_length=160)


class CreateDashboardWorkspaceResponse(BaseModel):
    id: UUID
    name: str
    client_name: str
    status: str
    workspace_key: Optional[str] = None
    workspace_key_is_one_time: bool = True
    created_at: datetime


class DeleteDashboardWorkspaceRequest(BaseModel):
    workspace_name_confirmation: str = Field(min_length=1, max_length=160)


class DeleteDashboardWorkspaceResponse(BaseModel):
    id: UUID
    name: str
    deleted: bool


class DashboardApiKeyResponse(BaseModel):
    id: UUID
    name: str
    workspace_id: UUID
    workspace_name: str
    workspace_client_name: Optional[str] = None
    key_prefix: str
    created_at: datetime
    created_by: Optional[UUID] = None
    last_used_at: Optional[datetime] = None
    status: str
    revoked_at: Optional[datetime] = None


class CreateDashboardApiKeyRequest(BaseModel):
    workspace_id: UUID
    name: str = Field(min_length=1, max_length=160)


class CreateDashboardApiKeyResponse(DashboardApiKeyResponse):
    raw_api_key: str
    raw_api_key_is_one_time: bool = True


class DashboardWorkspaceKeyInfoResponse(BaseModel):
    workspace_id: UUID
    workspace_name: str
    workspace_client_name: Optional[str] = None
    key_identifier: str
    full_key_available: bool = False
    workspace_key_is_one_time: bool = True


class RegenerateDashboardWorkspaceKeyResponse(DashboardWorkspaceKeyInfoResponse):
    workspace_key: Optional[str] = None


class CreateDashboardActionRequest(BaseModel):
    action_name: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=1000)
    risk_level: str
    policy_type: str
    threshold_amount: Optional[float] = None
    approver_email: Optional[str] = Field(default=None, max_length=320)
    explanation: str = Field(default="", max_length=2000)
    approval_triggers: list[str] = Field(default_factory=list, max_length=20)
    risk_factors: list[str] = Field(default_factory=list, max_length=20)
    client_facing_summary: str = Field(default="", max_length=2000)
    receipt_summary_template: str = Field(default="", max_length=2000)
    policy_source: str = "manual"
    setup_answers: Optional[dict[str, Any]] = None
    policy_suggestion_snapshot: Optional[dict[str, Any]] = None

    @field_validator("action_name")
    @classmethod
    def validate_action_name(cls, value: str) -> str:
        normalized = value.strip()
        if not re.match(r"^[a-z][a-z0-9_]{1,63}$", normalized):
            raise ValueError(
                "action_name must start with a lowercase letter and contain only lowercase letters, numbers, and underscores"
            )
        return normalized

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("title is required")
        return normalized

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        return value.strip()

    @field_validator("risk_level")
    @classmethod
    def validate_risk_level(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"low", "medium", "high", "critical"}:
            raise ValueError(
                "risk_level must be one of low, medium, high, critical"
            )
        return normalized

    @field_validator("policy_type")
    @classmethod
    def validate_policy_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {
            "log_only",
            "always_require_approval",
            "always_allow",
            "require_approval_above_amount",
            "always_block",
            "require_approval_when_external_recipient",
            "require_approval_when_new_recipient",
            "require_approval_when_not_reversible",
            "require_approval_when_destructive",
        }:
            raise ValueError(
                "policy_type must be a supported deterministic policy type"
            )
        return normalized

    @field_validator("threshold_amount")
    @classmethod
    def validate_threshold_amount(cls, value: Optional[float]) -> Optional[float]:
        if value is not None and value <= 0:
            raise ValueError("threshold_amount must be positive")
        return value

    @field_validator("approver_email")
    @classmethod
    def validate_approver_email(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not normalized:
            return None
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", normalized):
            raise ValueError("approver_email must be a valid email address")
        return normalized

    @field_validator(
        "explanation",
        "client_facing_summary",
        "receipt_summary_template",
    )
    @classmethod
    def strip_policy_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("approval_triggers", "risk_factors")
    @classmethod
    def strip_policy_labels(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if item.strip()]
        return normalized[:20]

    @field_validator("policy_source")
    @classmethod
    def validate_policy_source(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"manual", "llm_suggested_confirmed"}:
            raise ValueError(
                "policy_source must be one of manual, llm_suggested_confirmed"
            )
        return normalized


class DashboardActionPolicyResponse(BaseModel):
    rule_type: str
    threshold_amount: Optional[float] = None


class DashboardActionResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    action_name: str
    title: str
    description: str
    risk_level: str
    is_active: bool
    policy_type: str
    policy_config: dict[str, Any]
    policy: DashboardActionPolicyResponse
    approver_email: Optional[str] = None


MainActionType = Literal[
    "only_logs_or_updates_internal_notes",
    "changes_internal_business_data",
    "contacts_customer_supplier_or_external_person",
    "sends_or_shares_sensitive_information",
    "triggers_money_invoice_refund_or_payment_related_work",
    "deletes_cancels_closes_or_marks_final",
    "other",
]

BiggestRisk = Literal[
    "minor_admin_mistake",
    "customer_confusion_or_reputation_risk",
    "financial_loss_or_incorrect_payment_handling",
    "privacy_or_sensitive_data_exposure",
    "hard_to_reverse_business_state_change",
    "legal_or_compliance_issue",
    "other",
]

ApprovalPreference = Literal[
    "never_just_log",
    "always_require_approval",
    "only_above_money_threshold",
    "when_contacting_someone_outside_company",
    "when_using_new_customer_supplier_or_recipient",
    "when_action_cannot_easily_be_undone",
    "always_block_for_now",
    "other",
]

RiskLevel = Literal["low", "medium", "high", "critical"]
PolicySuggestionRuleType = Literal[
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
PolicySuggestionConfidence = Literal["low", "medium", "high"]


class PolicySetupAnswers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    main_action_type: MainActionType
    main_action_type_other: str = Field(default="", max_length=1000)
    biggest_risk: BiggestRisk
    biggest_risk_other: str = Field(default="", max_length=1000)
    approval_preference: ApprovalPreference
    approval_preference_other: str = Field(default="", max_length=1000)
    additional_context: str = Field(default="", max_length=2000)

    @field_validator(
        "main_action_type_other",
        "biggest_risk_other",
        "approval_preference_other",
        "additional_context",
    )
    @classmethod
    def strip_setup_text(cls, value: str) -> str:
        return value.strip()


class SuggestActionPolicyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_name: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=1000)
    risk_level: RiskLevel
    approver_email: Optional[str] = Field(default=None, max_length=320)
    setup_answers: PolicySetupAnswers

    @field_validator("action_name")
    @classmethod
    def validate_suggestion_action_name(cls, value: str) -> str:
        normalized = value.strip()
        if not re.match(r"^[a-z][a-z0-9_]{1,63}$", normalized):
            raise ValueError(
                "action_name must start with a lowercase letter and contain only lowercase letters, numbers, and underscores"
            )
        return normalized

    @field_validator("title")
    @classmethod
    def validate_suggestion_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("title is required")
        return normalized

    @field_validator("description")
    @classmethod
    def validate_suggestion_description(cls, value: str) -> str:
        return value.strip()

    @field_validator("approver_email")
    @classmethod
    def validate_suggestion_approver_email(
        cls, value: Optional[str]
    ) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not normalized:
            return None
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", normalized):
            raise ValueError("approver_email must be a valid email address")
        return normalized


class PolicySuggestionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_level: RiskLevel
    rule_type: PolicySuggestionRuleType
    threshold_amount: Optional[float] = None
    approval_triggers: list[str] = Field(default_factory=list, max_length=20)
    risk_factors: list[str] = Field(default_factory=list, max_length=20)
    explanation: str = Field(min_length=1, max_length=2000)
    client_facing_summary: str = Field(min_length=1, max_length=2000)
    receipt_summary_template: str = Field(min_length=1, max_length=2000)
    confidence: PolicySuggestionConfidence

    @field_validator("threshold_amount")
    @classmethod
    def validate_suggestion_threshold(
        cls, value: Optional[float]
    ) -> Optional[float]:
        if value is not None and value <= 0:
            raise ValueError("threshold_amount must be positive")
        return value

    @field_validator("approval_triggers", "risk_factors")
    @classmethod
    def strip_suggestion_labels(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if item.strip()]
        return normalized[:20]

    @field_validator(
        "explanation",
        "client_facing_summary",
        "receipt_summary_template",
    )
    @classmethod
    def strip_suggestion_text(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_amount_policy_threshold(self) -> "PolicySuggestionResponse":
        if (
            self.rule_type == "require_approval_above_amount"
            and self.threshold_amount is None
        ):
            raise ValueError(
                "threshold_amount is required for require_approval_above_amount"
            )
        return self


class DashboardWorkspaceApprovalSettingsRequest(BaseModel):
    approval_emails: list[str] = Field(default_factory=list)
    approval_link_ttl_minutes: int = Field(default=15, ge=5, le=1440)

    @field_validator("approval_emails")
    @classmethod
    def validate_approval_emails(cls, value: list[str]) -> list[str]:
        if len(value) > 2:
            raise ValueError("at most 2 approval emails are allowed")

        seen: set[str] = set()
        normalized: list[str] = []
        email_pattern = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
        for raw in value:
            candidate = raw.strip().lower()
            if not candidate:
                raise ValueError("approval email cannot be empty")
            if not email_pattern.match(candidate):
                raise ValueError(f"invalid approval email: {raw}")
            if candidate in seen:
                raise ValueError("duplicate approval emails are not allowed")
            seen.add(candidate)
            normalized.append(candidate)
        return normalized


class DashboardWorkspaceApprovalSettingsResponse(BaseModel):
    workspace_id: UUID
    approval_emails: list[str]
    approval_link_ttl_minutes: int


class DashboardWorkspaceMetricsResponse(BaseModel):
    total_runs: int
    pending_approval: int
    approved: int
    rejected: int
    blocked: int
    allowed: int
    executed: int
    failed: int


class UsageBucketResponse(BaseModel):
    used: int
    limit: int


class DashboardUsageResponse(BaseModel):
    plan: str
    client_workspaces: UsageBucketResponse
    registered_actions: UsageBucketResponse
    action_runs_this_month: UsageBucketResponse
    approval_emails_this_month: UsageBucketResponse


class DashboardActionRunListItemResponse(BaseModel):
    action_run_id: UUID
    action: str
    governance_status: GovernanceStatus
    execution_status: ExecutionStatus
    governance_reason: str
    executable: bool
    payload: dict[str, Any]
    created_at: datetime
    decided_at: Optional[datetime]
    receipt: Optional[GovernanceReceiptResponse]


class DashboardActionRunListResponse(BaseModel):
    items: list[DashboardActionRunListItemResponse]
    page: int
    page_size: int
    total: int
    total_pages: int


class DashboardPendingApprovalListItemResponse(BaseModel):
    action_run_id: UUID
    action: str
    governance_reason: str
    payload_preview: str
    created_at: datetime
    decision_expires_at: Optional[datetime]


class DashboardActionDecisionResponse(BaseModel):
    action_run_id: UUID
    governance_status: GovernanceStatus
    execution_status: ExecutionStatus
    governance_reason: str
    executable: bool
    receipt: GovernanceReceiptResponse


class DashboardActionRunDetailResponse(BaseModel):
    action_run_id: UUID
    action: str
    governance_status: GovernanceStatus
    execution_status: ExecutionStatus
    governance_reason: str
    executable: bool
    payload: dict[str, Any]
    policy_snapshot: dict[str, Any]
    execution_result: dict[str, Any]
    execution_error: Optional[str]
    execution_reported_at: Optional[datetime]
    created_at: datetime
    decided_at: Optional[datetime]
    receipt: Optional[GovernanceReceiptResponse]


class AdminOverviewResponse(BaseModel):
    total_users: int
    total_workspaces: int
    total_registered_actions: int
    total_action_runs: int
    pending_approvals: int
    approved_actions: int
    blocked_actions: int
    executed_actions: int
    failed_actions: int
    approval_emails_sent_this_month: int
    activated_users: int


class AdminUserResponse(BaseModel):
    email: Optional[str]
    signed_up_at: datetime
    plan: str
    workspace_count: int
    registered_action_count: int
    action_run_count: int
    last_action_run_at: Optional[datetime]
    activated: bool


class AdminWorkspaceResponse(BaseModel):
    workspace_id: UUID
    workspace_name: str
    client_name: Optional[str]
    owner_email: Optional[str]
    plan: str
    registered_action_count: int
    action_runs_this_month: int
    approval_emails_this_month: int
    last_action_run_at: Optional[datetime]
    created_at: datetime


class AdminActionRunResponse(BaseModel):
    action_run_id: UUID
    created_at: datetime
    workspace_id: UUID
    workspace_name: str
    owner_email: Optional[str]
    action_name: str
    actor: Optional[str]
    governance_status: GovernanceStatus
    governance_reason: str
    executable: bool
    execution_status: ExecutionStatus
