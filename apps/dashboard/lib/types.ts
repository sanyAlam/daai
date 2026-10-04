export type GovernanceStatus =
  | 'allowed'
  | 'pending_approval'
  | 'approved'
  | 'rejected'
  | 'blocked';

export type ExecutionStatus =
  | 'not_executed'
  | 'awaiting_execution_report'
  | 'executed'
  | 'failed';

export interface GovernanceReceipt {
  id: string;
  outcome: 'allowed' | 'blocked' | 'approved' | 'rejected';
  reason: string;
  policy_type: string;
  policy_snapshot: Record<string, unknown>;
  created_at: string;
}

export interface Workspace {
  id: string;
  name: string;
  client_name: string | null;
  status: string;
  created_at: string;
}

export interface CreatedWorkspace {
  id: string;
  name: string;
  client_name: string;
  status: string;
  workspace_key: string | null;
  workspace_key_is_one_time: boolean;
  created_at: string;
}

export interface DeletedWorkspace {
  id: string;
  name: string;
  deleted: boolean;
}

export interface DashboardApiKey {
  id: string;
  name: string;
  workspace_id: string;
  workspace_name: string;
  workspace_client_name: string | null;
  key_prefix: string;
  created_at: string;
  created_by: string | null;
  last_used_at: string | null;
  status: 'active' | 'revoked';
  revoked_at: string | null;
}

export interface CreatedDashboardApiKey extends DashboardApiKey {
  raw_api_key: string;
  raw_api_key_is_one_time: boolean;
}

export interface WorkspaceKeyInfo {
  workspace_id: string;
  workspace_name: string;
  workspace_client_name: string | null;
  key_identifier: string;
  full_key_available: boolean;
  workspace_key_is_one_time: boolean;
}

export interface RegeneratedWorkspaceKey extends WorkspaceKeyInfo {
  workspace_key: string | null;
}

export interface RegisteredAction {
  id: string;
  workspace_id: string;
  action_name: string;
  title: string;
  description: string;
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  is_active: boolean;
  policy_type: string;
  policy_config: Record<string, unknown>;
  policy: {
    rule_type: string;
    threshold_amount: number | null;
  };
  approver_email: string | null;
}

export type RegisteredActionRiskLevel = 'low' | 'medium' | 'high' | 'critical';

export type RegisteredActionPolicyType =
  | 'log_only'
  | 'always_require_approval'
  | 'always_allow'
  | 'require_approval_above_amount'
  | 'always_block'
  | 'require_approval_when_external_recipient'
  | 'require_approval_when_new_recipient'
  | 'require_approval_when_not_reversible'
  | 'require_approval_when_destructive';

export type PolicySource = 'llm_suggested_confirmed' | 'manual';

export interface PolicySetupAnswers {
  main_action_type:
    | 'only_logs_or_updates_internal_notes'
    | 'changes_internal_business_data'
    | 'contacts_customer_supplier_or_external_person'
    | 'sends_or_shares_sensitive_information'
    | 'triggers_money_invoice_refund_or_payment_related_work'
    | 'deletes_cancels_closes_or_marks_final'
    | 'other';
  main_action_type_other: string;
  biggest_risk:
    | 'minor_admin_mistake'
    | 'customer_confusion_or_reputation_risk'
    | 'financial_loss_or_incorrect_payment_handling'
    | 'privacy_or_sensitive_data_exposure'
    | 'hard_to_reverse_business_state_change'
    | 'legal_or_compliance_issue'
    | 'other';
  biggest_risk_other: string;
  approval_preference:
    | 'never_just_log'
    | 'always_require_approval'
    | 'only_above_money_threshold'
    | 'when_contacting_someone_outside_company'
    | 'when_using_new_customer_supplier_or_recipient'
    | 'when_action_cannot_easily_be_undone'
    | 'always_block_for_now'
    | 'other';
  approval_preference_other: string;
  additional_context: string;
}

export interface PolicySuggestion {
  risk_level: RegisteredActionRiskLevel;
  rule_type: RegisteredActionPolicyType;
  threshold_amount: number | null;
  approval_triggers: string[];
  risk_factors: string[];
  explanation: string;
  client_facing_summary: string;
  receipt_summary_template: string;
  confidence: 'low' | 'medium' | 'high';
}

export interface SuggestRegisteredActionPolicyInput {
  actionName: string;
  title: string;
  description: string;
  riskLevel: RegisteredActionRiskLevel;
  approverEmail?: string | null;
  setupAnswers: PolicySetupAnswers;
}

export interface CreateRegisteredActionInput {
  actionName: string;
  title: string;
  description: string;
  riskLevel: RegisteredActionRiskLevel;
  policyType: RegisteredActionPolicyType;
  thresholdAmount?: number | null;
  approverEmail?: string | null;
  explanation?: string;
  approvalTriggers?: string[];
  riskFactors?: string[];
  clientFacingSummary?: string;
  receiptSummaryTemplate?: string;
  policySource?: PolicySource;
  setupAnswers?: PolicySetupAnswers | null;
  policySuggestionSnapshot?: PolicySuggestion | null;
}

export interface WorkspaceRunMetrics {
  total_runs: number;
  pending_approval: number;
  approved: number;
  rejected: number;
  blocked: number;
  allowed: number;
  executed: number;
  failed: number;
}

export interface UsageBucket {
  used: number;
  limit: number;
}

export interface DashboardUsage {
  plan: string;
  client_workspaces: UsageBucket;
  registered_actions: UsageBucket;
  action_runs_this_month: UsageBucket;
  approval_emails_this_month: UsageBucket;
}

export interface WorkspaceApprovalSettings {
  workspace_id: string;
  approval_emails: string[];
  approval_link_ttl_minutes: number;
}

export interface PendingApprovalItem {
  action_run_id: string;
  action: string;
  governance_reason: string;
  payload_preview: string;
  created_at: string;
  decision_expires_at: string | null;
}

export interface DashboardActionDecision {
  action_run_id: string;
  governance_status: GovernanceStatus;
  execution_status: ExecutionStatus;
  governance_reason: string;
  executable: boolean;
  receipt: GovernanceReceipt;
}

export interface ActionRunListItem {
  action_run_id: string;
  action: string;
  governance_status: GovernanceStatus;
  execution_status: ExecutionStatus;
  governance_reason: string;
  executable: boolean;
  payload: Record<string, unknown>;
  created_at: string;
  decided_at: string | null;
  receipt: GovernanceReceipt | null;
}

export interface ActionRunListResponse {
  items: ActionRunListItem[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface ActionRunDetail {
  action_run_id: string;
  action: string;
  governance_status: GovernanceStatus;
  execution_status: ExecutionStatus;
  governance_reason: string;
  executable: boolean;
  payload: Record<string, unknown>;
  policy_snapshot: Record<string, unknown>;
  execution_result: Record<string, unknown>;
  execution_error: string | null;
  execution_reported_at: string | null;
  created_at: string;
  decided_at: string | null;
  receipt: GovernanceReceipt | null;
}

export interface AdminOverview {
  total_users: number;
  total_workspaces: number;
  total_registered_actions: number;
  total_action_runs: number;
  pending_approvals: number;
  approved_actions: number;
  blocked_actions: number;
  executed_actions: number;
  failed_actions: number;
  approval_emails_sent_this_month: number;
  activated_users: number;
}

export interface AdminUser {
  email: string | null;
  signed_up_at: string;
  plan: string;
  workspace_count: number;
  registered_action_count: number;
  action_run_count: number;
  last_action_run_at: string | null;
  activated: boolean;
}

export interface AdminWorkspace {
  workspace_id: string;
  workspace_name: string;
  client_name: string | null;
  owner_email: string | null;
  plan: string;
  registered_action_count: number;
  action_runs_this_month: number;
  approval_emails_this_month: number;
  last_action_run_at: string | null;
  created_at: string;
}

export interface AdminActionRun {
  action_run_id: string;
  created_at: string;
  workspace_id: string;
  workspace_name: string;
  owner_email: string | null;
  action_name: string;
  actor: string | null;
  governance_status: GovernanceStatus;
  governance_reason: string;
  executable: boolean;
  execution_status: ExecutionStatus;
}
