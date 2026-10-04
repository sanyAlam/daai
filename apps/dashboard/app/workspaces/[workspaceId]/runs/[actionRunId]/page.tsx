import {
  ExecutableBadge,
  ExecutionStatusBadge,
  GovernanceStatusBadge,
} from '@/components/badges';
import { Breadcrumbs } from '@/components/breadcrumbs';
import { CodeBlockWithCopy } from '@/components/code-block-with-copy';
import {
  KeyValueGrid,
  Notice,
  PageHeader,
  SectionCard,
  StatusBadge,
} from '@/components/console-ui';
import { ErrorState, NotFoundState } from '@/components/states';
import { WorkspaceTabs } from '@/components/workspace-tabs';
import { fetchWorkspace, fetchWorkspaceRunDetail } from '@/lib/api';
import { formatJson, formatTimestamp } from '@/lib/format';
import { ActionRunDetail, ExecutionStatus, GovernanceStatus } from '@/lib/types';

function governanceTone(value: GovernanceStatus): 'success' | 'warning' | 'danger' {
  if (value === 'allowed' || value === 'approved') {
    return 'success';
  }
  if (value === 'pending_approval') {
    return 'warning';
  }
  return 'danger';
}

function executionTone(value: ExecutionStatus): 'success' | 'warning' | 'danger' | 'neutral' {
  if (value === 'executed') {
    return 'success';
  }
  if (value === 'failed') {
    return 'danger';
  }
  if (value === 'awaiting_execution_report') {
    return 'warning';
  }
  return 'neutral';
}

function needsApproval(status: GovernanceStatus): boolean {
  return (
    status === 'pending_approval' ||
    status === 'approved' ||
    status === 'rejected'
  );
}

function receiptTone(outcome: string | undefined): 'success' | 'danger' | 'neutral' {
  if (outcome === 'allowed' || outcome === 'approved') {
    return 'success';
  }
  if (outcome === 'blocked' || outcome === 'rejected') {
    return 'danger';
  }
  return 'neutral';
}

function TimelineItem({
  title,
  detail,
  state,
}: {
  title: string;
  detail: string;
  state: 'complete' | 'current' | 'pending';
}) {
  const tone = state === 'complete' ? 'success' : state === 'current' ? 'warning' : 'neutral';

  return (
    <div className="relative flex gap-3 pb-5 last:pb-0">
      <div className="flex flex-col items-center">
        <span
          className={`h-3 w-3 rounded-full border ${
            state === 'complete'
              ? 'border-success bg-success'
              : state === 'current'
                ? 'border-warning bg-warning'
                : 'border-borderStrong bg-panelHover'
          }`}
        />
        <span className="mt-1 h-full w-px bg-border last:hidden" />
      </div>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm font-semibold text-text">{title}</p>
          <StatusBadge label={state} tone={tone} />
        </div>
        <p className="mt-1 text-sm text-muted">{detail}</p>
      </div>
    </div>
  );
}

function buildTimeline(run: ActionRunDetail) {
  const approvalApplies = needsApproval(run.governance_status);
  const decisionComplete = run.governance_status !== 'pending_approval';

  return [
    {
      title: 'Proposed',
      detail: `Action proposed at ${formatTimestamp(run.created_at)}.`,
      state: 'complete' as const,
    },
    {
      title: 'Policy evaluated',
      detail: run.governance_reason,
      state: 'complete' as const,
    },
    {
      title: 'Approval email sent',
      detail: approvalApplies
        ? 'This action entered the client approval path.'
        : 'This action did not require approval.',
      state: approvalApplies ? ('complete' as const) : ('pending' as const),
    },
    {
      title: 'Governance decision',
      detail: `Decision status is ${run.governance_status.replaceAll('_', ' ')}${
        run.decided_at ? ` at ${formatTimestamp(run.decided_at)}` : ''
      }.`,
      state: decisionComplete ? ('complete' as const) : ('current' as const),
    },
    {
      title: 'Execution reported',
      detail: run.execution_reported_at
        ? `Connected system reported ${run.execution_status.replaceAll('_', ' ')} at ${formatTimestamp(
            run.execution_reported_at,
          )}.`
        : 'No execution report has been received yet.',
      state: run.execution_reported_at ? ('complete' as const) : ('pending' as const),
    },
    {
      title: 'Receipt generated',
      detail: run.receipt
        ? `Receipt outcome is ${run.receipt.outcome}.`
        : 'No receipt is available for this run yet.',
      state: run.receipt ? ('complete' as const) : ('pending' as const),
    },
  ];
}

export default async function ActionRunDetailPage(
  props: {
    params: Promise<{ workspaceId: string; actionRunId: string }>;
  }
) {
  const params = await props.params;
  const [workspaceResult, runResult] = await Promise.all([
    fetchWorkspace(params.workspaceId),
    fetchWorkspaceRunDetail(params.workspaceId, params.actionRunId),
  ]);

  if (workspaceResult.error) {
    return <ErrorState title="Workspace Unavailable" message={workspaceResult.error} />;
  }

  if (runResult.error) {
    return <ErrorState title="Run Detail Unavailable" message={runResult.error} />;
  }

  const workspace = workspaceResult.data;
  const run = runResult.data;

  if (!workspace || !run) {
    return (
      <NotFoundState
        title="Action run not found"
        message="The run could not be loaded inside the current workspace scope."
      />
    );
  }

  const approvalApplies = needsApproval(run.governance_status);
  const timeline = buildTimeline(run);

  return (
    <section className="space-y-5">
      <Breadcrumbs
        items={[
          { label: 'Home', href: '/home' },
          { label: 'Workspace', href: `/workspaces/${workspace.id}` },
          { label: 'Runs', href: `/workspaces/${workspace.id}/runs` },
          { label: 'Action Run Detail' },
        ]}
      />

      <WorkspaceTabs workspaceId={workspace.id} />

      <PageHeader
        eyebrow="Action story"
        title={run.action}
        description={
          <>
            Run ID:{' '}
            <span className="font-mono text-xs text-muted">{run.action_run_id}</span>
          </>
        }
        meta={
          <div className="grid gap-3 md:grid-cols-4">
            <div>
              <p className="text-xs font-medium uppercase text-subtle">Governance</p>
              <div className="mt-1">
                <GovernanceStatusBadge value={run.governance_status} />
              </div>
            </div>
            <div>
              <p className="text-xs font-medium uppercase text-subtle">Execution</p>
              <div className="mt-1">
                <ExecutionStatusBadge value={run.execution_status} />
              </div>
            </div>
            <div>
              <p className="text-xs font-medium uppercase text-subtle">Executable</p>
              <div className="mt-1">
                <ExecutableBadge value={run.executable} />
              </div>
            </div>
            <div>
              <p className="text-xs font-medium uppercase text-subtle">Created</p>
              <p className="mt-1 text-sm text-text">{formatTimestamp(run.created_at)}</p>
            </div>
          </div>
        }
      />

      <SectionCard title="Timeline" description="Governance, approval, execution, and receipt progression for this action.">
        <div className="rounded-lg border border-border bg-canvas p-4">
          {timeline.map((item) => (
            <TimelineItem
              key={item.title}
              title={item.title}
              detail={item.detail}
              state={item.state}
            />
          ))}
        </div>
      </SectionCard>

      <SectionCard title="Run summary">
        <KeyValueGrid
          items={[
            { label: 'Action', value: run.action, mono: true },
            {
              label: 'Governance Status',
              value: (
                <StatusBadge
                  label={run.governance_status.replaceAll('_', ' ')}
                  tone={governanceTone(run.governance_status)}
                />
              ),
            },
            {
              label: 'Execution Status',
              value: (
                <StatusBadge
                  label={run.execution_status.replaceAll('_', ' ')}
                  tone={executionTone(run.execution_status)}
                />
              ),
            },
            { label: 'Executable', value: run.executable ? 'true' : 'false' },
            { label: 'Created', value: formatTimestamp(run.created_at) },
            { label: 'Decided', value: formatTimestamp(run.decided_at) },
            {
              label: 'Execution Reported',
              value: formatTimestamp(run.execution_reported_at),
            },
          ]}
        />
      </SectionCard>

      <SectionCard title="Reasoning" description="The deterministic governance reason returned for this run.">
        <Notice tone={governanceTone(run.governance_status)}>
          {run.governance_reason}
        </Notice>
      </SectionCard>

      <SectionCard title="Source">
        <KeyValueGrid
          items={[
            { label: 'Workspace', value: workspace.name },
            { label: 'Workspace ID', value: workspace.id, mono: true },
            { label: 'Action Run ID', value: run.action_run_id, mono: true },
            { label: 'Action Name', value: run.action, mono: true },
          ]}
        />
      </SectionCard>

      <SectionCard title="Input payload">
        <CodeBlockWithCopy title="Payload JSON" code={formatJson(run.payload)} />
      </SectionCard>

      <SectionCard title="Policy snapshot">
        <CodeBlockWithCopy title="Policy JSON" code={formatJson(run.policy_snapshot)} />
      </SectionCard>

      <SectionCard title="Approval snapshot">
        <KeyValueGrid
          items={[
            {
              label: 'Approval Required',
              value: approvalApplies ? 'yes' : 'no',
            },
            {
              label: 'Decision',
              value: run.governance_status.replaceAll('_', ' '),
            },
            {
              label: 'Decision Time',
              value: formatTimestamp(run.decided_at),
            },
            {
              label: 'Approval Path',
              value: approvalApplies
                ? 'client approval flow was used or is pending'
                : 'approval email was not required for this policy outcome',
            },
          ]}
        />
      </SectionCard>

      <SectionCard title="Execution result">
        <KeyValueGrid
          items={[
            {
              label: 'Execution Status',
              value: (
                <StatusBadge
                  label={run.execution_status.replaceAll('_', ' ')}
                  tone={executionTone(run.execution_status)}
                />
              ),
            },
            { label: 'Execution Error', value: run.execution_error ?? 'none' },
            { label: 'Execution Reported', value: formatTimestamp(run.execution_reported_at) },
          ]}
        />
        <CodeBlockWithCopy title="Execution JSON" code={formatJson(run.execution_result)} />
      </SectionCard>

      <SectionCard
        title="Receipt"
        description="Audit evidence generated by the governance flow for this run."
      >
        {run.receipt ? (
          <>
            <div className="mb-4">
              <KeyValueGrid
                items={[
                  {
                    label: 'Outcome',
                    value: (
                      <StatusBadge
                        label={run.receipt.outcome}
                        tone={receiptTone(run.receipt.outcome)}
                      />
                    ),
                  },
                  { label: 'Reason', value: run.receipt.reason },
                  { label: 'Policy Type', value: run.receipt.policy_type, mono: true },
                  { label: 'Created', value: formatTimestamp(run.receipt.created_at) },
                ]}
              />
            </div>
            <CodeBlockWithCopy title="Receipt JSON" code={formatJson(run.receipt)} />
          </>
        ) : (
          <EmptyReceiptNotice />
        )}
      </SectionCard>
    </section>
  );
}

function EmptyReceiptNotice() {
  return (
    <Notice tone="warning">
      No receipt is available for this run yet. Receipts appear when DAAI has an
      auditable governance outcome for the action.
    </Notice>
  );
}
