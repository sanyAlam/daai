'use client';

import Link from 'next/link';
import { FormEvent, useCallback, useMemo, useState } from 'react';

import {
  buttonStyles,
  fieldStyles,
  MetricCard,
  Notice,
  SectionCard,
  selectStyles,
} from '@/components/console-ui';
import { MetricsCardSkeletonGrid, ShimmerBlock } from '@/components/loaders';
import { formatTimestamp } from '@/lib/format';
import {
  DashboardActionDecision,
  PendingApprovalItem,
  WorkspaceApprovalSettings,
  WorkspaceRunMetrics,
} from '@/lib/types';

const TTL_OPTIONS = [
  { label: '5 min', value: 5 },
  { label: '15 min', value: 15 },
  { label: '30 min', value: 30 },
  { label: '1 hour', value: 60 },
  { label: '4 hours', value: 240 },
  { label: '24 hours', value: 1440 },
];

function truncate(text: string, max = 100): string {
  if (text.length <= max) {
    return text;
  }
  return `${text.slice(0, max - 3)}...`;
}

function parseInitialEmailSlots(approvalEmails: string[]): [string, string] {
  return [approvalEmails[0] ?? '', approvalEmails[1] ?? ''];
}

function normalizeEmails(values: string[]): string[] {
  return values
    .map((value) => value.trim().toLowerCase())
    .filter((value) => value.length > 0);
}

function formatExpiryStatus(expiresAt: string | null): string {
  if (!expiresAt) {
    return 'Expiry unavailable';
  }

  const expiry = new Date(expiresAt);
  if (Number.isNaN(expiry.getTime())) {
    return 'Expiry unavailable';
  }

  if (expiry.getTime() <= Date.now()) {
    return `Expired at ${formatTimestamp(expiresAt)}`;
  }

  return `Expires ${formatTimestamp(expiresAt)}`;
}

async function parseApiResponse<T>(response: Response): Promise<{
  data: T | null;
  error: string | null;
}> {
  const payload = (await response.json()) as T | { detail?: string };

  if (!response.ok) {
    const detailRaw = (payload as { detail?: string }).detail;
    const detail =
      typeof detailRaw === 'string' && detailRaw
        ? detailRaw
        : `Request failed (${response.status})`;
    return { data: null, error: detail };
  }

  return { data: payload as T, error: null };
}

export function WorkspaceOverviewAuditSection({
  workspaceId,
  initialMetrics,
  initialMetricsError,
  initialApprovalSettings,
  initialApprovalSettingsError,
  initialPendingApprovals,
  initialPendingApprovalsError,
}: {
  workspaceId: string;
  initialMetrics: WorkspaceRunMetrics | null;
  initialMetricsError: string | null;
  initialApprovalSettings: WorkspaceApprovalSettings | null;
  initialApprovalSettingsError: string | null;
  initialPendingApprovals: PendingApprovalItem[];
  initialPendingApprovalsError: string | null;
}) {
  const [metrics, setMetrics] = useState<WorkspaceRunMetrics | null>(initialMetrics);
  const [metricsError, setMetricsError] = useState<string | null>(initialMetricsError);
  const [metricsLoading, setMetricsLoading] = useState(false);

  const [approvalSettings, setApprovalSettings] = useState<WorkspaceApprovalSettings | null>(
    initialApprovalSettings,
  );
  const [approvalSettingsError, setApprovalSettingsError] = useState<string | null>(
    initialApprovalSettingsError,
  );

  const [pendingApprovals, setPendingApprovals] =
    useState<PendingApprovalItem[]>(initialPendingApprovals);
  const [pendingError, setPendingError] = useState<string | null>(
    initialPendingApprovalsError,
  );
  const [pendingLoading, setPendingLoading] = useState(false);

  const [emailOne, setEmailOne] = useState(
    parseInitialEmailSlots(initialApprovalSettings?.approval_emails ?? [])[0],
  );
  const [emailTwo, setEmailTwo] = useState(
    parseInitialEmailSlots(initialApprovalSettings?.approval_emails ?? [])[1],
  );
  const [ttlMinutes, setTtlMinutes] = useState<number>(
    initialApprovalSettings?.approval_link_ttl_minutes ?? 15,
  );
  const [saveSettingsLoading, setSaveSettingsLoading] = useState(false);
  const [saveSettingsMessage, setSaveSettingsMessage] = useState<string | null>(null);
  const [saveSettingsError, setSaveSettingsError] = useState<string | null>(null);

  const [decisionLoadingKey, setDecisionLoadingKey] = useState<string | null>(null);
  const [decisionError, setDecisionError] = useState<string | null>(null);

  const hasConfiguredApproverEmails = useMemo(() => {
    const emails = approvalSettings?.approval_emails ?? [];
    return emails.length > 0;
  }, [approvalSettings]);
  const loadMetrics = useCallback(async () => {
    setMetricsLoading(true);
    const response = await fetch(`/api/dashboard/workspaces/${workspaceId}/metrics`, {
      method: 'GET',
      cache: 'no-store',
    });
    const result = await parseApiResponse<WorkspaceRunMetrics>(response);
    if (result.error) {
      setMetricsError(result.error);
    } else {
      setMetrics(result.data);
      setMetricsError(null);
    }
    setMetricsLoading(false);
  }, [workspaceId]);

  const loadPendingApprovals = useCallback(async () => {
    setPendingLoading(true);
    const response = await fetch(
      `/api/dashboard/workspaces/${workspaceId}/pending-approvals?limit=25`,
      {
        method: 'GET',
        cache: 'no-store',
      },
    );
    const result = await parseApiResponse<PendingApprovalItem[]>(response);
    if (result.error) {
      setPendingError(result.error);
    } else {
      setPendingApprovals(result.data ?? []);
      setPendingError(null);
    }
    setPendingLoading(false);
  }, [workspaceId]);

  const refreshAudit = useCallback(async () => {
    await Promise.all([loadMetrics(), loadPendingApprovals()]);
  }, [loadMetrics, loadPendingApprovals]);

  const onSaveSettings = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (saveSettingsLoading) {
      return;
    }

    const approvalEmails = normalizeEmails([emailOne, emailTwo]);
    if (new Set(approvalEmails).size !== approvalEmails.length) {
      setSaveSettingsError('Duplicate approval emails are not allowed.');
      setSaveSettingsMessage(null);
      return;
    }

    setSaveSettingsLoading(true);
    setSaveSettingsMessage(null);
    setSaveSettingsError(null);

    const response = await fetch(
      `/api/dashboard/workspaces/${workspaceId}/approval-settings`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          approval_emails: approvalEmails,
          approval_link_ttl_minutes: ttlMinutes,
        }),
      },
    );

    const result = await parseApiResponse<WorkspaceApprovalSettings>(response);
    if (result.error || !result.data) {
      setSaveSettingsError(result.error ?? 'Could not save approval settings.');
      setSaveSettingsMessage(null);
      setSaveSettingsLoading(false);
      return;
    }

    setApprovalSettings(result.data);
    const [slotOne, slotTwo] = parseInitialEmailSlots(result.data.approval_emails);
    setEmailOne(slotOne);
    setEmailTwo(slotTwo);
    setTtlMinutes(result.data.approval_link_ttl_minutes);
    setApprovalSettingsError(null);
    setSaveSettingsError(null);
    setSaveSettingsMessage('Approval settings saved.');
    setSaveSettingsLoading(false);
  };

  const onDecision = async (
    actionRunId: string,
    decision: 'approve' | 'reject' | 'block',
  ) => {
    const loadingKey = `${actionRunId}:${decision}`;
    if (decisionLoadingKey) {
      return;
    }
    setDecisionLoadingKey(loadingKey);
    setDecisionError(null);

    const response = await fetch(
      `/api/dashboard/action-runs/${actionRunId}/${decision}`,
      {
        method: 'POST',
      },
    );
    const result = await parseApiResponse<DashboardActionDecision>(response);
    if (result.error) {
      setDecisionError(result.error);
      setDecisionLoadingKey(null);
      return;
    }

    await refreshAudit();
    setDecisionLoadingKey(null);
  };

  return (
    <div className="space-y-4">
      {metricsError ? (
        <Notice tone="danger">
          {metricsError}
        </Notice>
      ) : null}

      {metricsLoading ? (
        <MetricsCardSkeletonGrid cards={4} />
      ) : metrics ? (
        <SectionCard
          title="Run health"
          actions={
            <Link
              href={`/workspaces/${workspaceId}/runs`}
              className="text-sm font-medium text-muted transition hover:text-text"
            >
              View all runs
            </Link>
          }
        >
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard
              label="Pending approval"
              value={metrics.pending_approval}
              tone={metrics.pending_approval > 0 ? 'warning' : 'neutral'}
              compact
            />
            <MetricCard
              label="Blocked"
              value={metrics.blocked}
              tone={metrics.blocked > 0 ? 'danger' : 'neutral'}
              compact
            />
            <MetricCard
              label="Executed"
              value={metrics.executed}
              tone={metrics.executed > 0 ? 'success' : 'neutral'}
              compact
            />
            <MetricCard
              label="Failed"
              value={metrics.failed}
              tone={metrics.failed > 0 ? 'danger' : 'neutral'}
              compact
            />
          </div>
        </SectionCard>
      ) : null}

      <div className="grid gap-5 lg:grid-cols-[1.3fr,0.9fr]">
        <div id="pending-approvals">
          <SectionCard
            title={
              pendingApprovals.length > 0
                ? `Pending approvals (${pendingApprovals.length})`
                : 'Pending approvals'
            }
            description={
              pendingApprovals.length > 0
                ? 'Client decisions waiting for approval, rejection, or block.'
                : undefined
            }
            className={pendingApprovals.length > 0 ? 'border-warning/40 bg-warning/10' : undefined}
            actions={
              <button
                type="button"
                onClick={() => {
                  void refreshAudit();
                }}
                className={`${buttonStyles.secondary} px-2.5 py-1.5 text-xs`}
                disabled={pendingLoading || metricsLoading}
              >
                {pendingLoading ? 'Refreshing...' : 'Refresh'}
              </button>
            }
          >

            {!hasConfiguredApproverEmails && pendingApprovals.length > 0 ? (
              <Notice tone="warning" className="text-xs">
                Pending actions exist, but no approval email is configured for this workspace.
              </Notice>
            ) : null}

            {decisionError ? (
              <Notice tone="danger" className="mt-3 text-xs">
                {decisionError}
              </Notice>
            ) : null}

            {pendingError ? (
              <Notice tone="danger" className="mt-3 text-xs">
                {pendingError}
              </Notice>
            ) : null}

            <div className="mt-3 max-h-96 space-y-2 overflow-y-auto pr-1">
              {pendingLoading ? (
                <div className="space-y-3">
                  {Array.from({ length: 4 }).map((_, index) => (
                    <div
                      key={index}
                      className="rounded-lg border border-border bg-canvas p-3"
                    >
                      <ShimmerBlock className="h-4 w-36" />
                      <ShimmerBlock className="mt-2 h-3 w-52" />
                      <ShimmerBlock className="mt-2 h-3 w-full" />
                      <div className="mt-3 flex gap-2">
                        <ShimmerBlock className="h-8 w-16" />
                        <ShimmerBlock className="h-8 w-16" />
                        <ShimmerBlock className="h-8 w-16" />
                      </div>
                    </div>
                  ))}
                </div>
              ) : pendingApprovals.length === 0 ? (
                <div className="rounded-md bg-canvas px-3 py-2">
                  <p className="text-sm font-medium text-text">No pending approvals</p>
                  <p className="mt-1 text-xs text-muted">
                    When an action requires approval, it will appear here.
                  </p>
                </div>
              ) : (
                pendingApprovals.map((item) => {
                  const actionBusy =
                    decisionLoadingKey !== null &&
                    decisionLoadingKey.startsWith(`${item.action_run_id}:`);

                  return (
                    <div
                      key={item.action_run_id}
                      className="rounded-lg border border-border bg-canvas p-3"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-sm font-semibold text-text">{item.action}</p>
                        <p className="text-xs text-muted">{formatTimestamp(item.created_at)}</p>
                      </div>
                      <p className="mt-1 text-xs text-muted">
                        Reason: {truncate(item.governance_reason, 90)}
                      </p>
                      <p className="mt-1 text-xs text-muted">
                        Payload: {truncate(item.payload_preview, 110)}
                      </p>
                      <p className="mt-1 text-xs text-muted">
                        {formatExpiryStatus(item.decision_expires_at)}
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => {
                            void onDecision(item.action_run_id, 'approve');
                          }}
                          disabled={actionBusy}
                          className={`${buttonStyles.primary} px-3 py-1.5 text-xs`}
                        >
                          {decisionLoadingKey === `${item.action_run_id}:approve`
                            ? 'Approving...'
                            : 'Approve'}
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            void onDecision(item.action_run_id, 'reject');
                          }}
                          disabled={actionBusy}
                          className={`${buttonStyles.danger} px-3 py-1.5 text-xs`}
                        >
                          {decisionLoadingKey === `${item.action_run_id}:reject`
                            ? 'Rejecting...'
                            : 'Reject'}
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            void onDecision(item.action_run_id, 'block');
                          }}
                          disabled={actionBusy}
                          className={`${buttonStyles.danger} px-3 py-1.5 text-xs`}
                        >
                          {decisionLoadingKey === `${item.action_run_id}:block`
                            ? 'Blocking...'
                            : 'Block'}
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </SectionCard>
        </div>

        <div id="approval-routing">
          <SectionCard
            title="Approval routing"
            description="Decision links go to these approvers when policy requires human approval."
          >

          {approvalSettingsError ? (
            <Notice tone="danger" className="mt-3 text-xs">
              {approvalSettingsError}
            </Notice>
          ) : null}

          {saveSettingsMessage ? (
            <Notice tone="success" className="mt-3 text-xs">
              {saveSettingsMessage}
            </Notice>
          ) : null}

          {saveSettingsError ? (
            <Notice tone="danger" className="mt-3 text-xs">
              {saveSettingsError}
            </Notice>
          ) : null}

          <form className="mt-3 space-y-3" onSubmit={(event) => void onSaveSettings(event)}>
            <div>
              <label className="block text-xs font-medium text-text" htmlFor="approval_email_1">
                Primary approver
              </label>
              <input
                id="approval_email_1"
                type="email"
                value={emailOne}
                onChange={(event) => setEmailOne(event.target.value)}
                placeholder="approver@client.com"
                className={`mt-1 ${fieldStyles}`}
                disabled={saveSettingsLoading}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-text" htmlFor="approval_email_2">
                Backup approver
              </label>
              <input
                id="approval_email_2"
                type="email"
                value={emailTwo}
                onChange={(event) => setEmailTwo(event.target.value)}
                placeholder="backup-approver@client.com"
                className={`mt-1 ${fieldStyles}`}
                disabled={saveSettingsLoading}
              />
            </div>
            <div>
              <label
                className="block text-xs font-medium text-text"
                htmlFor="approval_ttl_minutes"
              >
                Approval link expiry
              </label>
              <select
                id="approval_ttl_minutes"
                value={String(ttlMinutes)}
                onChange={(event) => setTtlMinutes(Number(event.target.value))}
                className={`mt-1 ${selectStyles}`}
                disabled={saveSettingsLoading}
              >
                {TTL_OPTIONS.map((option) => (
                  <option key={option.value} value={String(option.value)}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            <button
              type="submit"
              disabled={saveSettingsLoading}
              className={buttonStyles.primary}
            >
              {saveSettingsLoading ? 'Saving...' : 'Save approval settings'}
            </button>
          </form>
        </SectionCard>
      </div>
    </div>
    </div>
  );
}
