import Link from 'next/link';
import { headers } from 'next/headers';
import type { ReactNode } from 'react';

import { Breadcrumbs } from '@/components/breadcrumbs';
import { CodeBlockWithCopy } from '@/components/code-block-with-copy';
import {
  buttonStyles,
  Notice,
  SectionCard,
  StatusBadge,
  type Tone,
} from '@/components/console-ui';
import { createSupabaseServerClient } from '@/lib/supabase/server';
import { fetchWorkspaces, getApiBaseUrl } from '@/lib/api';
import type { Workspace } from '@/lib/types';

const docsNav = [
  { id: 'overview', label: 'Overview' },
  { id: 'quickstart', label: 'Quickstart' },
  { id: 'core-concepts', label: 'Core concepts' },
  { id: 'python-sdk', label: 'Python SDK' },
  { id: 'approval-flow', label: 'Approval flow' },
  { id: 'action-runner', label: 'Action runner' },
  { id: 'receipts', label: 'Receipts' },
  { id: 'free-beta-limits', label: 'Free beta limits' },
  { id: 'troubleshooting', label: 'Troubleshooting' },
];

const quickstartToc = [
  { id: 'create-workspace', label: 'Create workspace' },
  { id: 'install-sdk', label: 'Install SDK' },
  { id: 'set-keys', label: 'Set keys' },
  { id: 'register-action', label: 'Register action' },
  { id: 'call-intercept', label: 'Call intercept' },
  { id: 'approve-or-reject', label: 'Approve' },
  { id: 'review-receipt', label: 'Receipt' },
];

const flowSteps = [
  'Register an action in the dashboard',
  'Install the Python SDK',
  'Call DAAI before the risky function',
  'DAAI returns allowed, pending approval, or blocked',
  'Execute only when executable',
  'Report execution result',
  'Review the receipt',
];

const conceptCards = [
  {
    title: 'Registered action',
    body: (
      <>
        An action type configured in DAAI, such as{' '}
        <code className="font-mono text-text">send_invoice_reminder</code> or{' '}
        <code className="font-mono text-text">mark_invoice_paid</code>.
      </>
    ),
  },
  {
    title: 'Action run',
    body: 'One proposed execution of a registered action.',
  },
  {
    title: 'Policy',
    body: 'The deterministic rule DAAI uses to decide whether to allow, block, or request approval.',
  },
  {
    title: 'Approval',
    body: 'A human decision collected through a secure approval link.',
  },
  {
    title: 'Executable',
    body: (
      <>
        A boolean returned by DAAI. Your app should only execute the real action when{' '}
        <code className="font-mono text-text">executable</code> is true.
      </>
    ),
  },
  {
    title: 'Receipt',
    body: 'The audit record showing what was proposed, what DAAI decided, and what happened after execution was reported.',
  },
];

const lifecycleSteps = [
  'Propose',
  'Decide',
  'Approve if needed',
  'Execute locally',
  'Report result',
  'Receipt',
];

const governanceStatuses = [
  ['allowed', 'Policy allowed the action immediately.', 'success'],
  ['pending_approval', 'DAAI sent or attempted to send an approval request.', 'warning'],
  ['approved', 'A human approved the action. The app may execute if executable is true.', 'success'],
  ['rejected', 'A human rejected the action. The app must not execute.', 'danger'],
  ['blocked', 'Policy blocked the action. The app must not execute.', 'danger'],
] satisfies Array<[string, string, Tone]>;

const executionStatuses = [
  ['not_executed', 'The developer app has not reported execution.', 'neutral'],
  ['awaiting_execution_report', 'The action can execute and DAAI is waiting for the app result.', 'info'],
  ['executed', 'The developer app reported successful execution.', 'success'],
  ['failed', 'The developer app reported execution failure.', 'danger'],
] satisfies Array<[string, string, Tone]>;

const limitRows = [
  ['Client workspaces', '2 client workspaces'],
  ['Registered actions', '3 registered actions per workspace'],
  ['Audit records', '1,000 action-run audit records per month'],
  ['Approval emails', '100 approval emails per month'],
  ['SDK rate limits', 'Request limits that protect launch reliability'],
];

const troubleshooting = [
  {
    issue: 'pip install fails',
    advice:
      'Confirm you are using Python 3.9+ and try again in a fresh virtual environment.',
  },
  {
    issue: 'Authentication failed',
    advice:
      'Check DAAI_API_KEY and DAAI_WORKSPACE_KEY. Make sure both come from the same workspace.',
  },
  {
    issue: 'Unknown action blocked',
    advice:
      'Register the action name in the dashboard before calling intercept. The action string in code must exactly match the registered action name.',
  },
  {
    issue: 'Action is pending approval',
    advice:
      'This is expected when policy requires approval. Do not execute the real action yet. Approve it from the email link or dashboard flow.',
  },
  {
    issue: 'No approval email received',
    advice:
      'Check the approver email on the registered action. Check spam. Confirm the free beta approval email limit has not been reached.',
  },
  {
    issue: 'Payload too large',
    advice:
      'Send only the fields needed for policy and review. Do not send full documents, large emails, or raw files in the action payload.',
  },
];

function cx(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(' ');
}

function DocsSection({
  id,
  title,
  subtitle,
  children,
}: {
  id: string;
  title: string;
  subtitle?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-24 space-y-4">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight text-text">{title}</h2>
        {subtitle ? <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">{subtitle}</p> : null}
      </div>
      {children}
    </section>
  );
}

function DocsCard({
  title,
  children,
  className,
}: {
  title?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <article className={cx('rounded-lg border border-border bg-panel p-5 shadow-card', className)}>
      {title ? <h3 className="text-base font-semibold text-text">{title}</h3> : null}
      <div className={cx(title && 'mt-3', 'text-sm leading-6 text-muted')}>{children}</div>
    </article>
  );
}

function StepCard({
  id,
  number,
  title,
  children,
  action,
}: {
  id: string;
  number: number;
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <article
      id={id}
      className="scroll-mt-24 rounded-lg border border-border bg-panel p-5 shadow-card"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 gap-3">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-brand/40 bg-brand/10 font-mono text-xs font-semibold text-brand">
            {number}
          </span>
          <div className="min-w-0">
            <h3 className="text-base font-semibold text-text">{title}</h3>
            <div className="mt-2 text-sm leading-6 text-muted">{children}</div>
          </div>
        </div>
        {action ? <div className="flex shrink-0 flex-wrap gap-2">{action}</div> : null}
      </div>
    </article>
  );
}

function DocsSidebar() {
  return (
    <aside className="xl:sticky xl:top-6 xl:self-start">
      <nav
        aria-label="Documentation sections"
        className="rounded-lg border border-border bg-panel p-2 shadow-card"
      >
        <div className="flex gap-1 overflow-x-auto pb-1 xl:block xl:space-y-1 xl:overflow-visible xl:pb-0">
          {docsNav.map((item) => (
            <a
              key={item.id}
              href={`#${item.id}`}
              className="shrink-0 rounded-md px-3 py-2 text-sm font-medium text-muted transition hover:bg-panelHover hover:text-text xl:block"
            >
              {item.label}
            </a>
          ))}
        </div>
      </nav>
    </aside>
  );
}

function OnThisPage() {
  return (
    <aside className="hidden 2xl:block 2xl:sticky 2xl:top-6 2xl:self-start">
      <div className="rounded-lg border border-border bg-panel p-4 shadow-card">
        <p className="text-xs font-semibold uppercase text-subtle">On this page</p>
        <nav aria-label="Quickstart steps" className="mt-3 space-y-2">
          {quickstartToc.map((item) => (
            <a
              key={item.id}
              href={`#${item.id}`}
              className="block text-sm text-muted transition hover:text-text"
            >
              {item.label}
            </a>
          ))}
        </nav>
      </div>
    </aside>
  );
}

function WorkspaceDocCta({
  workspace,
  createWorkspaceHref = '/home#create-workspace',
}: {
  workspace: Workspace | null;
  createWorkspaceHref?: string;
}) {
  if (!workspace) {
    return (
      <DocsCard className="border-brand/30 bg-brand/10">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="font-semibold text-text">Create a workspace first.</p>
            <p className="mt-1">
              The examples below use placeholders until your workspace and keys exist.
            </p>
          </div>
          <Link href={createWorkspaceHref} className={buttonStyles.primary}>
            Create workspace
          </Link>
        </div>
      </DocsCard>
    );
  }

  return (
    <DocsCard className="border-brand/30 bg-brand/10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="font-semibold text-text">Continue setup for {workspace.name}</p>
          <p className="mt-1">
            Copy keys from setup, register the action, then watch runs and receipts.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href={`/workspaces/${workspace.id}/setup`} className={buttonStyles.primary}>
            Continue setup
          </Link>
          <Link href={`/workspaces/${workspace.id}/actions/new`} className={buttonStyles.secondary}>
            Register action
          </Link>
          <Link href={`/workspaces/${workspace.id}/runs`} className={buttonStyles.subtle}>
            View runs
          </Link>
        </div>
      </div>
    </DocsCard>
  );
}

function StatusGrid({
  items,
}: {
  items: Array<[string, string, Tone]>;
}) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {items.map(([label, description, tone]) => (
        <article key={label} className="rounded-lg border border-border bg-canvas p-4">
          <StatusBadge label={label} tone={tone} mono />
          <p className="mt-3 text-sm leading-6 text-muted">{description}</p>
        </article>
      ))}
    </div>
  );
}

function LimitTable() {
  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-canvas">
      <table className="min-w-full divide-y divide-border text-left text-sm">
        <thead className="bg-panel">
          <tr>
            <th scope="col" className="px-4 py-3 font-semibold text-text">
              Free beta includes
            </th>
            <th scope="col" className="px-4 py-3 font-semibold text-text">
              Limit
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {limitRows.map(([label, value]) => (
            <tr key={label}>
              <td className="px-4 py-3 text-muted">{label}</td>
              <td className="px-4 py-3 text-text">{value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default async function DocumentationPage() {
  const pathname = (await headers()).get('x-daai-pathname');
  const apiBaseUrl = getApiBaseUrl();
  const supabase = createSupabaseServerClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  const publicView =
    pathname === '/documentation' || (pathname === '/dashboard/documentation' && !user);
  const shouldPersonalizeWorkspaceLinks = Boolean(user) && !publicView;
  const workspacesResult = shouldPersonalizeWorkspaceLinks
    ? await fetchWorkspaces()
    : { data: null, error: null };
  const firstWorkspace = workspacesResult.data?.[0] ?? null;
  const homeHref = publicView ? '/' : '/home';
  const createWorkspaceHref = publicView ? '/signup' : '/home#create-workspace';
  const setupHref = firstWorkspace
    ? `/workspaces/${firstWorkspace.id}/setup`
    : createWorkspaceHref;
  const actionHref = firstWorkspace
    ? `/workspaces/${firstWorkspace.id}/actions/new`
    : createWorkspaceHref;
  const runsHref = firstWorkspace
    ? `/workspaces/${firstWorkspace.id}/runs`
    : createWorkspaceHref;

  const envCode = `export DAAI_API_KEY="your_api_key"
export DAAI_WORKSPACE_KEY="your_workspace_key"
export DAAI_BASE_URL="${apiBaseUrl}"`;

  const clientCode = `import os
from daai import DaaiClient

client = DaaiClient(
    api_key=os.environ["DAAI_API_KEY"],
    workspace_key=os.environ["DAAI_WORKSPACE_KEY"],
    base_url=os.environ.get("DAAI_BASE_URL", "${apiBaseUrl}"),
)`;

  const interceptCode = `${clientCode}

result = client.intercept(
    action="send_invoice_reminder",
    payload={
        "actor": "finance_agent",
        "invoice_id": "INV-1025",
        "customer_name": "ABC Pty Ltd",
        "customer_email": "accounts@example.com",
        "amount": 1250,
        "reasoning": "Invoice is overdue and no reply has been received.",
        "source": {
            "type": "finance_admin_agent",
            "ref": "INV-1025",
        },
    },
    idempotency_key="invoice-reminder:INV-1025",
)

print(result.governance_status)
print(result.executable)
print(result.governance_reason)

if result.executable:
    print("Run the real action here.")
else:
    print("Do not execute yet.")`;

  const statusCode = `status = client.status(action_run_id)

print(status.governance_status)
print(status.execution_status)
print(status.executable)`;

  const reportCode = `client.report_executed(
    action_run_id,
    execution_result={
        "result_summary": "Invoice reminder email sent successfully.",
    },
)

client.report_failed(
    action_run_id,
    execution_error="SMTP provider rejected the message.",
)`;

  const runnerCode = `${clientCode}

from daai import DaaiActionRunner, PendingActionManager, SQLitePendingStore

store = SQLitePendingStore("daai_pending.db")
manager = PendingActionManager(client=client, pending_store=store)
runner = DaaiActionRunner(client=client, pending_store=store)

def send_invoice_reminder_executor(payload):
    print(f"Sending reminder for {payload['invoice_id']}")
    return {"result_summary": "Invoice reminder sent successfully."}

runner.when_executable(
    action="send_invoice_reminder",
    run=send_invoice_reminder_executor,
)

runner.run_pending_once()`;

  const managerCode = `ticket = manager.propose(
    action="send_invoice_reminder",
    payload={
        "actor": "finance_agent",
        "invoice_id": "INV-1025",
        "customer_name": "ABC Pty Ltd",
        "customer_email": "accounts@example.com",
        "amount": 1250,
        "reasoning": "Invoice is overdue.",
    },
    idempotency_key="invoice-reminder:INV-1025",
)

if ticket.executable:
    send_invoice_reminder_executor(ticket.payload)`;

  return (
    <section className="space-y-6">
      <Breadcrumbs
        items={[
          { label: 'Home', href: homeHref },
          { label: 'Documentation' },
        ]}
      />

      <div className="rounded-lg border border-border bg-panel p-5 shadow-card shadow-inset">
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div className="max-w-3xl">
            <p className="text-xs font-semibold uppercase text-brand">Developer docs</p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-text">
              DAAI Console documentation
            </h1>
            <p className="mt-3 text-base leading-7 text-muted">
              Add approval, policy checks, and audit receipts before risky AI-agent
              actions execute.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href={createWorkspaceHref} className={buttonStyles.primary}>
              Create workspace
            </Link>
            <a href="#quickstart" className={buttonStyles.secondary}>
              Go to quickstart
            </a>
          </div>
        </div>
      </div>

      {shouldPersonalizeWorkspaceLinks && workspacesResult.error ? (
        <Notice tone="warning">
          Workspace links could not be personalized: {workspacesResult.error}
        </Notice>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[15rem_minmax(0,1fr)] 2xl:grid-cols-[15rem_minmax(0,1fr)_13rem]">
        <DocsSidebar />

        <main className="min-w-0 space-y-10">
          <DocsSection
            id="overview"
            title="Overview"
            subtitle="Understand the boundary first: DAAI decides whether your app may execute. Your app still owns the real business action."
          >
            <div className="space-y-4 rounded-lg border border-border bg-panel p-5 text-sm leading-7 text-muted shadow-card">
              <p>
                DAAI Console is a Python-first governance layer for AI automations.
                It lets developers register risky actions, check those actions
                against policy, request human approval when needed, and record
                governance receipts.
              </p>
              <p>
                DAAI is not the executor. Your app still performs the real business
                action. DAAI tells your app whether the action is allowed, blocked,
                or waiting for approval.
              </p>
              <p>
                Use DAAI when an AI agent or automation is about to perform an
                action that affects customers, money, records, external
                communication, or business state.
              </p>
            </div>

            <SectionCard title="The core flow">
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                {flowSteps.map((step, index) => (
                  <article
                    key={step}
                    className="rounded-lg border border-border bg-canvas p-4"
                  >
                    <span className="flex h-8 w-8 items-center justify-center rounded-md border border-brand/40 bg-brand/10 font-mono text-xs font-semibold text-brand">
                      {index + 1}
                    </span>
                    <p className="mt-4 text-sm font-medium leading-6 text-text">{step}</p>
                  </article>
                ))}
              </div>
            </SectionCard>

            <WorkspaceDocCta
              workspace={firstWorkspace}
              createWorkspaceHref={createWorkspaceHref}
            />
          </DocsSection>

          <DocsSection
            id="quickstart"
            title="Quickstart"
            subtitle="Run your first governed action with the Python SDK."
          >
            <div className="space-y-3">
              <StepCard
                id="create-workspace"
                number={1}
                title="Create a workspace"
                action={
                  <Link href={setupHref} className={buttonStyles.primary}>
                    {firstWorkspace ? 'Continue setup' : 'Create workspace'}
                  </Link>
                }
              >
                Create a client workspace from the dashboard. DAAI will generate
                the keys your app needs to call the API.
              </StepCard>

              <StepCard id="install-sdk" number={2} title="Install the SDK">
                <p>
                  Install the current beta package in the Python environment that
                  runs the automation.
                </p>
                <CodeBlockWithCopy
                  code="pip install daai-python"
                  title="Shell"
                  label="Copy install"
                />
              </StepCard>

              <StepCard id="set-keys" number={3} title="Set environment variables">
                <p>
                  Use the API key, workspace key, and API base URL from your
                  workspace setup page. The docs never display secret values.
                </p>
                <CodeBlockWithCopy
                  code={envCode}
                  title="Environment"
                  label="Copy env"
                />
              </StepCard>

              <StepCard
                id="register-action"
                number={4}
                title="Register an action"
                action={
                  <Link href={actionHref} className={buttonStyles.secondary}>
                    Register action
                  </Link>
                }
              >
                <p>
                  In the dashboard, register an action named{' '}
                  <code className="font-mono text-text">send_invoice_reminder</code>.
                </p>
                <ul className="mt-3 grid gap-2">
                  <li>Risk level: medium</li>
                  <li>Policy: always require approval or require approval above amount</li>
                  <li>Approver email: your test email</li>
                </ul>
              </StepCard>

              <StepCard id="call-intercept" number={5} title="Call intercept before execution">
                <p>
                  Put the SDK call before the risky function. If your action uses an
                  amount policy, keep <code className="font-mono text-text">amount</code>{' '}
                  at the top level of the payload.
                </p>
                <CodeBlockWithCopy
                  code={interceptCode}
                  title="Python"
                  label="Copy intercept"
                />
              </StepCard>

              <StepCard
                id="check-dashboard"
                number={6}
                title="Check the dashboard"
                action={
                  <Link href={runsHref} className={buttonStyles.secondary}>
                    View action runs
                  </Link>
                }
              >
                After running the script, open the workspace action runs page. You
                should see the proposed action with its governance status.
              </StepCard>

              <StepCard id="approve-or-reject" number={7} title="Approve or reject">
                If the policy requires approval, open the approval email and approve
                or reject the action. DAAI updates the action run and creates a
                governance receipt.
              </StepCard>

              <StepCard id="review-receipt" number={8} title="Expected result">
                <p>At the end of the quickstart, you should have:</p>
                <ul className="mt-3 grid gap-2">
                  <li>one registered action</li>
                  <li>one action run</li>
                  <li>one approval decision or allowed decision</li>
                  <li>one governance receipt</li>
                </ul>
              </StepCard>
            </div>
          </DocsSection>

          <DocsSection
            id="core-concepts"
            title="Core concepts"
            subtitle="The smallest mental model you need before integrating."
          >
            <div className="grid gap-3 md:grid-cols-2">
              {conceptCards.map((concept) => (
                <DocsCard key={concept.title} title={concept.title}>
                  {concept.body}
                </DocsCard>
              ))}
            </div>

            <SectionCard title="Visual flow" description="A governed action moves through a short lifecycle.">
              <div className="grid gap-3 lg:grid-cols-6">
                {lifecycleSteps.map((step, index) => (
                  <div key={step} className="relative">
                    <article className="h-full rounded-lg border border-border bg-canvas p-4 text-center">
                      <span className="mx-auto flex h-8 w-8 items-center justify-center rounded-md border border-borderStrong bg-panel font-mono text-xs font-semibold text-muted">
                        {index + 1}
                      </span>
                      <p className="mt-3 text-sm font-semibold text-text">{step}</p>
                    </article>
                    {index < lifecycleSteps.length - 1 ? (
                      <span className="absolute -right-3 top-1/2 z-10 hidden -translate-y-1/2 text-xs text-subtle lg:block">
                        -&gt;
                      </span>
                    ) : null}
                  </div>
                ))}
              </div>
            </SectionCard>
          </DocsSection>

          <DocsSection
            id="python-sdk"
            title="Python SDK"
            subtitle="Use the low-level client before risky execution, then report what happened after your app runs the real action."
          >
            <div className="grid gap-4 lg:grid-cols-2">
              <DocsCard title="Install">
                <CodeBlockWithCopy
                  code="pip install daai-python"
                  title="Shell"
                  label="Copy install"
                />
              </DocsCard>

              <DocsCard title="Initialize client">
                <CodeBlockWithCopy
                  code={clientCode}
                  title="Python"
                  label="Copy client"
                />
              </DocsCard>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <DocsCard title="intercept()">
                Use <code className="font-mono text-text">intercept</code> before
                the risky function. DAAI returns the governance status and whether
                the app may execute now.
              </DocsCard>
              <DocsCard title="status()">
                Use <code className="font-mono text-text">status</code> to check
                whether a pending action became executable after approval.
              </DocsCard>
              <DocsCard title="report_executed()">
                Call after your app successfully executes the real business action.
              </DocsCard>
              <DocsCard title="report_failed()">
                Call if your app attempted execution but failed.
              </DocsCard>
            </div>

            <CodeBlockWithCopy
              code={statusCode}
              title="Check status"
              label="Copy status"
            />
            <CodeBlockWithCopy
              code={reportCode}
              title="Report execution"
              label="Copy report"
            />
          </DocsSection>

          <DocsSection
            id="approval-flow"
            title="Approval flow"
            subtitle="Some actions should not run immediately. DAAI creates a pending action run and sends an approval email to the configured approver."
          >
            <Notice tone="warning">
              Pending approval does not mean the action failed. It means your app
              should wait and avoid executing until DAAI returns{' '}
              <code className="font-mono text-text">executable=true</code>.
            </Notice>

            <div className="grid gap-5 lg:grid-cols-2">
              <div>
                <h3 className="mb-3 text-base font-semibold text-text">
                  Governance statuses
                </h3>
                <StatusGrid items={governanceStatuses} />
              </div>
              <div>
                <h3 className="mb-3 text-base font-semibold text-text">
                  Execution statuses
                </h3>
                <StatusGrid items={executionStatuses} />
              </div>
            </div>
          </DocsSection>

          <DocsSection
            id="action-runner"
            title="Run approved actions later"
            subtitle="For approval-based workflows, your app may need to store pending actions and run them after approval."
          >
            <CodeBlockWithCopy
              code={runnerCode}
              title="Python runner"
              label="Copy runner"
            />
            <CodeBlockWithCopy
              code={managerCode}
              title="Store pending action"
              label="Copy propose"
            />
          </DocsSection>

          <DocsSection
            id="receipts"
            title="Governance receipts"
            subtitle="DAAI creates receipts for final governance decisions such as allowed, blocked, approved, or rejected. Execution result can be attached later when the developer app reports success or failure."
          >
            <DocsCard title="A receipt should answer">
              <ul className="grid gap-2 sm:grid-cols-2">
                <li>What action was proposed?</li>
                <li>Who or what proposed it?</li>
                <li>What policy applied?</li>
                <li>Was approval required?</li>
                <li>Was it allowed, approved, rejected, or blocked?</li>
                <li>Did the connected app report execution?</li>
              </ul>
            </DocsCard>
          </DocsSection>

          <DocsSection
            id="free-beta-limits"
            title="Free beta limits"
            subtitle="These limits are enforced server-side during the beta to protect system reliability."
          >
            <LimitTable />
            <p className="text-sm text-muted">
              If you hit a limit while testing a real workflow, contact us.
            </p>
          </DocsSection>

          <DocsSection
            id="troubleshooting"
            title="Troubleshooting"
            subtitle="Most integration issues are setup mismatches, pending approvals, or payload shape problems."
          >
            <div className="space-y-3">
              {troubleshooting.map((item) => (
                <DocsCard key={item.issue}>
                  <div className="grid gap-3 md:grid-cols-[0.35fr_0.65fr]">
                    <div>
                      <p className="text-xs font-semibold uppercase text-subtle">Issue</p>
                      <p className="mt-1 font-semibold text-text">{item.issue}</p>
                    </div>
                    <div>
                      <p className="text-xs font-semibold uppercase text-subtle">Advice</p>
                      <p className="mt-1">{item.advice}</p>
                    </div>
                  </div>
                </DocsCard>
              ))}
            </div>
          </DocsSection>
        </main>

        <OnThisPage />
      </div>
    </section>
  );
}
