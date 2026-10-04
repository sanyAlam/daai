import Link from 'next/link';

import { Breadcrumbs } from '@/components/breadcrumbs';
import {
  buttonStyles,
  MetricCard,
  Notice,
  PageHeader,
  PolicyBadge,
  RiskBadge,
  SectionCard,
  StatusBadge,
  TableShell,
} from '@/components/console-ui';
import { EmptyState, ErrorState, NotFoundState } from '@/components/states';
import { WorkspaceTabs } from '@/components/workspace-tabs';
import { fetchWorkspace, fetchWorkspaceActions, fetchWorkspaceUsage } from '@/lib/api';

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

function humanize(value: string): string {
  return value.replaceAll('_', ' ');
}

function policyRule(action: { policy?: { rule_type: string } | null; policy_type: string }) {
  return action.policy?.rule_type ?? action.policy_type;
}

export default async function WorkspaceActionsPage(
  props: {
    params: Promise<{ workspaceId: string }>;
    searchParams?: Promise<{ created_action?: string }>;
  }
) {
  const searchParams = await props.searchParams;
  const params = await props.params;
  const [workspaceResult, actionsResult, usageResult] = await Promise.all([
    fetchWorkspace(params.workspaceId),
    fetchWorkspaceActions(params.workspaceId),
    fetchWorkspaceUsage(params.workspaceId),
  ]);

  if (workspaceResult.error) {
    return <ErrorState title="Workspace Unavailable" message={workspaceResult.error} />;
  }

  if (actionsResult.error) {
    return <ErrorState title="Actions Unavailable" message={actionsResult.error} />;
  }

  const workspace = workspaceResult.data;
  const actions = actionsResult.data ?? [];
  const usage = usageResult.data;
  const actionLimitReached = Boolean(
    usage && usage.registered_actions.used >= usage.registered_actions.limit,
  );
  const createdAction = decodeMessage(searchParams?.created_action);
  const requireApprovalCount = actions.filter((action) =>
    policyRule(action).includes('approval'),
  ).length;
  const alwaysAllowedCount = actions.filter((action) => policyRule(action) === 'always_allow').length;
  const alwaysBlockedCount = actions.filter((action) => policyRule(action) === 'always_block').length;

  if (!workspace) {
    return (
      <NotFoundState
        title="Workspace not found"
        message="The workspace could not be loaded in the current scope."
      />
    );
  }

  return (
    <section className="space-y-5">
      <Breadcrumbs
        items={[
          { label: 'Home', href: '/home' },
          { label: 'Workspace', href: `/workspaces/${workspace.id}` },
          { label: 'Actions' },
        ]}
      />

      <WorkspaceTabs workspaceId={workspace.id} />

      <PageHeader
        title="Registered actions"
        description="Only registered actions can be governed. Unknown actions are blocked by default."
        actions={
          actionLimitReached ? (
            <button type="button" disabled className={buttonStyles.primary}>
              Register action
            </button>
          ) : (
            <Link href={`/workspaces/${workspace.id}/actions/new`} className={buttonStyles.primary}>
              Register action
            </Link>
          )
        }
      />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Total actions"
          value={
            usage
              ? `${usage.registered_actions.used} / ${usage.registered_actions.limit}`
              : actions.length
          }
          tone={actionLimitReached ? 'warning' : 'neutral'}
          compact
        />
        <MetricCard
          label="Require approval"
          value={requireApprovalCount}
          tone={requireApprovalCount > 0 ? 'warning' : 'neutral'}
          compact
        />
        <MetricCard
          label="Always allowed"
          value={alwaysAllowedCount}
          compact
        />
        <MetricCard
          label="Always blocked"
          value={alwaysBlockedCount}
          tone={alwaysBlockedCount > 0 ? 'danger' : 'neutral'}
          compact
        />
      </div>

      {usage ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            label="Client workspaces"
            value={`${usage.client_workspaces.used} / ${usage.client_workspaces.limit}`}
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
          <MetricCard label="Plan" value={usage.plan} compact />
        </div>
      ) : null}

      {usageResult.error ? <Notice tone="warning">{usageResult.error}</Notice> : null}

      {actionLimitReached ? (
        <Notice tone="warning">
          Beta limit reached. Usage is capped during launch to protect reliability.
        </Notice>
      ) : null}

      <SectionCard title="Action registry">
        {createdAction ? (
          <Notice tone="success">
            Action registered. Now run the SDK using{' '}
            <code>action=&quot;{createdAction}&quot;</code>.
          </Notice>
        ) : null}

        {actions.length === 0 ? (
          <div className={createdAction ? 'mt-4' : ''}>
            <EmptyState
              title="Register your first governed action"
              message="Start with one risky action your Python agent may propose."
            />
            <div className="mt-3 text-center">
              {actionLimitReached ? (
                <button type="button" disabled className={buttonStyles.primary}>
                  Action limit reached
                </button>
              ) : (
                <Link
                  href={`/workspaces/${workspace.id}/actions/new`}
                  className={buttonStyles.primary}
                >
                  Register action
                </Link>
              )}
            </div>
          </div>
        ) : (
          <TableShell>
            <table className="min-w-full border-collapse text-sm">
              <thead className="bg-panelHover">
                <tr className="text-left text-xs uppercase text-muted">
                  <th className="px-4 py-3 font-medium">Action</th>
                  <th className="px-4 py-3 font-medium">Risk</th>
                  <th className="px-4 py-3 font-medium">Policy</th>
                  <th className="px-4 py-3 font-medium">Threshold</th>
                  <th className="px-4 py-3 font-medium">Approver</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {actions.map((action) => (
                  <tr key={action.id} className="align-top transition hover:bg-panelHover">
                    <td className="max-w-md px-4 py-3 text-muted">
                      <p className="font-mono text-xs font-medium text-muted">
                        {action.action_name}
                      </p>
                      <p className="font-medium text-text">
                        {action.title || humanize(action.action_name)}
                      </p>
                      {action.description ? (
                        <p className="mt-1 max-w-md text-xs text-muted">
                          {action.description}
                        </p>
                      ) : null}
                    </td>
                    <td className="px-4 py-3 text-muted">
                      <RiskBadge value={action.risk_level} />
                    </td>
                    <td className="px-4 py-3 text-muted">
                      <PolicyBadge value={policyRule(action)} />
                    </td>
                    <td className="px-4 py-3 text-muted">
                      {action.policy?.threshold_amount ?? 'N/A'}
                    </td>
                    <td className="px-4 py-3 text-muted">
                      {action.approver_email ?? 'N/A'}
                    </td>
                    <td className="px-4 py-3 text-muted">
                      <StatusBadge
                        label={action.is_active ? 'active' : 'inactive'}
                        tone={action.is_active ? 'success' : 'neutral'}
                      />
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
