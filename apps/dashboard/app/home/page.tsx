import Link from 'next/link';

import { createWorkspaceAction } from '@/app/workspace-actions';
import { Breadcrumbs } from '@/components/breadcrumbs';
import {
  buttonStyles,
  fieldStyles,
  MetricCard,
  Notice,
  PageHeader,
  StatusBadge,
} from '@/components/console-ui';
import { FormSubmitButton } from '@/components/form-submit-button';
import { ErrorState } from '@/components/states';
import {
  fetchDashboardUsage,
  fetchWorkspaceActions,
  fetchWorkspaceMetrics,
  fetchWorkspaces,
} from '@/lib/api';
import { formatTimestamp } from '@/lib/format';
import type { DashboardUsage } from '@/lib/types';

function workspaceSummaryStatus({
  actionCount,
  pendingApprovalCount,
  status,
}: {
  actionCount: number | null;
  pendingApprovalCount: number | null;
  status: string;
}): { label: string; tone: 'success' | 'warning' | 'neutral' } {
  if (pendingApprovalCount !== null && pendingApprovalCount > 0) {
    return { label: 'Needs review', tone: 'warning' };
  }
  if (actionCount === 0) {
    return { label: 'Setup needed', tone: 'neutral' };
  }
  if (status === 'active') {
    return { label: 'Active', tone: 'success' };
  }
  return { label: status, tone: 'neutral' };
}

function decodeMessage(value: string | undefined): string | null {
  if (!value) {
    return null;
  }
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

const heroBullets = [
  'Govern one registered action before execution',
  'Add one SDK checkpoint to your Python app',
  'Review the decision and receipt in DAAI',
];

const flowStages = [
  {
    title: 'Create workspace',
    helper: 'One client environment for keys, actions, approvals, and receipts.',
  },
  {
    title: 'Register action',
    helper: (
      <>
        Example: <code className="font-mono text-text">send_invoice_reminder</code>
      </>
    ),
  },
  {
    title: 'Add SDK gate',
    helper: (
      <>
        Call <code className="font-mono text-text">client.intercept()</code> before the risky function.
      </>
    ),
    featured: true,
    rail: 'result = client.intercept(...)',
  },
  {
    title: 'Approve or block',
    helper: 'DAAI applies policy and asks for approval if needed.',
    rail: 'if result.executable: run action',
  },
  {
    title: 'Review receipt',
    helper: 'See the proposal, decision, and result.',
  },
];

function OnboardingHeroSection() {
  return (
    <section className="rounded-2xl border border-brand/20 bg-[radial-gradient(circle_at_top_left,rgba(62,207,142,0.14),transparent_34%),var(--panel)] p-6 shadow-card shadow-inset md:p-8 lg:p-10">
      <div className="grid gap-8 lg:grid-cols-[1.08fr_0.92fr] lg:items-center">
        <div className="max-w-3xl">
          <p className="text-xs font-semibold uppercase tracking-wide text-brand">START HERE</p>
          <h1 className="mt-4 text-3xl font-semibold tracking-tight text-text md:text-4xl">
            Create your first client workspace
          </h1>
          <p className="mt-4 max-w-2xl text-base leading-7 text-muted">
            Create a client workspace, register one risky action, add the Python
            SDK gate, and prove the approval-to-receipt path.
          </p>
          <ul className="mt-7 grid gap-3 text-sm text-muted">
            {heroBullets.map((bullet) => (
              <li key={bullet} className="flex items-center gap-3">
                <span className="h-1.5 w-1.5 rounded-full bg-brand" />
                <span>{bullet}</span>
              </li>
            ))}
          </ul>
          <div className="mt-8 flex flex-wrap gap-3">
            <a href="#create-workspace" className={buttonStyles.primary}>
              Create workspace
            </a>
            <Link href="/dashboard/documentation" className={buttonStyles.secondary}>
              View documentation
            </Link>
          </div>
        </div>

        <article className="rounded-2xl border border-border bg-canvas/80 p-5 shadow-card md:p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-base font-semibold text-text">What you are building</h2>
              <p className="mt-2 text-sm leading-6 text-muted">
                A developer-friendly approval gate for risky agent actions.
              </p>
            </div>
            <StatusBadge label="Python SDK" tone="brand" />
          </div>
          <div className="mt-6 space-y-3">
            {[
              ['Agent proposes', 'registered action request'],
              ['DAAI decides', 'allow, approval, or block'],
              ['Your app executes only if allowed', 'business logic stays in your app'],
            ].map(([title, helper], index) => (
              <div key={title} className="flex gap-3 rounded-xl border border-border bg-panel px-4 py-3">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-brand/30 bg-brand/10 font-mono text-xs font-semibold text-brand">
                  {index + 1}
                </span>
                <div>
                  <p className="text-sm font-semibold text-text">{title}</p>
                  <p className="mt-1 text-xs text-muted">{helper}</p>
                </div>
              </div>
            ))}
          </div>
        </article>
      </div>
    </section>
  );
}

function VisualOnboardingFlow() {
  return (
    <section className="space-y-5">
      <div>
        <h2 className="text-2xl font-semibold text-text">Your first governed action in 10 minutes</h2>
        <p className="mt-2 text-sm text-muted">
          A single flow to prove the product from proposal to receipt.
        </p>
      </div>

      <article
        className="overflow-hidden rounded-2xl border border-border bg-panel p-5 shadow-card md:p-7"
        style={{
          backgroundImage: 'radial-gradient(circle, rgba(40,50,45,0.7) 1px, transparent 1px)',
          backgroundSize: '26px 26px',
        }}
      >
        <div className="grid gap-5 lg:grid-cols-5 lg:items-stretch">
          {flowStages.map((stage, index) => (
            <div key={stage.title} className="relative">
              <article
                className={`flex h-full flex-col rounded-2xl border p-5 transition ${
                  stage.featured
                    ? 'border-brand/60 bg-brand/10 shadow-[0_18px_42px_rgba(62,207,142,0.12)]'
                    : 'border-border bg-canvas/90'
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <span
                    className={`flex h-8 w-8 items-center justify-center rounded-full border font-mono text-xs font-semibold ${
                      stage.featured
                        ? 'border-brand/50 bg-brand/10 text-brand'
                        : 'border-borderStrong bg-panel text-muted'
                    }`}
                  >
                    {index + 1}
                  </span>
                  {stage.featured ? <StatusBadge label="Adapt here" tone="brand" /> : null}
                </div>
                <h3 className="mt-5 text-base font-semibold text-text">{stage.title}</h3>
                <p className="mt-2 text-sm leading-6 text-muted">{stage.helper}</p>
                {stage.rail ? (
                  <div className="mt-5 rounded-lg border border-border bg-background px-3 py-2">
                    <code className="font-mono text-xs text-text">{stage.rail}</code>
                  </div>
                ) : null}
              </article>
              {index < flowStages.length - 1 ? (
                <span className="absolute -right-4 top-1/2 z-10 hidden -translate-y-1/2 rounded-full border border-border bg-panel px-2 py-1 text-xs text-muted lg:block">
                  -&gt;
                </span>
              ) : null}
              {index < flowStages.length - 1 ? (
                <div className="flex justify-center py-1 text-xs text-subtle lg:hidden">v</div>
              ) : null}
            </div>
          ))}
        </div>
      </article>
    </section>
  );
}

function TestAgentQuickstartCard() {
  return (
    <section className="rounded-lg border border-brand/30 bg-brand/10 p-5 shadow-card">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-wide text-brand">
            Test agent script
          </p>
          <h2 className="mt-2 text-lg font-semibold text-text">
            Download a sample invoice reminder agent
          </h2>
          <p className="mt-2 text-sm leading-6 text-muted">
            Use this local script to propose{' '}
            <code className="font-mono text-text">send_invoice_reminder</code> and
            see DAAI pause, allow, or block it before simulated execution.
          </p>
        </div>
        <a
          href="/examples/send_invoice_reminder_agent.py"
          download
          className={buttonStyles.primary}
        >
          Download script
        </a>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="rounded-lg border border-border bg-canvas p-4">
          <p className="text-sm font-semibold text-text">Quick start</p>
          <ol className="mt-3 space-y-2 text-sm leading-6 text-muted">
            <li>1. Save the file as <code className="font-mono text-text">~/Documents/daai-test-agent/send_invoice_reminder_agent.py</code>.</li>
            <li>2. Install the SDK with <code className="font-mono text-text">pip install daai-python</code>.</li>
            <li>3. Export your DAAI keys from workspace setup, then run <code className="font-mono text-text">python send_invoice_reminder_agent.py</code>.</li>
          </ol>
        </div>
        <pre className="overflow-x-auto rounded-lg border border-border bg-background p-4 text-xs leading-6 text-text">
          <code>{`mkdir -p ~/Documents/daai-test-agent
cd ~/Documents/daai-test-agent
python send_invoice_reminder_agent.py`}</code>
        </pre>
      </div>
    </section>
  );
}

function CreateWorkspaceCard({
  errorMessage,
  usage,
  compact = false,
}: {
  errorMessage: string | undefined;
  usage?: DashboardUsage | null;
  compact?: boolean;
}) {
  const workspaceLimitReached = Boolean(
    usage && usage.client_workspaces.used >= usage.client_workspaces.limit,
  );
  const form = (
    <form
      action={createWorkspaceAction}
      className={`rounded-lg border border-border bg-canvas p-5 ${
        errorMessage ? 'mt-4' : ''
      }`}
    >
      <div className="grid gap-5 md:grid-cols-2">
        <div>
          <label htmlFor="workspace_name" className="block text-sm font-medium text-text">
            Workspace name
          </label>
          <input
            id="workspace_name"
            name="workspace_name"
            type="text"
            required
            maxLength={160}
            className={`mt-2 ${fieldStyles}`}
            placeholder="Acme Finance Workspace"
          />
        </div>

        <div>
          <label htmlFor="client_name" className="block text-sm font-medium text-text">
            Client name
          </label>
          <input
            id="client_name"
            name="client_name"
            type="text"
            required
            maxLength={160}
            className={`mt-2 ${fieldStyles}`}
            placeholder="Acme Finance"
          />
        </div>

        <div className="md:col-span-2">
          <FormSubmitButton
            label="Create workspace"
            loadingLabel="Creating workspace..."
            disabled={workspaceLimitReached}
            className={buttonStyles.primary}
          />
        </div>
      </div>
    </form>
  );

  if (compact) {
    return (
      <section id="create-workspace" className="rounded-lg border border-border bg-panel p-5 shadow-card">
        <details open={Boolean(errorMessage)}>
          <summary className="cursor-pointer list-none">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold text-text">Create another workspace</h2>
                <p className="mt-1 text-sm text-muted">
                  Add a separate client environment when you need distinct actions, approvals, and history.
                </p>
              </div>
              <span className={buttonStyles.secondary}>Create workspace</span>
            </div>
          </summary>

          <div className="mt-4">
            {errorMessage ? <Notice tone="danger">{errorMessage}</Notice> : null}
            {workspaceLimitReached ? (
              <Notice tone="warning" className={errorMessage ? 'mt-3' : ''}>
                Beta limit reached. Usage is capped during launch to protect reliability.
              </Notice>
            ) : null}
            {form}
          </div>
        </details>
      </section>
    );
  }

  return (
    <section id="create-workspace" className="rounded-lg border border-border bg-panel p-6 shadow-card md:p-8">
      <div className="grid gap-8 lg:grid-cols-[0.9fr_1.1fr]">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">First real step</p>
          <h2 className="mt-3 text-2xl font-semibold text-text">
            Create your first client workspace
          </h2>
          <p className="mt-3 text-sm leading-6 text-muted">
            Each workspace keeps one client&apos;s keys, registered actions,
            approval policy, approval routing, and audit history separate.
          </p>

          <div className="mt-7 rounded-lg border border-border bg-canvas p-5">
            <p className="text-sm font-semibold text-text">How to name the first workspace</p>
            <p className="mt-2 text-sm leading-6 text-muted">
              Use the client name and automation area so actions, approvals, and
              receipts stay easy to audit later.
            </p>
            <div className="mt-5 grid gap-3 text-sm">
              <div className="rounded-xl border border-border bg-panel px-4 py-3">
                <p className="text-xs uppercase text-subtle">Workspace</p>
                <p className="mt-1 text-text">Acme Finance Workspace</p>
              </div>
              <div className="rounded-xl border border-border bg-panel px-4 py-3">
                <p className="text-xs uppercase text-subtle">Client</p>
                <p className="mt-1 text-text">Acme Finance</p>
              </div>
            </div>
            <p className="mt-5 text-sm text-muted">
              Start with one real workflow, not your whole automation system.
            </p>
          </div>
        </div>

        <div>
          {errorMessage ? (
            <Notice tone="danger">
              {errorMessage}
            </Notice>
          ) : null}
          {workspaceLimitReached ? (
            <Notice tone="warning" className={errorMessage ? 'mt-3' : ''}>
              Beta limit reached. Usage is capped during launch to protect reliability.
            </Notice>
          ) : null}

          {form}
        </div>
      </div>
    </section>
  );
}

function BetaUsagePanel({ usage }: { usage: DashboardUsage | null }) {
  if (!usage) {
    return null;
  }

  return (
    <section className="rounded-lg border border-border bg-panel p-5 shadow-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-text">Beta usage</h2>
          <p className="mt-1 text-sm text-muted">Launch caps while billing is offline.</p>
        </div>
        <StatusBadge label={usage.plan} tone="brand" />
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Client workspaces"
          value={`${usage.client_workspaces.used} / ${usage.client_workspaces.limit}`}
          tone={
            usage.client_workspaces.used >= usage.client_workspaces.limit
              ? 'warning'
              : 'neutral'
          }
          compact
        />
        <MetricCard
          label="Registered actions"
          value="Open a workspace"
          description="Shown per workspace"
          compact
        />
        <MetricCard
          label="Action-run audit records"
          value={`${usage.action_runs_this_month.used} / ${usage.action_runs_this_month.limit}`}
          compact
        />
        <MetricCard
          label="Approval emails"
          value={`${usage.approval_emails_this_month.used} / ${usage.approval_emails_this_month.limit}`}
          compact
        />
      </div>
    </section>
  );
}

export default async function HomePage(
  props: {
    searchParams?: Promise<{ create_error?: string; deleted?: string }>;
  }
) {
  const searchParams = await props.searchParams;
  const [{ data: workspaces, error }, usageResult] = await Promise.all([
    fetchWorkspaces(),
    fetchDashboardUsage(),
  ]);

  if (error) {
    return <ErrorState title="Home Unavailable" message={error} />;
  }

  const createError = searchParams?.create_error;
  const deletedWorkspaceName = decodeMessage(searchParams?.deleted);

  if (!workspaces || workspaces.length === 0) {
    return (
      <section className="space-y-12">
        <Breadcrumbs items={[{ label: 'Home' }]} />

        <OnboardingHeroSection />
        {deletedWorkspaceName ? (
          <Notice tone="success">Workspace deleted: {deletedWorkspaceName}</Notice>
        ) : null}
        <BetaUsagePanel usage={usageResult.data} />
        {usageResult.error ? <Notice tone="warning">{usageResult.error}</Notice> : null}
        <TestAgentQuickstartCard />
        <CreateWorkspaceCard errorMessage={createError} usage={usageResult.data} />
        <VisualOnboardingFlow />
      </section>
    );
  }

  const summaries = await Promise.all(
    workspaces.map(async (workspace) => {
      const [actionsResult, metricsResult] = await Promise.all([
        fetchWorkspaceActions(workspace.id),
        fetchWorkspaceMetrics(workspace.id),
      ]);

      return {
        workspace,
        actionCount: actionsResult.data?.length ?? null,
        runCount: metricsResult.data?.total_runs ?? null,
        pendingApprovalCount: metricsResult.data?.pending_approval ?? null,
      };
    }),
  );

  return (
    <section className="space-y-5">
      <Breadcrumbs items={[{ label: 'Home' }]} />

      <PageHeader
        title="Workspaces"
        description="Choose a client automation environment to configure registered actions, approval routing, and governed run history."
        actions={
          usageResult.data &&
          usageResult.data.client_workspaces.used >= usageResult.data.client_workspaces.limit ? (
            <button type="button" disabled className={buttonStyles.primary}>
              Create workspace
            </button>
          ) : (
            <a href="#create-workspace" className={buttonStyles.primary}>
              Create workspace
            </a>
          )
        }
      />

      {deletedWorkspaceName ? (
        <Notice tone="success">Workspace deleted: {deletedWorkspaceName}</Notice>
      ) : null}
      <BetaUsagePanel usage={usageResult.data} />
      {usageResult.error ? <Notice tone="warning">{usageResult.error}</Notice> : null}
      <TestAgentQuickstartCard />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {summaries.map(({ workspace, actionCount, runCount, pendingApprovalCount }) => {
          const status = workspaceSummaryStatus({
            actionCount,
            pendingApprovalCount,
            status: workspace.status,
          });

          return (
            <article
              key={workspace.id}
              className="rounded-lg border border-border bg-panel p-5 shadow-card transition hover:border-borderStrong hover:bg-panelHover"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="break-words text-base font-semibold text-text">
                    {workspace.name}
                  </h2>
                  <p className="mt-1 text-sm text-muted">
                    {workspace.client_name ?? 'Client name not set'}
                  </p>
                </div>
                <StatusBadge label={status.label} tone={status.tone} />
              </div>

              <p className="mt-3 text-xs text-muted">
                Created {formatTimestamp(workspace.created_at)}
              </p>

              <div className="mt-5 grid grid-cols-3 gap-3 border-t border-border pt-4">
                <div>
                  <p className="text-xs font-medium uppercase text-subtle">Actions</p>
                  <p className="mt-1 font-semibold text-text">
                    {actionCount === null ? 'N/A' : actionCount}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-medium uppercase text-subtle">Runs</p>
                  <p className="mt-1 font-semibold text-text">
                    {runCount === null ? 'N/A' : runCount}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-medium uppercase text-subtle">Pending</p>
                  <p
                    className={`mt-1 font-semibold ${
                      pendingApprovalCount !== null && pendingApprovalCount > 0
                        ? 'text-warning'
                        : 'text-text'
                    }`}
                  >
                    {pendingApprovalCount === null ? 'N/A' : pendingApprovalCount}
                  </p>
                </div>
              </div>

              <div className="mt-5 flex flex-wrap items-center gap-3">
                <Link href={`/workspaces/${workspace.id}`} className={buttonStyles.primary}>
                  Open workspace
                </Link>
                {actionCount === 0 ? (
                  <Link
                    href={`/workspaces/${workspace.id}/setup`}
                    className="text-sm font-medium text-muted transition hover:text-text"
                  >
                    Setup
                  </Link>
                ) : null}
              </div>
            </article>
          );
        })}
      </div>

      <CreateWorkspaceCard errorMessage={createError} usage={usageResult.data} compact />
    </section>
  );
}
