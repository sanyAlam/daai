import Link from 'next/link';
import { cookies, type UnsafeUnwrappedCookies } from 'next/headers';
import type { ReactNode } from 'react';

import { regenerateWorkspaceKeyAction } from '@/app/key-management-actions';
import { Breadcrumbs } from '@/components/breadcrumbs';
import { CollapsibleCodeBlock } from '@/components/collapsible-code-block';
import {
  buttonStyles,
  Notice,
  PageHeader,
  SectionCard,
  StatusBadge,
} from '@/components/console-ui';
import { CopyButton } from '@/components/copy-button';
import { DeleteWorkspaceDialog } from '@/components/delete-workspace-dialog';
import { FormSubmitButton } from '@/components/form-submit-button';
import { ErrorState, NotFoundState } from '@/components/states';
import { WorkspaceTabs } from '@/components/workspace-tabs';
import {
  fetchDashboardApiKeys,
  fetchWorkspace,
  fetchWorkspaceActions,
  fetchWorkspaceApprovalSettings,
  fetchWorkspaceKeyInfo,
  fetchWorkspaceMetrics,
  fetchWorkspaceUsage,
  getApiBaseUrl,
} from '@/lib/api';

const NEW_WORKSPACE_KEY_COOKIE = 'daai_new_workspace_key';

function readWorkspaceKeyForSetup(workspaceId: string): string | null {
  const cookieStore = (cookies() as unknown as UnsafeUnwrappedCookies);
  const cookieValue = cookieStore.get(NEW_WORKSPACE_KEY_COOKIE)?.value;
  if (!cookieValue) {
    return null;
  }

  try {
    const parsed = JSON.parse(decodeURIComponent(cookieValue)) as {
      workspace_id?: unknown;
      workspace_key?: unknown;
    };
    if (parsed.workspace_id !== workspaceId) {
      return null;
    }
    if (typeof parsed.workspace_key !== 'string' || !parsed.workspace_key) {
      return null;
    }
    return parsed.workspace_key;
  } catch {
    return null;
  }
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

function maskIdentifier(value: string | null | undefined): string {
  if (!value) {
    return 'Unavailable';
  }
  if (value.length <= 12) {
    return `${value.slice(0, 4)}...`;
  }
  return `${value.slice(0, 8)}...${value.slice(-4)}`;
}

type StepState = 'complete' | 'next' | 'later';

function stepState(isComplete: boolean, isNext: boolean): StepState {
  if (isComplete) {
    return 'complete';
  }
  return isNext ? 'next' : 'later';
}

function SetupStep({
  number,
  title,
  description,
  state,
  children,
  action,
}: {
  number: number;
  title: string;
  description: string;
  state: StepState;
  children?: ReactNode;
  action?: ReactNode;
}) {
  const label = state === 'complete' ? 'Complete' : state === 'next' ? 'Next' : 'Later';
  const tone = state === 'complete' ? 'success' : state === 'next' ? 'warning' : 'neutral';

  return (
    <details
      id={`setup-step-${number}`}
      className="rounded-lg border border-border bg-panel p-5 shadow-card open:border-borderStrong"
      open={state === 'next'}
    >
      <summary className="cursor-pointer list-none">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex min-w-0 gap-4">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-border bg-canvas font-mono text-sm font-semibold text-text">
              {number}
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-lg font-semibold text-text">{title}</h2>
                <StatusBadge label={label} tone={tone} />
              </div>
              <p className="mt-1 max-w-3xl text-sm text-muted">{description}</p>
            </div>
          </div>
          {action ? <div className="flex shrink-0 flex-wrap gap-2">{action}</div> : null}
        </div>
      </summary>
      {children ? <div className="mt-4 border-t border-border pt-4">{children}</div> : null}
    </details>
  );
}

function CompactUsageItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[11px] font-medium uppercase text-subtle">{label}</p>
      <p className="mt-1 text-sm font-semibold text-text">{value}</p>
    </div>
  );
}

export default async function WorkspaceSetupPage(
  props: {
    params: Promise<{ workspaceId: string }>;
    searchParams?: Promise<{
      created?: string;
      regenerated?: string;
      key_error?: string;
      delete_error?: string;
    }>;
  }
) {
  const searchParams = await props.searchParams;
  const params = await props.params;
  const [
    workspaceResult,
    keyInfoResult,
    apiKeysResult,
    actionsResult,
    metricsResult,
    approvalSettingsResult,
    usageResult,
  ] = await Promise.all([
    fetchWorkspace(params.workspaceId),
    fetchWorkspaceKeyInfo(params.workspaceId),
    fetchDashboardApiKeys(),
    fetchWorkspaceActions(params.workspaceId),
    fetchWorkspaceMetrics(params.workspaceId),
    fetchWorkspaceApprovalSettings(params.workspaceId),
    fetchWorkspaceUsage(params.workspaceId),
  ]);

  const workspace = workspaceResult.data;
  const keyInfo = keyInfoResult.data;

  if (workspaceResult.error) {
    return <ErrorState title="Workspace Setup Unavailable" message={workspaceResult.error} />;
  }

  if (!workspace) {
    return (
      <NotFoundState
        title="Workspace not found"
        message="The workspace could not be loaded in the current scope."
      />
    );
  }

  const workspaceKey = readWorkspaceKeyForSetup(workspace.id);
  const isNewWorkspace = searchParams?.created === '1';
  const isRegenerated = searchParams?.regenerated === '1';
  const keyErrorMessage = decodeMessage(searchParams?.key_error);
  const deleteErrorMessage = decodeMessage(searchParams?.delete_error);
  const hasWorkspaceKey = Boolean(keyInfo?.key_identifier);
  const hasApiKey = Boolean(
    apiKeysResult.data?.some(
      (apiKey) => apiKey.workspace_id === workspace.id && apiKey.status === 'active',
    ),
  );
  const hasActions = (actionsResult.data?.length ?? 0) > 0;
  const hasRun = (metricsResult.data?.total_runs ?? 0) > 0;
  const hasExecutedRun = (metricsResult.data?.executed ?? 0) > 0;
  const approvalEmailCount = approvalSettingsResult.data?.approval_emails.length ?? 0;
  const apiBaseUrl = getApiBaseUrl();
  const envSnippet = `DAAI_API_KEY=your_api_key
DAAI_WORKSPACE_KEY=${workspaceKey ?? 'your_workspace_key'}
DAAI_BASE_URL=${apiBaseUrl}`;
  const stepCompletions = [
    hasRun,
    hasApiKey && hasWorkspaceKey,
    hasActions,
    hasRun,
    hasExecutedRun,
    hasRun,
    hasRun,
  ];
  const completedSteps = stepCompletions.filter(Boolean).length;
  const nextStepIndex = stepCompletions.findIndex((complete) => !complete);
  const nextStepNumber = nextStepIndex === -1 ? 7 : nextStepIndex + 1;

  return (
    <section className="space-y-7">
      <Breadcrumbs
        items={[
          { label: 'Home', href: '/home' },
          { label: 'Workspace', href: `/workspaces/${workspace.id}` },
          { label: 'Setup' },
        ]}
      />

      <WorkspaceTabs workspaceId={workspace.id} />

      <PageHeader
        title="Workspace setup"
        description="Connect your Python app to DAAI and run the first governed action."
        actions={
          <a href={`#setup-step-${nextStepNumber}`} className={buttonStyles.primary}>
            Continue next step
          </a>
        }
        meta={
          <div className="flex flex-wrap items-center gap-3">
            <StatusBadge label={`${completedSteps} of 7 steps complete`} tone="neutral" />
            <span className="text-sm text-muted">{workspace.name}</span>
          </div>
        }
      />

      {isNewWorkspace ? <Notice tone="success">Workspace created and linked to your account.</Notice> : null}
      {isRegenerated ? (
        <Notice tone="warning">Workspace key regenerated. The old workspace key is now invalid.</Notice>
      ) : null}
      {keyErrorMessage ? <Notice tone="danger">{keyErrorMessage}</Notice> : null}
      {deleteErrorMessage ? <Notice tone="danger">{deleteErrorMessage}</Notice> : null}
      {usageResult.data ? (
        <section className="rounded-lg border border-border bg-panel px-4 py-3 shadow-card">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <h2 className="text-sm font-semibold text-text">Beta usage</h2>
              <span className="text-xs text-muted">Server-enforced launch caps</span>
            </div>
            <StatusBadge label={usageResult.data.plan} tone="brand" />
          </div>
          <div className="mt-3 grid gap-x-5 gap-y-3 sm:grid-cols-2 xl:grid-cols-4">
            <CompactUsageItem
              label="Workspaces"
              value={`${usageResult.data.client_workspaces.used} / ${usageResult.data.client_workspaces.limit}`}
            />
            <CompactUsageItem
              label="Actions"
              value={`${usageResult.data.registered_actions.used} / ${usageResult.data.registered_actions.limit}`}
            />
            <CompactUsageItem
              label="Runs this month"
              value={`${usageResult.data.action_runs_this_month.used} / ${usageResult.data.action_runs_this_month.limit}`}
            />
            <CompactUsageItem
              label="Approval emails"
              value={`${usageResult.data.approval_emails_this_month.used} / ${usageResult.data.approval_emails_this_month.limit}`}
            />
          </div>
        </section>
      ) : null}
      {usageResult.error ? <Notice tone="warning">{usageResult.error}</Notice> : null}

      <SectionCard
        title="Required credentials"
        description="This is the integration home for workspace keys and environment values."
        actions={<CopyButton value={envSnippet} label="Copy env" />}
      >
        <div className="grid gap-4 rounded-lg bg-canvas p-4 md:grid-cols-3">
          <div>
            <p className="text-xs font-medium uppercase text-subtle">API base URL</p>
            <p className="mt-2 break-all font-mono text-xs text-text">{apiBaseUrl}</p>
          </div>
          <div>
            <p className="text-xs font-medium uppercase text-subtle">Workspace key</p>
            <p className="mt-2 font-mono text-xs text-text">
              {maskIdentifier(keyInfo?.key_identifier)}
            </p>
          </div>
          <div>
            <p className="text-xs font-medium uppercase text-subtle">API key status</p>
            <div className="mt-2">
              <StatusBadge
                label={hasApiKey ? 'Active key available' : 'Create or verify key'}
                tone={hasApiKey ? 'success' : 'warning'}
              />
            </div>
            <Link href="/account" className="mt-2 inline-flex text-xs font-medium text-muted hover:text-text">
              Manage API keys
            </Link>
          </div>
        </div>

        {workspaceKey ? (
          <div className="mt-4 rounded-lg border border-brand/30 bg-brand/10 p-4">
            <p className="text-sm font-semibold text-text">Workspace key shown once</p>
            <p className="mt-2 break-all font-mono text-xs text-text">{workspaceKey}</p>
            <div className="mt-3">
              <CopyButton value={workspaceKey} label="Copy workspace key" />
            </div>
            <p className="mt-2 text-xs text-muted">Store it now. It will not be shown again.</p>
          </div>
        ) : null}

        <div className="mt-4 flex flex-wrap items-start justify-between gap-4 border-t border-border pt-4">
          <div className="max-w-2xl">
            <p className="text-sm font-medium text-text">Regenerate workspace key</p>
            <p className="mt-1 text-xs text-muted">
              Regeneration invalidates the old workspace key immediately.
            </p>
          </div>
          <form action={regenerateWorkspaceKeyAction}>
            <input type="hidden" name="workspace_id" value={workspace.id} />
            <input type="hidden" name="return_to" value={`/workspaces/${workspace.id}/setup`} />
            <FormSubmitButton
              label="Regenerate key"
              loadingLabel="Regenerating..."
              className={buttonStyles.danger}
            />
          </form>
        </div>

        <div className="mt-4 flex flex-wrap gap-x-4 gap-y-2 text-sm text-muted">
          <span>
            Approval routing: {approvalEmailCount > 0 ? 'configured' : 'not configured'}
          </span>
          <Link href={`/workspaces/${workspace.id}#approval-routing`} className="font-medium hover:text-text">
            Manage on Overview
          </Link>
        </div>

        {keyInfoResult.error ? <Notice tone="warning" className="mt-4">{keyInfoResult.error}</Notice> : null}
        {apiKeysResult.error ? <Notice tone="warning" className="mt-4">{apiKeysResult.error}</Notice> : null}
      </SectionCard>

      <section className="space-y-3">
        <SetupStep
          number={1}
          title="Install Python SDK"
          description="Install the DAAI Python package in the client automation environment."
          state={stepState(stepCompletions[0], nextStepIndex === 0)}
        >
          <CollapsibleCodeBlock
            code="pip install daai-python"
            defaultOpen={nextStepIndex === 0}
            label="Copy command"
            title="Shell"
          />
        </SetupStep>

        <SetupStep
          number={2}
          title="Set environment variables"
          description="Provide the SDK API key, workspace key, and API base URL at runtime."
          state={stepState(stepCompletions[1], nextStepIndex === 1)}
        >
          <CollapsibleCodeBlock
            code={envSnippet}
            defaultOpen={nextStepIndex === 1}
            label="Copy env"
            title="Environment"
          />
        </SetupStep>

        <SetupStep
          number={3}
          title="Register first action"
          description="Register the exact action_name before the SDK sends a proposal. Unknown actions are blocked by default."
          state={stepState(stepCompletions[2], nextStepIndex === 2)}
          action={
            <Link href={`/workspaces/${workspace.id}/actions/new`} className={buttonStyles.primary}>
              Register action
            </Link>
          }
        />

        <SetupStep
          number={4}
          title="Add interception gate"
          description="Call intercept() before the risky action executes."
          state={stepState(stepCompletions[3], nextStepIndex === 3)}
        >
          <p className="text-sm text-muted">
            Use the same idempotency key only when retrying the same proposal payload.
          </p>
          <CollapsibleCodeBlock
            defaultOpen={nextStepIndex === 3}
            label="Copy snippet"
            title="Python"
            code={`import os
from daai import DaaiClient

client = DaaiClient(
    api_key=os.environ["DAAI_API_KEY"],
    workspace_key=os.environ["DAAI_WORKSPACE_KEY"],
    base_url=os.environ.get("DAAI_BASE_URL", "${apiBaseUrl}"),
)

result = client.intercept(
    action="send_invoice_reminder",
    payload={
        "invoice_id": "INV-1025",
        "customer_email": "client@example.com",
        "amount": 250,
        "external_recipient": True,
        "is_new_recipient": False,
        "reversible": True,
        "destructive": False,
    },
    idempotency_key="invoice-reminder:INV-1025",
)

if result.executable:
    send_invoice_reminder()`}
          />
        </SetupStep>

        <SetupStep
          number={5}
          title="Add worker runner"
          description="Runner is needed for actions that become executable after approval."
          state={stepState(stepCompletions[4], nextStepIndex === 4)}
        >
          <CollapsibleCodeBlock
            defaultOpen={nextStepIndex === 4}
            label="Copy runner"
            title="Python"
            code={`from daai import DaaiActionRunner, SQLitePendingStore

runner = DaaiActionRunner(
    client=client,
    pending_store=SQLitePendingStore("daai-pending.sqlite3"),
)

runner.when_executable(
    action="send_invoice_reminder",
    run=send_invoice_reminder_executor,
)

runner.run_pending_once()`}
          />
        </SetupStep>

        <SetupStep
          number={6}
          title="Run a test action"
          description="Send one proposal with an idempotency key so retries do not create duplicate action runs or approval emails."
          state={stepState(stepCompletions[5], nextStepIndex === 5)}
        >
          <CollapsibleCodeBlock
            defaultOpen={nextStepIndex === 5}
            label="Copy test"
            title="Python"
            code={`result = client.intercept(
    action="send_invoice_reminder",
    payload={
        "invoice_id": "INV-1025",
        "customer_email": "client@example.com",
        "amount": 250,
        "external_recipient": True,
        "is_new_recipient": False,
        "reversible": True,
        "destructive": False,
    },
    idempotency_key="invoice-reminder:INV-1025",
)

print(result.governance_status)
print(result.executable)`}
          />
        </SetupStep>

        <SetupStep
          number={7}
          title="Review run in DAAI"
          description="Confirm the governed run and receipt tell the full action story."
          state={stepState(stepCompletions[6], nextStepIndex === 6)}
        >
          <div className="flex flex-wrap gap-2">
            <Link href={`/workspaces/${workspace.id}/runs`} className={buttonStyles.primary}>
              View runs
            </Link>
            <Link href={`/workspaces/${workspace.id}/receipts`} className={buttonStyles.secondary}>
              View receipts
            </Link>
          </div>
        </SetupStep>
      </section>

      <SectionCard title="Need the concept guide?">
        <p className="text-sm text-muted">
          Open the visual documentation for policy concepts, approval lifecycle, and common mistakes.
        </p>
        <div className="mt-3">
          <Link href="/dashboard/documentation" className={buttonStyles.secondary}>
            Open documentation
          </Link>
        </div>
      </SectionCard>

      <SectionCard
        title="Danger zone"
        description="Delete this workspace only when its actions, runs, receipts, keys, and approval records should be permanently removed."
        actions={
          <DeleteWorkspaceDialog
            workspaceId={workspace.id}
            workspaceName={workspace.name}
          />
        }
      />
    </section>
  );
}
