'use client';

import { useState } from 'react';

import {
  registerAction,
  suggestActionPolicy,
} from '@/app/action-registration-actions';
import {
  buttonStyles,
  fieldStyles,
  Notice,
  selectStyles,
  textareaStyles,
} from '@/components/console-ui';
import { FormSubmitButton } from '@/components/form-submit-button';
import {
  PolicySetupAnswers,
  PolicySource,
  PolicySuggestion,
  RegisteredActionPolicyType,
  RegisteredActionRiskLevel,
} from '@/lib/types';

type PolicyType = RegisteredActionPolicyType;

const APPROVAL_POLICY_TYPES = new Set<PolicyType>([
  'always_require_approval',
  'require_approval_above_amount',
  'require_approval_when_external_recipient',
  'require_approval_when_new_recipient',
  'require_approval_when_not_reversible',
  'require_approval_when_destructive',
]);

const POLICY_OPTIONS: PolicyType[] = [
  'log_only',
  'always_allow',
  'always_require_approval',
  'require_approval_above_amount',
  'always_block',
  'require_approval_when_external_recipient',
  'require_approval_when_new_recipient',
  'require_approval_when_not_reversible',
  'require_approval_when_destructive',
];

const DEFAULT_SETUP_ANSWERS: PolicySetupAnswers = {
  main_action_type: 'contacts_customer_supplier_or_external_person',
  main_action_type_other: '',
  biggest_risk: 'customer_confusion_or_reputation_risk',
  biggest_risk_other: '',
  approval_preference: 'always_require_approval',
  approval_preference_other: '',
  additional_context: '',
};

function label(value: string): string {
  return value.replaceAll('_', ' ');
}

function formatList(values: string[]): string {
  return values.length ? values.map(label).join(', ') : 'None listed';
}

function runtimeSignalHint(policyType: PolicyType | ''): string | null {
  if (policyType === 'require_approval_when_external_recipient') {
    return 'Pass external_recipient: true or a clear recipient email field in the SDK input payload.';
  }
  if (policyType === 'require_approval_when_new_recipient') {
    return 'Pass is_new_recipient, new_recipient, or recipient_is_new in the SDK input payload.';
  }
  if (policyType === 'require_approval_when_not_reversible') {
    return 'Pass reversible: false or not_reversible: true in the SDK input payload.';
  }
  if (policyType === 'require_approval_when_destructive') {
    return 'Pass destructive: true or is_destructive: true in the SDK input payload.';
  }
  return null;
}

function isFallbackSuggestion(suggestion: PolicySuggestion | null): boolean {
  return Boolean(
    suggestion?.risk_factors.includes('policy_suggestion_uncertain'),
  );
}

export function ActionRegistrationForm({
  workspaceId,
  disabled = false,
}: {
  workspaceId: string;
  disabled?: boolean;
}) {
  const [actionName, setActionName] = useState('send_invoice_reminder');
  const [title, setTitle] = useState('Send invoice reminder');
  const [description, setDescription] = useState(
    'Sends a payment reminder to an overdue invoice customer.',
  );
  const [riskLevel, setRiskLevel] = useState<RegisteredActionRiskLevel>('medium');
  const [approverEmail, setApproverEmail] = useState('');
  const [setupAnswers, setSetupAnswers] = useState<PolicySetupAnswers>(
    DEFAULT_SETUP_ANSWERS,
  );
  const [suggestion, setSuggestion] = useState<PolicySuggestion | null>(null);
  const [suggestionError, setSuggestionError] = useState<string | null>(null);
  const [suggesting, setSuggesting] = useState(false);
  const [policySource, setPolicySource] = useState<PolicySource | ''>('');
  const [policyType, setPolicyType] = useState<PolicyType | ''>('');
  const [thresholdAmount, setThresholdAmount] = useState('');
  const [explanation, setExplanation] = useState('');
  const [approvalTriggers, setApprovalTriggers] = useState<string[]>([]);
  const [riskFactors, setRiskFactors] = useState<string[]>([]);
  const [clientFacingSummary, setClientFacingSummary] = useState('');
  const [receiptSummaryTemplate, setReceiptSummaryTemplate] = useState('');
  const [policySuggestionSnapshot, setPolicySuggestionSnapshot] =
    useState<PolicySuggestion | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);

  const requiresThreshold = policyType === 'require_approval_above_amount';
  const requiresApproval =
    policyType !== '' && APPROVAL_POLICY_TYPES.has(policyType);
  const selectedSignalHint = runtimeSignalHint(policyType);

  function updateSetupAnswer<Key extends keyof PolicySetupAnswers>(
    key: Key,
    value: PolicySetupAnswers[Key],
  ) {
    setSetupAnswers((current) => ({ ...current, [key]: value }));
  }

  function applySuggestion(nextSuggestion: PolicySuggestion, edit: boolean) {
    setPolicySource('llm_suggested_confirmed');
    setPolicyType(nextSuggestion.rule_type);
    setRiskLevel(nextSuggestion.risk_level);
    setThresholdAmount(
      nextSuggestion.threshold_amount === null
        ? ''
        : String(nextSuggestion.threshold_amount),
    );
    setExplanation(nextSuggestion.explanation);
    setApprovalTriggers(nextSuggestion.approval_triggers);
    setRiskFactors(nextSuggestion.risk_factors);
    setClientFacingSummary(nextSuggestion.client_facing_summary);
    setReceiptSummaryTemplate(nextSuggestion.receipt_summary_template);
    setPolicySuggestionSnapshot(nextSuggestion);
    setEditorOpen(edit);
  }

  function chooseManualPolicy() {
    setPolicySource('manual');
    setPolicyType((current) => current || 'always_require_approval');
    setThresholdAmount((current) => current || '');
    setExplanation('');
    setApprovalTriggers([]);
    setRiskFactors([]);
    setClientFacingSummary('');
    setReceiptSummaryTemplate('');
    setPolicySuggestionSnapshot(null);
    setEditorOpen(true);
  }

  async function requestSuggestion() {
    setSuggesting(true);
    setSuggestionError(null);

    const result = await suggestActionPolicy(workspaceId, {
      actionName,
      title,
      description,
      riskLevel,
      approverEmail: approverEmail || null,
      setupAnswers,
    });

    setSuggesting(false);
    if (result.error || !result.data) {
      setSuggestion(null);
      setSuggestionError(
        result.error ?? 'Policy suggestion is unavailable. Choose a policy manually.',
      );
      return;
    }

    setSuggestion(result.data);
  }

  return (
    <form action={registerAction} className="grid gap-5">
      <input type="hidden" name="workspace_id" value={workspaceId} />
      <input type="hidden" name="policy_type" value={policyType} />
      <input type="hidden" name="policy_source" value={policySource} />
      <input type="hidden" name="threshold_amount" value={thresholdAmount} />
      <input type="hidden" name="explanation" value={explanation} />
      <input
        type="hidden"
        name="approval_triggers_json"
        value={JSON.stringify(approvalTriggers)}
      />
      <input
        type="hidden"
        name="risk_factors_json"
        value={JSON.stringify(riskFactors)}
      />
      <input
        type="hidden"
        name="client_facing_summary"
        value={clientFacingSummary}
      />
      <input
        type="hidden"
        name="receipt_summary_template"
        value={receiptSummaryTemplate}
      />
      <input
        type="hidden"
        name="setup_answers_json"
        value={JSON.stringify(setupAnswers)}
      />
      <input
        type="hidden"
        name="policy_suggestion_snapshot_json"
        value={
          policySuggestionSnapshot
            ? JSON.stringify(policySuggestionSnapshot)
            : ''
        }
      />

      <section className="grid gap-4">
        <h2 className="text-base font-semibold text-text">Action details</h2>

        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <label htmlFor="action_name" className="block text-sm font-medium text-text">
              Action name
            </label>
            <input
              id="action_name"
              name="action_name"
              type="text"
              required
              maxLength={64}
              pattern="^[a-z][a-z0-9_]{1,63}$"
              value={actionName}
              onChange={(event) => setActionName(event.target.value)}
              className={`mt-1 font-mono ${fieldStyles}`}
            />
          </div>

          <div>
            <label htmlFor="title" className="block text-sm font-medium text-text">
              Title
            </label>
            <input
              id="title"
              name="title"
              type="text"
              required
              maxLength={160}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              className={`mt-1 ${fieldStyles}`}
            />
          </div>
        </div>

        <div>
          <label htmlFor="description" className="block text-sm font-medium text-text">
            Description
          </label>
          <textarea
            id="description"
            name="description"
            rows={3}
            maxLength={1000}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            className={`mt-1 ${textareaStyles}`}
          />
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <label htmlFor="risk_level" className="block text-sm font-medium text-text">
              Risk level
            </label>
            <select
              id="risk_level"
              name="risk_level"
              value={riskLevel}
              onChange={(event) =>
                setRiskLevel(event.target.value as RegisteredActionRiskLevel)
              }
              className={`mt-1 ${selectStyles}`}
            >
              <option value="low">low</option>
              <option value="medium">medium</option>
              <option value="high">high</option>
              <option value="critical">critical</option>
            </select>
          </div>

          <div>
            <label htmlFor="approver_email" className="block text-sm font-medium text-text">
              Approver email
            </label>
            <input
              id="approver_email"
              name="approver_email"
              type="email"
              value={approverEmail}
              onChange={(event) => setApproverEmail(event.target.value)}
              required={requiresApproval}
              placeholder="owner@example.com"
              className={`mt-1 ${fieldStyles}`}
            />
          </div>
        </div>
      </section>

      <section className="grid gap-4 border-t border-border pt-5">
        <div>
          <h2 className="text-base font-semibold text-text">Policy setup</h2>
          <p className="mt-1 text-sm text-muted">
            Answer three setup questions before confirming a deterministic policy.
          </p>
        </div>

        <div className="grid gap-4">
          <div>
            <label htmlFor="main_action_type" className="block text-sm font-medium text-text">
              What does this action mainly do?
            </label>
            <select
              id="main_action_type"
              value={setupAnswers.main_action_type}
              onChange={(event) =>
                updateSetupAnswer(
                  'main_action_type',
                  event.target.value as PolicySetupAnswers['main_action_type'],
                )
              }
              className={`mt-1 ${selectStyles}`}
            >
              <option value="only_logs_or_updates_internal_notes">
                only logs or updates internal notes
              </option>
              <option value="changes_internal_business_data">
                changes internal business data
              </option>
              <option value="contacts_customer_supplier_or_external_person">
                contacts customer, supplier, or external person
              </option>
              <option value="sends_or_shares_sensitive_information">
                sends or shares sensitive information
              </option>
              <option value="triggers_money_invoice_refund_or_payment_related_work">
                triggers money, invoice, refund, or payment work
              </option>
              <option value="deletes_cancels_closes_or_marks_final">
                deletes, cancels, closes, or marks final
              </option>
              <option value="other">other</option>
            </select>
            <input
              type="text"
              value={setupAnswers.main_action_type_other}
              onChange={(event) =>
                updateSetupAnswer('main_action_type_other', event.target.value)
              }
              placeholder="Other / extra details"
              className={`mt-2 ${fieldStyles}`}
            />
          </div>

          <div>
            <label htmlFor="biggest_risk" className="block text-sm font-medium text-text">
              What is the biggest risk if this action is wrong?
            </label>
            <select
              id="biggest_risk"
              value={setupAnswers.biggest_risk}
              onChange={(event) =>
                updateSetupAnswer(
                  'biggest_risk',
                  event.target.value as PolicySetupAnswers['biggest_risk'],
                )
              }
              className={`mt-1 ${selectStyles}`}
            >
              <option value="minor_admin_mistake">minor admin mistake</option>
              <option value="customer_confusion_or_reputation_risk">
                customer confusion or reputation risk
              </option>
              <option value="financial_loss_or_incorrect_payment_handling">
                financial loss or incorrect payment handling
              </option>
              <option value="privacy_or_sensitive_data_exposure">
                privacy or sensitive data exposure
              </option>
              <option value="hard_to_reverse_business_state_change">
                hard to reverse business state change
              </option>
              <option value="legal_or_compliance_issue">
                legal or compliance issue
              </option>
              <option value="other">other</option>
            </select>
            <input
              type="text"
              value={setupAnswers.biggest_risk_other}
              onChange={(event) =>
                updateSetupAnswer('biggest_risk_other', event.target.value)
              }
              placeholder="Other / extra details"
              className={`mt-2 ${fieldStyles}`}
            />
          </div>

          <div>
            <label
              htmlFor="approval_preference"
              className="block text-sm font-medium text-text"
            >
              When should a human review this action first?
            </label>
            <select
              id="approval_preference"
              value={setupAnswers.approval_preference}
              onChange={(event) =>
                updateSetupAnswer(
                  'approval_preference',
                  event.target.value as PolicySetupAnswers['approval_preference'],
                )
              }
              className={`mt-1 ${selectStyles}`}
            >
              <option value="never_just_log">never, just log</option>
              <option value="always_require_approval">
                always require approval
              </option>
              <option value="only_above_money_threshold">
                only above money threshold
              </option>
              <option value="when_contacting_someone_outside_company">
                when contacting someone outside company
              </option>
              <option value="when_using_new_customer_supplier_or_recipient">
                when using new customer, supplier, or recipient
              </option>
              <option value="when_action_cannot_easily_be_undone">
                when action cannot easily be undone
              </option>
              <option value="always_block_for_now">always block for now</option>
              <option value="other">other</option>
            </select>
            <input
              type="text"
              value={setupAnswers.approval_preference_other}
              onChange={(event) =>
                updateSetupAnswer('approval_preference_other', event.target.value)
              }
              placeholder="Other / extra details"
              className={`mt-2 ${fieldStyles}`}
            />
          </div>

          <div>
            <label
              htmlFor="additional_context"
              className="block text-sm font-medium text-text"
            >
              Describe any business-specific policy concern for this action.
            </label>
            <textarea
              id="additional_context"
              rows={3}
              maxLength={2000}
              value={setupAnswers.additional_context}
              onChange={(event) =>
                updateSetupAnswer('additional_context', event.target.value)
              }
              className={`mt-1 ${textareaStyles}`}
            />
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={suggesting || disabled}
            onClick={requestSuggestion}
            className={buttonStyles.primary}
          >
            {suggesting ? 'Suggesting...' : 'Suggest policy'}
          </button>
          <button
            type="button"
            onClick={chooseManualPolicy}
            disabled={disabled}
            className={buttonStyles.secondary}
          >
            Choose manually
          </button>
        </div>

        {suggestionError ? <Notice tone="warning">{suggestionError}</Notice> : null}

        {isFallbackSuggestion(suggestion) ? (
          <Notice tone="warning">
            The suggestion service returned a conservative fallback. Review it or choose
            a manual policy.
          </Notice>
        ) : null}
      </section>

      {suggestion ? (
        <section className="grid gap-4 rounded-md border border-border bg-canvas p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold text-text">Policy review</h2>
              <p className="mt-1 font-mono text-sm text-text">
                {suggestion.rule_type}
              </p>
            </div>
            <p className="text-sm text-muted">
              Risk {suggestion.risk_level} | Confidence {suggestion.confidence}
            </p>
          </div>

          <dl className="grid gap-3 text-sm md:grid-cols-2">
            <div>
              <dt className="font-medium text-text">Explanation</dt>
              <dd className="mt-1 text-muted">{suggestion.explanation}</dd>
            </div>
            <div>
              <dt className="font-medium text-text">Client-facing summary</dt>
              <dd className="mt-1 text-muted">{suggestion.client_facing_summary}</dd>
            </div>
            <div>
              <dt className="font-medium text-text">Approval triggers</dt>
              <dd className="mt-1 text-muted">
                {formatList(suggestion.approval_triggers)}
              </dd>
            </div>
            <div>
              <dt className="font-medium text-text">Risk factors</dt>
              <dd className="mt-1 text-muted">{formatList(suggestion.risk_factors)}</dd>
            </div>
            {suggestion.threshold_amount !== null ? (
              <div>
                <dt className="font-medium text-text">Threshold amount</dt>
                <dd className="mt-1 text-muted">{suggestion.threshold_amount}</dd>
              </div>
            ) : null}
          </dl>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => applySuggestion(suggestion, false)}
              className={buttonStyles.primary}
            >
              Use this policy
            </button>
            <button
              type="button"
              onClick={() => applySuggestion(suggestion, true)}
              className={buttonStyles.secondary}
            >
              Edit policy
            </button>
            <button
              type="button"
              onClick={chooseManualPolicy}
              className={buttonStyles.subtle}
            >
              Choose manually
            </button>
          </div>
        </section>
      ) : null}

      {policySource ? (
        <Notice tone="success">
          Confirmed policy: <span className="font-mono">{policyType}</span>
        </Notice>
      ) : null}

      {editorOpen ? (
        <section className="grid gap-4 rounded-md border border-border bg-canvas p-4">
          <h2 className="text-base font-semibold text-text">Edit policy</h2>

          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label htmlFor="manual_policy_type" className="block text-sm font-medium text-text">
                Rule type
              </label>
              <select
                id="manual_policy_type"
                value={policyType}
                onChange={(event) =>
                  setPolicyType(event.target.value as PolicyType)
                }
                className={`mt-1 ${selectStyles}`}
              >
                {POLICY_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </div>

            {requiresThreshold ? (
              <div>
                <label
                  htmlFor="manual_threshold_amount"
                  className="block text-sm font-medium text-text"
                >
                  Threshold amount
                </label>
                <input
                  id="manual_threshold_amount"
                  type="number"
                  min="0.01"
                  step="0.01"
                  required
                  value={thresholdAmount}
                  onChange={(event) => setThresholdAmount(event.target.value)}
                  className={`mt-1 ${fieldStyles}`}
                />
              </div>
            ) : null}
          </div>

          <div>
            <label
              htmlFor="manual_policy_explanation"
              className="block text-sm font-medium text-text"
            >
              Explanation
            </label>
            <textarea
              id="manual_policy_explanation"
              rows={3}
              maxLength={2000}
              value={explanation}
              onChange={(event) => setExplanation(event.target.value)}
              className={`mt-1 ${textareaStyles}`}
            />
          </div>

          {requiresApproval ? (
            <div>
              <label
                htmlFor="manual_approver_email"
                className="block text-sm font-medium text-text"
              >
                Approver email
              </label>
              <input
                id="manual_approver_email"
                type="email"
                value={approverEmail}
                onChange={(event) => setApproverEmail(event.target.value)}
                required
                placeholder="owner@example.com"
                className={`mt-1 ${fieldStyles}`}
              />
            </div>
          ) : null}

          {selectedSignalHint ? <Notice tone="info">{selectedSignalHint}</Notice> : null}
        </section>
      ) : selectedSignalHint ? (
        <Notice tone="info">{selectedSignalHint}</Notice>
      ) : null}

      <div>
        <FormSubmitButton
          label="Register action"
          loadingLabel="Registering..."
          disabled={!policySource || disabled}
          className={buttonStyles.primary}
        />
      </div>
    </form>
  );
}
