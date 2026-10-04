import { cookies, type UnsafeUnwrappedCookies } from 'next/headers';

import {
  createApiKeyAction,
  revokeApiKeyAction,
} from '@/app/key-management-actions';
import { Breadcrumbs } from '@/components/breadcrumbs';
import {
  buttonStyles,
  fieldStyles,
  Notice,
  PageHeader,
  SectionCard,
  selectStyles,
  StatusBadge,
  TableShell,
} from '@/components/console-ui';
import { CopyButton } from '@/components/copy-button';
import { FormSubmitButton } from '@/components/form-submit-button';
import { EmptyState, ErrorState } from '@/components/states';
import { fetchDashboardApiKeys, fetchWorkspaces } from '@/lib/api';
import { formatTimestamp } from '@/lib/format';

const NEW_API_KEY_COOKIE = 'daai_new_api_key';

type NewApiKeyFlash = {
  id: string;
  name: string;
  workspace_id: string;
  workspace_name: string;
  raw_api_key: string;
};

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

function readNewApiKeyFlash(): NewApiKeyFlash | null {
  const cookieStore = (cookies() as unknown as UnsafeUnwrappedCookies);
  const cookieValue = cookieStore.get(NEW_API_KEY_COOKIE)?.value;
  if (!cookieValue) {
    return null;
  }

  try {
    const parsed = JSON.parse(decodeURIComponent(cookieValue)) as {
      id?: unknown;
      name?: unknown;
      workspace_id?: unknown;
      workspace_name?: unknown;
      raw_api_key?: unknown;
    };

    if (
      typeof parsed.id !== 'string' ||
      typeof parsed.name !== 'string' ||
      typeof parsed.workspace_id !== 'string' ||
      typeof parsed.workspace_name !== 'string' ||
      typeof parsed.raw_api_key !== 'string'
    ) {
      return null;
    }

    return {
      id: parsed.id,
      name: parsed.name,
      workspace_id: parsed.workspace_id,
      workspace_name: parsed.workspace_name,
      raw_api_key: parsed.raw_api_key,
    };
  } catch {
    return null;
  }
}

function maskPrefix(prefix: string): string {
  return `${prefix}********`;
}

export default async function AccountPage(
  props: {
    searchParams?: Promise<{
      error?: string;
      created?: string;
      revoked?: string;
    }>;
  }
) {
  const searchParams = await props.searchParams;
  const [workspacesResult, apiKeysResult] = await Promise.all([
    fetchWorkspaces(),
    fetchDashboardApiKeys(),
  ]);

  if (workspacesResult.error) {
    return <ErrorState title="Account Unavailable" message={workspacesResult.error} />;
  }
  if (apiKeysResult.error) {
    return <ErrorState title="Account Unavailable" message={apiKeysResult.error} />;
  }

  const workspaces = workspacesResult.data ?? [];
  const apiKeys = apiKeysResult.data ?? [];
  const newApiKey = readNewApiKeyFlash();
  const errorMessage = decodeMessage(searchParams?.error);

  return (
    <section className="space-y-5">
      <Breadcrumbs items={[{ label: 'Home', href: '/home' }, { label: 'Account' }]} />

      <PageHeader
        title="Account"
        description="Manage workspace-scoped API keys used by SDK clients. Keys are hashed at rest."
      />

      {errorMessage ? (
        <Notice tone="danger">
          {errorMessage}
        </Notice>
      ) : null}

      {searchParams?.revoked === '1' ? (
        <Notice tone="warning">
          API key revoked.
        </Notice>
      ) : null}

      {newApiKey ? (
        <SectionCard
          title="New API key (shown once)"
          description="Save this key now. It will not be shown again."
          className="border-brand/40 bg-brand/10"
        >
          <div className="rounded-md border border-brand/30 bg-canvas p-3">
            <p className="text-xs text-muted">
              {newApiKey.name} for {newApiKey.workspace_name}
            </p>
            <p className="mt-2 break-all font-mono text-xs text-text">{newApiKey.raw_api_key}</p>
            <div className="mt-3">
              <CopyButton value={newApiKey.raw_api_key} label="Copy key" />
            </div>
          </div>
        </SectionCard>
      ) : null}

      <SectionCard
        title="Create API key"
        description="Create a workspace-scoped key for SDK interception requests."
      >
        <form action={createApiKeyAction} className="mt-4 grid gap-3 md:grid-cols-2">
          <div>
            <label htmlFor="name" className="block text-sm font-medium text-text">
              Key name
            </label>
            <input
              id="name"
              name="name"
              type="text"
              maxLength={160}
              required
              placeholder="Invoice Runner Key"
              className={`mt-1 ${fieldStyles}`}
            />
          </div>

          <div>
            <label htmlFor="workspace_id" className="block text-sm font-medium text-text">
              Workspace
            </label>
            <select
              id="workspace_id"
              name="workspace_id"
              required
              className={`mt-1 ${selectStyles}`}
            >
              <option value="">Select workspace</option>
              {workspaces.map((workspace) => (
                <option key={workspace.id} value={workspace.id}>
                  {workspace.name}
                </option>
              ))}
            </select>
          </div>

          <div className="md:col-span-2">
            <FormSubmitButton
              label="Create API key"
              loadingLabel="Creating API key..."
              className={buttonStyles.primary}
            />
          </div>
        </form>
      </SectionCard>

      <SectionCard
        title="API keys"
        description="Existing keys show only a masked prefix. Revoked keys cannot authenticate SDK requests."
      >
        {apiKeys.length === 0 ? (
          <div className="mt-4">
            <EmptyState
              title="No API keys yet"
              message="Create a key above for SDK access."
            />
          </div>
        ) : (
          <TableShell>
            <table className="min-w-full divide-y divide-border text-sm">
              <thead className="bg-panelHover">
                <tr>
                  <th className="px-3 py-2 text-left font-medium text-muted">Name</th>
                  <th className="px-3 py-2 text-left font-medium text-muted">Workspace</th>
                  <th className="px-3 py-2 text-left font-medium text-muted">Key</th>
                  <th className="px-3 py-2 text-left font-medium text-muted">Created</th>
                  <th className="px-3 py-2 text-left font-medium text-muted">Last used</th>
                  <th className="px-3 py-2 text-left font-medium text-muted">Status</th>
                  <th className="px-3 py-2 text-left font-medium text-muted">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border bg-canvas">
                {apiKeys.map((apiKey) => (
                  <tr key={apiKey.id} className="transition hover:bg-panelHover">
                    <td className="px-3 py-2 text-text">{apiKey.name}</td>
                    <td className="px-3 py-2 text-muted">{apiKey.workspace_name}</td>
                    <td className="px-3 py-2 font-mono text-xs text-muted">
                      {maskPrefix(apiKey.key_prefix)}
                    </td>
                    <td className="px-3 py-2 text-muted">{formatTimestamp(apiKey.created_at)}</td>
                    <td className="px-3 py-2 text-muted">
                      {formatTimestamp(apiKey.last_used_at)}
                    </td>
                    <td className="px-3 py-2 text-muted">
                      <StatusBadge
                        label={apiKey.status === 'revoked' ? 'revoked' : 'active'}
                        tone={apiKey.status === 'revoked' ? 'neutral' : 'success'}
                      />
                    </td>
                    <td className="px-3 py-2">
                      {apiKey.status === 'revoked' ? (
                        <span className="text-xs text-muted">Revoked</span>
                      ) : (
                        <form action={revokeApiKeyAction}>
                          <input type="hidden" name="api_key_id" value={apiKey.id} />
                          <FormSubmitButton
                            label="Revoke"
                            loadingLabel="Revoking..."
                            className={`${buttonStyles.danger} px-3 py-2 text-xs`}
                          />
                        </form>
                      )}
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
