'use server';

import { redirect } from 'next/navigation';

import {
  createWorkspaceRegisteredAction,
  suggestWorkspaceRegisteredActionPolicy,
} from '@/lib/api';
import {
  CreateRegisteredActionInput,
  PolicySetupAnswers,
  PolicySuggestion,
  SuggestRegisteredActionPolicyInput,
} from '@/lib/types';

const ACTION_NAME_PATTERN = /^[a-z][a-z0-9_]{1,63}$/;
const APPROVAL_POLICY_TYPES = new Set([
  'always_require_approval',
  'require_approval_above_amount',
  'require_approval_when_external_recipient',
  'require_approval_when_new_recipient',
  'require_approval_when_not_reversible',
  'require_approval_when_destructive',
]);
const POLICY_TYPES = [
  'log_only',
  'always_require_approval',
  'always_allow',
  'require_approval_above_amount',
  'always_block',
  'require_approval_when_external_recipient',
  'require_approval_when_new_recipient',
  'require_approval_when_not_reversible',
  'require_approval_when_destructive',
] as const;

function encodeMessage(message: string): string {
  return encodeURIComponent(message);
}

function readString(formData: FormData, key: string): string {
  const value = formData.get(key);
  return typeof value === 'string' ? value.trim() : '';
}

function safeReturnPath(workspaceId: string): string {
  return `/workspaces/${workspaceId}/actions/new`;
}

function redirectWithError(workspaceId: string, message: string): never {
  redirect(`${safeReturnPath(workspaceId)}?error=${encodeMessage(message)}`);
}

function friendlyApiError(error: string): string {
  const lower = error.toLowerCase();
  if (lower.includes('already exists')) {
    return 'An action with this action name already exists in this workspace.';
  }
  if (lower.includes('action_name')) {
    return 'Use lowercase letters, numbers, and underscores only. Start with a letter.';
  }
  if (lower.includes('approver_email')) {
    return 'Add an approver email for approval policies.';
  }
  if (lower.includes('threshold_amount')) {
    return 'Add a positive threshold amount for this policy.';
  }
  if (lower.includes('free beta') || lower.includes('limit reached')) {
    return 'Beta limit reached. Usage is capped during launch to protect reliability.';
  }
  return 'Action registration failed. Check the fields and try again.';
}

function readJson<T>(raw: string): T | null {
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export async function suggestActionPolicy(
  workspaceId: string,
  input: SuggestRegisteredActionPolicyInput,
): Promise<{ data: PolicySuggestion | null; error: string | null }> {
  if (!workspaceId) {
    return { data: null, error: 'Workspace is required.' };
  }

  return suggestWorkspaceRegisteredActionPolicy(workspaceId, input);
}

export async function registerAction(formData: FormData): Promise<never> {
  const workspaceId = readString(formData, 'workspace_id');
  if (!workspaceId) {
    redirect('/home');
  }

  const actionName = readString(formData, 'action_name');
  const title = readString(formData, 'title');
  const description = readString(formData, 'description');
  const riskLevel = readString(formData, 'risk_level') as CreateRegisteredActionInput['riskLevel'];
  const policyType = readString(formData, 'policy_type') as CreateRegisteredActionInput['policyType'];
  const thresholdValue = readString(formData, 'threshold_amount');
  const approverEmail = readString(formData, 'approver_email');
  const explanation = readString(formData, 'explanation');
  const policySource = readString(formData, 'policy_source') as CreateRegisteredActionInput['policySource'];
  const approvalTriggers = readJson<string[]>(
    readString(formData, 'approval_triggers_json'),
  );
  const riskFactors = readJson<string[]>(
    readString(formData, 'risk_factors_json'),
  );
  const clientFacingSummary = readString(formData, 'client_facing_summary');
  const receiptSummaryTemplate = readString(formData, 'receipt_summary_template');
  const setupAnswers = readJson<PolicySetupAnswers>(
    readString(formData, 'setup_answers_json'),
  );
  const policySuggestionSnapshot = readJson<PolicySuggestion>(
    readString(formData, 'policy_suggestion_snapshot_json'),
  );

  if (!ACTION_NAME_PATTERN.test(actionName)) {
    redirectWithError(
      workspaceId,
      'Use lowercase letters, numbers, and underscores only. Start with a letter.',
    );
  }
  if (!title) {
    redirectWithError(workspaceId, 'Title is required.');
  }
  if (!['low', 'medium', 'high', 'critical'].includes(riskLevel)) {
    redirectWithError(workspaceId, 'Choose a risk level.');
  }
  if (!POLICY_TYPES.includes(policyType)) {
    redirectWithError(workspaceId, 'Confirm a policy before registering the action.');
  }
  if (!['manual', 'llm_suggested_confirmed'].includes(policySource ?? '')) {
    redirectWithError(workspaceId, 'Confirm a policy before registering the action.');
  }

  let thresholdAmount: number | null = null;
  if (policyType === 'require_approval_above_amount') {
    thresholdAmount = Number(thresholdValue);
    if (!Number.isFinite(thresholdAmount) || thresholdAmount <= 0) {
      redirectWithError(workspaceId, 'Add a positive threshold amount for this policy.');
    }
  }

  if (APPROVAL_POLICY_TYPES.has(policyType) && !approverEmail) {
    redirectWithError(workspaceId, 'Add an approver email for approval policies.');
  }

  const result = await createWorkspaceRegisteredAction(workspaceId, {
    actionName,
    title,
    description,
    riskLevel,
    policyType,
    thresholdAmount,
    approverEmail: approverEmail || null,
    explanation,
    approvalTriggers: approvalTriggers ?? [],
    riskFactors: riskFactors ?? [],
    clientFacingSummary,
    receiptSummaryTemplate,
    policySource,
    setupAnswers,
    policySuggestionSnapshot,
  });

  if (result.error || !result.data) {
    redirectWithError(
      workspaceId,
      friendlyApiError(result.error ?? 'Action registration failed.'),
    );
  }

  redirect(
    `/workspaces/${workspaceId}/actions?created_action=${encodeMessage(
      result.data.action_name,
    )}`,
  );
}
