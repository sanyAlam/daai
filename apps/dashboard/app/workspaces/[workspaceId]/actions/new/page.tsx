import Link from 'next/link';

import { ActionRegistrationForm } from '@/components/action-registration-form';
import { Breadcrumbs } from '@/components/breadcrumbs';
import { buttonStyles, Notice, PageHeader, SectionCard } from '@/components/console-ui';
import { ErrorState, NotFoundState } from '@/components/states';
import { WorkspaceTabs } from '@/components/workspace-tabs';
import { fetchWorkspace, fetchWorkspaceUsage } from '@/lib/api';

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

export default async function NewWorkspaceActionPage(
  props: {
    params: Promise<{ workspaceId: string }>;
    searchParams?: Promise<{ error?: string }>;
  }
) {
  const searchParams = await props.searchParams;
  const params = await props.params;
  const [workspaceResult, usageResult] = await Promise.all([
    fetchWorkspace(params.workspaceId),
    fetchWorkspaceUsage(params.workspaceId),
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

  const errorMessage = decodeMessage(searchParams?.error);
  const actionLimitReached = Boolean(
    usageResult.data &&
      usageResult.data.registered_actions.used >= usageResult.data.registered_actions.limit,
  );

  return (
    <section className="space-y-5">
      <Breadcrumbs
        items={[
          { label: 'Home', href: '/home' },
          { label: 'Workspace', href: `/workspaces/${workspace.id}` },
          { label: 'Actions', href: `/workspaces/${workspace.id}/actions` },
          { label: 'Register' },
        ]}
      />

      <WorkspaceTabs workspaceId={workspace.id} />

      <PageHeader
        title="Register Action"
        description={`Workspace: ${workspace.name}`}
        actions={
          <Link href={`/workspaces/${workspace.id}/actions`} className={buttonStyles.secondary}>
            Back to actions
          </Link>
        }
      />

      <SectionCard>
        {errorMessage ? (
          <Notice tone="danger">
            {errorMessage}
          </Notice>
        ) : null}
        {usageResult.data ? (
          <Notice tone={actionLimitReached ? 'warning' : 'info'} className={errorMessage ? 'mt-3' : ''}>
            Registered actions for this workspace: {usageResult.data.registered_actions.used} / {usageResult.data.registered_actions.limit}
          </Notice>
        ) : null}
        {usageResult.error ? (
          <Notice tone="warning" className={errorMessage || usageResult.data ? 'mt-3' : ''}>
            {usageResult.error}
          </Notice>
        ) : null}
        {actionLimitReached ? (
          <Notice tone="warning" className="mt-3">
            Beta limit reached. Usage is capped during launch to protect reliability.
          </Notice>
        ) : null}

        <div className={errorMessage || usageResult.data || actionLimitReached ? 'mt-5' : ''}>
          <ActionRegistrationForm
            workspaceId={workspace.id}
            disabled={actionLimitReached}
          />
        </div>
      </SectionCard>
    </section>
  );
}
