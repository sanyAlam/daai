import { Breadcrumbs } from '@/components/breadcrumbs';
import { PageHeader, SectionCard } from '@/components/console-ui';
import { ErrorState, NotFoundState } from '@/components/states';
import { WorkspaceRunsTable } from '@/components/workspace-runs-table';
import { WorkspaceTabs } from '@/components/workspace-tabs';
import { fetchWorkspace, fetchWorkspaceMetrics } from '@/lib/api';
import { ExecutionStatus, GovernanceStatus } from '@/lib/types';

const GOVERNANCE_STATUS_OPTIONS = new Set<GovernanceStatus>([
  'allowed',
  'pending_approval',
  'approved',
  'rejected',
  'blocked',
]);

const EXECUTION_STATUS_OPTIONS = new Set<ExecutionStatus>([
  'not_executed',
  'awaiting_execution_report',
  'executed',
  'failed',
]);

function pickSingle(value: string | string[] | undefined): string | undefined {
  if (typeof value === 'string') {
    return value;
  }
  if (Array.isArray(value)) {
    return value[0];
  }
  return undefined;
}

function parsePositiveInt(value: string | undefined, fallback: number): number {
  const parsed = Number.parseInt(value ?? '', 10);
  if (!Number.isFinite(parsed) || parsed < 1) {
    return fallback;
  }
  return parsed;
}

function parseGovernanceStatus(
  value: string | undefined,
): GovernanceStatus | '' {
  if (!value) {
    return '';
  }
  return GOVERNANCE_STATUS_OPTIONS.has(value as GovernanceStatus)
    ? (value as GovernanceStatus)
    : '';
}

function parseExecutionStatus(value: string | undefined): ExecutionStatus | '' {
  if (!value) {
    return '';
  }
  return EXECUTION_STATUS_OPTIONS.has(value as ExecutionStatus)
    ? (value as ExecutionStatus)
    : '';
}

export default async function WorkspaceRunsPage(
  props: {
    params: Promise<{ workspaceId: string }>;
    searchParams?: Promise<{
      page?: string | string[];
      page_size?: string | string[];
      search?: string | string[];
      governance_status?: string | string[];
      execution_status?: string | string[];
    }>;
  }
) {
  const searchParams = await props.searchParams;
  const params = await props.params;
  const [workspaceResult, metricsResult] = await Promise.all([
    fetchWorkspace(params.workspaceId),
    fetchWorkspaceMetrics(params.workspaceId),
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

  const initialPage = parsePositiveInt(pickSingle(searchParams?.page), 1);
  const initialPageSize = Math.min(
    100,
    parsePositiveInt(pickSingle(searchParams?.page_size), 25),
  );
  const initialSearch = (pickSingle(searchParams?.search) ?? '').trim();
  const initialGovernanceStatus = parseGovernanceStatus(
    pickSingle(searchParams?.governance_status),
  );
  const initialExecutionStatus = parseExecutionStatus(
    pickSingle(searchParams?.execution_status),
  );

  return (
    <section className="space-y-5">
      <Breadcrumbs
        items={[
          { label: 'Home', href: '/home' },
          { label: 'Workspace', href: `/workspaces/${workspace.id}` },
          { label: 'Runs' },
        ]}
      />

      <WorkspaceTabs workspaceId={workspace.id} />

      <PageHeader
        title="Action runs"
        description="Every proposed agent action appears here with governance and execution status."
        meta={`Workspace: ${workspace.name}`}
      />

      <SectionCard
        title="Run history"
        description="Filter governed proposals and open a run to review its detail."
      >
        <WorkspaceRunsTable
          workspaceId={workspace.id}
          initialMetrics={metricsResult.data}
          initialMetricsError={metricsResult.error}
          initialPage={initialPage}
          initialPageSize={initialPageSize}
          initialSearch={initialSearch}
          initialGovernanceStatus={initialGovernanceStatus}
          initialExecutionStatus={initialExecutionStatus}
        />
      </SectionCard>
    </section>
  );
}
