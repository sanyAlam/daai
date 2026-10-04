import Link from 'next/link';

import { ExecutionStatusBadge } from '@/components/badges';
import { Breadcrumbs } from '@/components/breadcrumbs';
import {
  buttonStyles,
  PageHeader,
  SectionCard,
  StatusBadge,
  TableShell,
} from '@/components/console-ui';
import { EmptyState, ErrorState, NotFoundState } from '@/components/states';
import { WorkspaceTabs } from '@/components/workspace-tabs';
import { fetchWorkspace, fetchWorkspaceRuns } from '@/lib/api';
import { formatTimestamp } from '@/lib/format';
import { ActionRunListItem, GovernanceReceipt } from '@/lib/types';

type ReceiptRun = ActionRunListItem & { receipt: GovernanceReceipt };

function hasReceipt(run: ActionRunListItem): run is ReceiptRun {
  return run.receipt !== null;
}

function receiptTone(outcome: GovernanceReceipt['outcome']): 'success' | 'danger' {
  if (outcome === 'allowed' || outcome === 'approved') {
    return 'success';
  }
  return 'danger';
}

export default async function WorkspaceReceiptsPage(
  props: {
    params: Promise<{ workspaceId: string }>;
  }
) {
  const params = await props.params;
  const [workspaceResult, runsResult] = await Promise.all([
    fetchWorkspace(params.workspaceId),
    fetchWorkspaceRuns(params.workspaceId, { pageSize: 100 }),
  ]);

  if (workspaceResult.error) {
    return <ErrorState title="Workspace Unavailable" message={workspaceResult.error} />;
  }

  if (runsResult.error) {
    return <ErrorState title="Receipts Unavailable" message={runsResult.error} />;
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

  const receiptRuns = (runsResult.data?.items ?? []).filter(hasReceipt);

  return (
    <section className="space-y-5">
      <Breadcrumbs
        items={[
          { label: 'Home', href: '/home' },
          { label: 'Workspace', href: `/workspaces/${workspace.id}` },
          { label: 'Receipts' },
        ]}
      />

      <WorkspaceTabs workspaceId={workspace.id} />

      <PageHeader
        title="Receipts"
        description="Review audit evidence generated for governed action runs."
        actions={
          <Link href={`/workspaces/${workspace.id}/runs`} className={buttonStyles.secondary}>
            View runs
          </Link>
        }
        meta={`Workspace: ${workspace.name}`}
      />

      <SectionCard
        title="Audit evidence"
        description="Open the action run for the full receipt JSON, policy snapshot, and execution detail."
      >
        {receiptRuns.length === 0 ? (
          <EmptyState
            title="No receipts yet"
            message="Receipts appear after DAAI records an auditable governance outcome."
          />
        ) : (
          <TableShell>
            <table className="min-w-full divide-y divide-border text-sm">
              <thead className="bg-panelHover">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-text">Generated</th>
                  <th className="px-4 py-3 text-left font-medium text-text">Action</th>
                  <th className="px-4 py-3 text-left font-medium text-text">
                    Governance outcome
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-text">
                    Execution outcome
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-text">Reason</th>
                  <th className="px-4 py-3 text-left font-medium text-text">View</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border bg-canvas">
                {receiptRuns.map((run) => (
                  <tr key={run.action_run_id} className="align-top transition hover:bg-panelHover">
                    <td className="whitespace-nowrap px-4 py-3 text-xs text-muted">
                      {formatTimestamp(run.receipt.created_at)}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-text">{run.action}</td>
                    <td className="px-4 py-3">
                      <StatusBadge
                        label={run.receipt.outcome.replaceAll('_', ' ')}
                        tone={receiptTone(run.receipt.outcome)}
                      />
                    </td>
                    <td className="px-4 py-3">
                      <ExecutionStatusBadge value={run.execution_status} />
                    </td>
                    <td className="max-w-md px-4 py-3 text-muted">{run.receipt.reason}</td>
                    <td className="px-4 py-3">
                      <Link
                        href={`/workspaces/${workspace.id}/runs/${run.action_run_id}`}
                        className={`${buttonStyles.subtle} px-2.5 py-1.5 text-xs`}
                      >
                        View receipt
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableShell>
        )}
      </SectionCard>
    </section>
  );
}
