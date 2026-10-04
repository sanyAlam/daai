import Link from 'next/link';

import { Breadcrumbs } from '@/components/breadcrumbs';
import {
  buttonStyles,
  Notice,
  PageHeader,
  SectionCard,
  StatusBadge,
} from '@/components/console-ui';
import { ErrorState, NotFoundState } from '@/components/states';
import { WorkspaceOverviewAuditSection } from '@/components/workspace-overview-audit-section';
import { WorkspaceTabs } from '@/components/workspace-tabs';
import {
  fetchDashboardApiKeys,
  fetchWorkspace,
  fetchWorkspaceActions,
  fetchWorkspaceApprovalSettings,
  fetchWorkspaceKeyInfo,
  fetchWorkspaceMetrics,
  fetchWorkspacePendingApprovals,
} from '@/lib/api';
import { formatTimestamp } from '@/lib/format';

function workspaceStatusTone(status: string): 'success' | 'neutral' {
  return status === 'active' ? 'success' : 'neutral';
}

function maskIdentifier(value: string | null | undefined): string {
  if (!value) {
    return 'Unavailable';
  }
  if (value.length <= 12) {
    return `${value.slice(0, 4)}...`;
  }
  return `${value.slice(0, 8)}...${value.slice(-4)}`;
}

type ReadinessState = 'complete' | 'next' | 'later';

function ReadinessItem({
  title,
  state,
}: {
  title: string;
  state: ReadinessState;
}) {
  const label = state === 'complete' ? 'Complete' : state === 'next' ? 'Next' : 'Later';
  const tone = state === 'complete' ? 'success' : state === 'next' ? 'warning' : 'neutral';

  return (
    <div className="flex min-w-0 items-center gap-2 rounded-md border border-border bg-canvas px-3 py-2">
      <span
        className={`h-2 w-2 shrink-0 rounded-full ${
          state === 'complete'
            ? 'bg-success'
            : state === 'next'
              ? 'bg-warning'
              : 'bg-borderStrong'
        }`}
      />
      <p className="truncate text-sm font-medium text-text">{title}</p>
      <StatusBadge label={label} tone={tone} />
    </div>
  );
}

function nextState(isComplete: boolean, isFirstIncomplete: boolean): ReadinessState {
  if (isComplete) {
    return 'complete';
  }
  return isFirstIncomplete ? 'next' : 'later';
}

function NextActionCard({
  title,
  description,
  primaryHref,
  primaryLabel,
  secondaryHref,
  secondaryLabel,
  urgent = false,
}: {
  title: string;
  description: string;
  primaryHref: string;
  primaryLabel: string;
  secondaryHref?: string;
  secondaryLabel?: string;
  urgent?: boolean;
}) {
  return (
    <SectionCard className={urgent ? 'border-warning/40 bg-warning/10' : undefined}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-3xl">
          <p className="text-xs font-medium uppercase text-muted">Next action</p>
          <h2 className="mt-2 text-xl font-semibold text-text">{title}</h2>
          <p className="mt-2 text-sm leading-6 text-muted">{description}</p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <Link href={primaryHref} className={buttonStyles.primary}>
            {primaryLabel}
          </Link>
          {secondaryHref && secondaryLabel ? (
            <Link href={secondaryHref} className={buttonStyles.secondary}>
              {secondaryLabel}
            </Link>
          ) : null}
        </div>
      </div>
    </SectionCard>
  );
}

export default async function WorkspaceOverviewPage(
  props: {
    params: Promise<{ workspaceId: string }>;
  }
) {
  const params = await props.params;
  const [
    workspaceResult,
    actionsResult,
    metricsResult,
    keyInfoResult,
    apiKeysResult,
    approvalSettingsResult,
    pendingApprovalsResult,
  ] = await Promise.all([
    fetchWorkspace(params.workspaceId),
    fetchWorkspaceActions(params.workspaceId),
    fetchWorkspaceMetrics(params.workspaceId),
    fetchWorkspaceKeyInfo(params.workspaceId),
    fetchDashboardApiKeys(),
    fetchWorkspaceApprovalSettings(params.workspaceId),
    fetchWorkspacePendingApprovals(params.workspaceId),
  ]);

  if (workspaceResult.error) {
    return <ErrorState title="Workspace Unavailable" message={workspaceResult.error} />;
  }

  const workspace = workspaceResult.data;
  if (!workspace) {
    return (
      <NotFoundState
        title="Workspace not found"
        message="The workspace could not be loaded in the current scope."
      />
    );
  }

  const actionCount = actionsResult.data?.length ?? 0;
  const metrics = metricsResult.data;
  const runCount = metrics?.total_runs ?? 0;
  const keyInfo = keyInfoResult.data;
  const keyInfoError = keyInfoResult.error;
  const approvalEmailCount = approvalSettingsResult.data?.approval_emails.length ?? 0;
  const activeApiKeyCount =
    apiKeysResult.data?.filter(
      (apiKey) => apiKey.workspace_id === workspace.id && apiKey.status === 'active',
    ).length ?? 0;
  const hasWorkspaceKey = Boolean(keyInfo?.key_identifier);
  const hasApiKey = activeApiKeyCount > 0;
  const hasActions = actionCount > 0;
  const hasTestRun = runCount > 0;
  const pendingApprovalCount = pendingApprovalsResult.data?.length ?? 0;
  const readinessChecks = [
    { title: 'Workspace created', complete: true },
    { title: 'API key available', complete: hasApiKey },
    { title: 'Approval email configured', complete: approvalEmailCount > 0 },
    { title: 'Action registered', complete: hasActions },
    { title: 'Test run received', complete: hasTestRun },
  ];
  const firstIncompleteCheck = readinessChecks.findIndex((check) => !check.complete);

  const nextAction = !hasApiKey
    ? {
        title: 'Create or verify API key',
        description: 'The SDK needs a workspace-scoped API key before it can propose governed actions.',
        primaryHref: '/account',
        primaryLabel: 'Manage API keys',
        secondaryHref: `/workspaces/${workspace.id}/setup`,
        secondaryLabel: 'Open setup',
      }
    : !hasWorkspaceKey
      ? {
          title: 'Verify workspace key',
          description: 'Use Setup to get the workspace key used by this client automation environment.',
          primaryHref: `/workspaces/${workspace.id}/setup`,
          primaryLabel: 'Manage keys in Setup',
        }
      : approvalEmailCount === 0
        ? {
            title: 'Configure approval email',
            description: 'Add an approver so actions that require human approval have a decision route.',
            primaryHref: '#approval-routing',
            primaryLabel: 'Configure approval',
          }
        : !hasActions
          ? {
              title: 'Register your first action',
              description: 'Register the exact risky action name before the Python SDK proposes it.',
              primaryHref: `/workspaces/${workspace.id}/actions/new`,
              primaryLabel: 'Register action',
            }
          : !hasTestRun
            ? {
                title: 'Run your first test action',
                description: 'Send one SDK proposal, then review the governed run and its receipt.',
                primaryHref: `/workspaces/${workspace.id}/setup`,
                primaryLabel: 'Continue setup',
                secondaryHref: `/workspaces/${workspace.id}/runs`,
                secondaryLabel: 'View runs',
              }
            : pendingApprovalCount > 0
              ? {
                  title: 'Review pending approvals',
                  description: 'A governed action is waiting for a client decision.',
                  primaryHref: '#pending-approvals',
                  primaryLabel: 'Review approvals',
                  secondaryHref: `/workspaces/${workspace.id}/runs`,
                  secondaryLabel: 'View runs',
                  urgent: true,
                }
              : {
                  title: 'Workspace is ready',
                  description: 'Keys, approval routing, action registration, and a first run are in place.',
                  primaryHref: `/workspaces/${workspace.id}/runs`,
                  primaryLabel: 'Review runs',
                  secondaryHref: `/workspaces/${workspace.id}/receipts`,
                  secondaryLabel: 'View receipts',
                };

  return (
    <section className="space-y-5">
      <Breadcrumbs
        items={[
          { label: 'Home', href: '/home' },
          { label: 'Workspace' },
        ]}
      />

      <WorkspaceTabs workspaceId={workspace.id} />

      <PageHeader
        eyebrow="Workspace"
        title={workspace.name}
        description={workspace.client_name ?? 'Client name not set'}
        actions={
          <>
            <Link href={`/workspaces/${workspace.id}/setup`} className={buttonStyles.primary}>
              Continue setup
            </Link>
            <Link href={`/workspaces/${workspace.id}/runs`} className={buttonStyles.secondary}>
              View runs
            </Link>
          </>
        }
        meta={
          <div className="grid gap-3 md:grid-cols-3">
            <div>
              <p className="text-xs font-medium uppercase text-subtle">Status</p>
              <div className="mt-1">
                <StatusBadge
                  label={workspace.status}
                  tone={workspaceStatusTone(workspace.status)}
                />
              </div>
            </div>
            <div>
              <p className="text-xs font-medium uppercase text-subtle">Workspace key</p>
              <p className="mt-1 font-mono text-xs text-text">
                {maskIdentifier(keyInfo?.key_identifier)}
              </p>
              <Link
                href={`/workspaces/${workspace.id}/setup`}
                className="mt-1 inline-flex text-xs font-medium text-muted transition hover:text-text"
              >
                Manage keys in Setup
              </Link>
            </div>
            <div>
              <p className="text-xs font-medium uppercase text-subtle">Created</p>
              <p className="mt-1 text-sm text-text">{formatTimestamp(workspace.created_at)}</p>
            </div>
            <details className="md:col-span-3">
              <summary className="cursor-pointer text-xs font-medium text-muted transition hover:text-text">
                Workspace details
              </summary>
              <p className="mt-2 break-all font-mono text-xs text-text">{workspace.id}</p>
            </details>
          </div>
        }
      />

      <NextActionCard
        title={nextAction.title}
        description={nextAction.description}
        primaryHref={nextAction.primaryHref}
        primaryLabel={nextAction.primaryLabel}
        secondaryHref={nextAction.secondaryHref}
        secondaryLabel={nextAction.secondaryLabel}
        urgent={nextAction.urgent}
      />

      <SectionCard
        title="Readiness"
        description="A compact view of the first integration path."
      >
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-5">
          {readinessChecks.map((check, index) => (
            <ReadinessItem
              key={check.title}
              title={check.title}
              state={nextState(check.complete, firstIncompleteCheck === index)}
            />
          ))}
        </div>
        <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 border-t border-border pt-4 text-sm">
          <Link
            href={`/workspaces/${workspace.id}/actions`}
            className="font-medium text-muted transition hover:text-text"
          >
            Register actions
          </Link>
          <Link
            href={`/workspaces/${workspace.id}/runs`}
            className="font-medium text-muted transition hover:text-text"
          >
            View runs
          </Link>
          <Link
            href={`/workspaces/${workspace.id}/receipts`}
            className="font-medium text-muted transition hover:text-text"
          >
            View receipts
          </Link>
        </div>
      </SectionCard>

      <WorkspaceOverviewAuditSection
        workspaceId={workspace.id}
        initialMetrics={metrics}
        initialMetricsError={metricsResult.error}
        initialApprovalSettings={approvalSettingsResult.data}
        initialApprovalSettingsError={approvalSettingsResult.error}
        initialPendingApprovals={pendingApprovalsResult.data ?? []}
        initialPendingApprovalsError={pendingApprovalsResult.error}
      />

      {keyInfoError ? (
        <Notice tone="warning">
          {keyInfoError}
        </Notice>
      ) : null}
      {apiKeysResult.error ? <Notice tone="warning">{apiKeysResult.error}</Notice> : null}
    </section>
  );
}
