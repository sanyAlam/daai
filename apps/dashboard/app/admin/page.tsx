import type { Metadata } from 'next';

import {
  ExecutableBadge,
  ExecutionStatusBadge,
  GovernanceStatusBadge,
} from '@/components/badges';
import {
  buttonStyles,
  fieldStyles,
  MetricCard,
  PageHeader,
  selectStyles,
  SectionCard,
  StatusBadge,
  TableShell,
} from '@/components/console-ui';
import { EmptyState, ErrorState } from '@/components/states';
import {
  fetchAdminOverview,
  fetchAdminRecentActionRuns,
  fetchAdminUsers,
  fetchAdminWorkspaces,
} from '@/lib/api';
import { formatTimestamp } from '@/lib/format';
import type { GovernanceStatus } from '@/lib/types';

export const metadata: Metadata = {
  title: 'Internal Admin | DAAI Console',
};

const GOVERNANCE_STATUSES: GovernanceStatus[] = [
  'allowed',
  'pending_approval',
  'approved',
  'rejected',
  'blocked',
];

type AdminSearchParams = {
  search?: string | string[];
  governance_status?: string | string[];
  activated_only?: string | string[];
  sort?: string | string[];
};

function firstParam(value: string | string[] | undefined): string {
  if (Array.isArray(value)) {
    return value[0] ?? '';
  }
  return value ?? '';
}

function isGovernanceStatus(value: string): value is GovernanceStatus {
  return GOVERNANCE_STATUSES.includes(value as GovernanceStatus);
}

function compactReason(value: string, maxLength = 80): string {
  if (value.length <= maxLength) {
    return value;
  }
  return `${value.slice(0, maxLength - 3)}...`;
}

function formatNumber(value: number): string {
  return value.toLocaleString('en-US');
}

export default async function AdminPage(
  props: {
    searchParams: Promise<AdminSearchParams>;
  }
) {
  const searchParams = await props.searchParams;
  const search = firstParam(searchParams.search).trim();
  const statusParam = firstParam(searchParams.governance_status);
  const governanceStatus = isGovernanceStatus(statusParam)
    ? statusParam
    : undefined;
  const activatedOnly = firstParam(searchParams.activated_only) === 'true';
  const sortParam = firstParam(searchParams.sort);
  const sort = sortParam === 'last_activity' ? 'last_activity' : 'newest';

  const [overviewResult, usersResult, workspacesResult, runsResult] =
    await Promise.all([
      fetchAdminOverview(),
      fetchAdminUsers({ search, activatedOnly, sort }),
      fetchAdminWorkspaces({ search }),
      fetchAdminRecentActionRuns({ search, governanceStatus }),
    ]);

  const error =
    overviewResult.error ??
    usersResult.error ??
    workspacesResult.error ??
    runsResult.error;

  if (error) {
    return (
      <ErrorState
        title="Admin view unavailable"
        message={error}
      />
    );
  }

  const overview = overviewResult.data;
  const users = usersResult.data ?? [];
  const workspaces = workspacesResult.data ?? [];
  const recentRuns = runsResult.data ?? [];

  if (!overview) {
    return (
      <ErrorState
        title="Admin view unavailable"
        message="Admin overview data was not returned."
      />
    );
  }

  const metrics = [
    ['Total users', overview.total_users, 'neutral'],
    ['Total workspaces', overview.total_workspaces, 'neutral'],
    ['Total registered actions', overview.total_registered_actions, 'neutral'],
    ['Total action runs', overview.total_action_runs, 'neutral'],
    ['Pending approvals', overview.pending_approvals, 'warning'],
    ['Approved actions', overview.approved_actions, 'success'],
    ['Blocked actions', overview.blocked_actions, 'danger'],
    ['Executed actions', overview.executed_actions, 'success'],
    ['Failed actions', overview.failed_actions, 'danger'],
    [
      'Approval emails sent this month',
      overview.approval_emails_sent_this_month,
      'info',
    ],
    ['Activated users', overview.activated_users, 'brand'],
  ] as const;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Internal admin beta view"
        title="Beta usage"
        description="Read-only activation and action-run visibility for DAAI Console beta observation."
      />

      <form
        action="/admin"
        className="rounded-lg border border-border bg-panel p-4 shadow-card"
      >
        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_180px_170px_180px_auto] md:items-end">
          <div>
            <label htmlFor="search" className="block text-xs font-medium uppercase text-muted">
              Search
            </label>
            <input
              id="search"
              name="search"
              defaultValue={search}
              className={`mt-2 ${fieldStyles}`}
              placeholder="Email, workspace, action"
            />
          </div>

          <div>
            <label htmlFor="governance_status" className="block text-xs font-medium uppercase text-muted">
              Status
            </label>
            <select
              id="governance_status"
              name="governance_status"
              defaultValue={governanceStatus ?? ''}
              className={`mt-2 ${selectStyles}`}
            >
              <option value="">All statuses</option>
              {GOVERNANCE_STATUSES.map((status) => (
                <option key={status} value={status}>
                  {status.replaceAll('_', ' ')}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="sort" className="block text-xs font-medium uppercase text-muted">
              Users sort
            </label>
            <select
              id="sort"
              name="sort"
              defaultValue={sort}
              className={`mt-2 ${selectStyles}`}
            >
              <option value="newest">Newest users</option>
              <option value="last_activity">Last activity</option>
            </select>
          </div>

          <label className="flex min-h-[42px] items-center gap-2 rounded-md border border-border bg-canvas px-3 py-2 text-sm text-muted">
            <input
              type="checkbox"
              name="activated_only"
              value="true"
              defaultChecked={activatedOnly}
              className="h-4 w-4 accent-brand"
            />
            Activated only
          </label>

          <button type="submit" className={buttonStyles.primary}>
            Apply
          </button>
        </div>
      </form>

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
        {metrics.map(([label, value, tone]) => (
          <MetricCard
            key={label}
            label={label}
            value={formatNumber(value)}
            tone={tone}
            compact
          />
        ))}
      </section>

      <SectionCard title="Users">
        {users.length === 0 ? (
          <EmptyState title="No users found" message="No beta users match this view." />
        ) : (
          <TableShell>
            <table className="min-w-full divide-y divide-border text-sm">
              <thead className="bg-panel">
                <tr className="text-left text-xs font-medium uppercase text-subtle">
                  <th className="px-3 py-3">Email</th>
                  <th className="px-3 py-3">Signed up at</th>
                  <th className="px-3 py-3">Plan</th>
                  <th className="px-3 py-3">Workspaces</th>
                  <th className="px-3 py-3">Actions</th>
                  <th className="px-3 py-3">Runs</th>
                  <th className="px-3 py-3">Last run</th>
                  <th className="px-3 py-3">Activated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {users.map((user) => (
                  <tr key={`${user.email}-${user.signed_up_at}`} className="align-top">
                    <td className="whitespace-nowrap px-3 py-3 font-medium text-text">
                      {user.email ?? 'Unknown'}
                    </td>
                    <td className="whitespace-nowrap px-3 py-3 text-muted">
                      {formatTimestamp(user.signed_up_at)}
                    </td>
                    <td className="whitespace-nowrap px-3 py-3">
                      <StatusBadge label={user.plan} tone="neutral" />
                    </td>
                    <td className="px-3 py-3 text-muted">{user.workspace_count}</td>
                    <td className="px-3 py-3 text-muted">{user.registered_action_count}</td>
                    <td className="px-3 py-3 text-muted">{user.action_run_count}</td>
                    <td className="whitespace-nowrap px-3 py-3 text-muted">
                      {formatTimestamp(user.last_action_run_at)}
                    </td>
                    <td className="whitespace-nowrap px-3 py-3">
                      <StatusBadge
                        label={user.activated ? 'yes' : 'no'}
                        tone={user.activated ? 'success' : 'neutral'}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableShell>
        )}
      </SectionCard>

      <SectionCard title="Workspaces">
        {workspaces.length === 0 ? (
          <EmptyState title="No workspaces found" message="No workspaces match this view." />
        ) : (
          <TableShell>
            <table className="min-w-full divide-y divide-border text-sm">
              <thead className="bg-panel">
                <tr className="text-left text-xs font-medium uppercase text-subtle">
                  <th className="px-3 py-3">Workspace name</th>
                  <th className="px-3 py-3">Client name</th>
                  <th className="px-3 py-3">Owner email</th>
                  <th className="px-3 py-3">Plan</th>
                  <th className="px-3 py-3">Actions</th>
                  <th className="px-3 py-3">Runs this month</th>
                  <th className="px-3 py-3">Approval emails</th>
                  <th className="px-3 py-3">Last run</th>
                  <th className="px-3 py-3">Created at</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {workspaces.map((workspace) => (
                  <tr key={workspace.workspace_id} className="align-top">
                    <td className="whitespace-nowrap px-3 py-3 font-medium text-text">
                      {workspace.workspace_name}
                    </td>
                    <td className="whitespace-nowrap px-3 py-3 text-muted">
                      {workspace.client_name ?? 'N/A'}
                    </td>
                    <td className="whitespace-nowrap px-3 py-3 text-muted">
                      {workspace.owner_email ?? 'Unknown'}
                    </td>
                    <td className="whitespace-nowrap px-3 py-3">
                      <StatusBadge label={workspace.plan} tone="neutral" />
                    </td>
                    <td className="px-3 py-3 text-muted">
                      {workspace.registered_action_count}
                    </td>
                    <td className="px-3 py-3 text-muted">
                      {workspace.action_runs_this_month}
                    </td>
                    <td className="px-3 py-3 text-muted">
                      {workspace.approval_emails_this_month}
                    </td>
                    <td className="whitespace-nowrap px-3 py-3 text-muted">
                      {formatTimestamp(workspace.last_action_run_at)}
                    </td>
                    <td className="whitespace-nowrap px-3 py-3 text-muted">
                      {formatTimestamp(workspace.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableShell>
        )}
      </SectionCard>

      <SectionCard title="Recent action runs">
        {recentRuns.length === 0 ? (
          <EmptyState title="No action runs found" message="No action runs match this view." />
        ) : (
          <TableShell>
            <table className="min-w-full divide-y divide-border text-sm">
              <thead className="bg-panel">
                <tr className="text-left text-xs font-medium uppercase text-subtle">
                  <th className="px-3 py-3">Created at</th>
                  <th className="px-3 py-3">Workspace</th>
                  <th className="px-3 py-3">Owner email</th>
                  <th className="px-3 py-3">Action name</th>
                  <th className="px-3 py-3">Actor</th>
                  <th className="px-3 py-3">Status</th>
                  <th className="px-3 py-3">Decision</th>
                  <th className="px-3 py-3">Executable</th>
                  <th className="px-3 py-3">Execution status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {recentRuns.map((run) => (
                  <tr key={run.action_run_id} className="align-top">
                    <td className="whitespace-nowrap px-3 py-3 text-muted">
                      {formatTimestamp(run.created_at)}
                    </td>
                    <td className="whitespace-nowrap px-3 py-3 font-medium text-text">
                      {run.workspace_name}
                    </td>
                    <td className="whitespace-nowrap px-3 py-3 text-muted">
                      {run.owner_email ?? 'Unknown'}
                    </td>
                    <td className="whitespace-nowrap px-3 py-3 font-mono text-xs text-text">
                      {run.action_name}
                    </td>
                    <td className="whitespace-nowrap px-3 py-3 text-muted">
                      {run.actor ?? 'N/A'}
                    </td>
                    <td className="whitespace-nowrap px-3 py-3">
                      <GovernanceStatusBadge value={run.governance_status} />
                    </td>
                    <td className="max-w-xs px-3 py-3 text-muted">
                      {compactReason(run.governance_reason)}
                    </td>
                    <td className="whitespace-nowrap px-3 py-3">
                      <ExecutableBadge value={run.executable} />
                    </td>
                    <td className="whitespace-nowrap px-3 py-3">
                      <ExecutionStatusBadge value={run.execution_status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableShell>
        )}
      </SectionCard>
    </div>
  );
}
