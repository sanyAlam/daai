'use server';

import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';

import {
  createDashboardApiKey,
  regenerateWorkspaceKey,
  revokeDashboardApiKey,
} from '@/lib/api';

const NEW_API_KEY_COOKIE = 'daai_new_api_key';
const NEW_WORKSPACE_KEY_COOKIE = 'daai_new_workspace_key';

function encodeMessage(message: string): string {
  return encodeURIComponent(message);
}

function sanitizeWorkspacePath(workspaceId: string, returnTo: string | null): string {
  if (returnTo && returnTo.startsWith(`/workspaces/${workspaceId}`)) {
    return returnTo;
  }
  return `/workspaces/${workspaceId}/setup`;
}

export async function createApiKeyAction(formData: FormData): Promise<never> {
  const keyNameValue = formData.get('name');
  const workspaceIdValue = formData.get('workspace_id');

  const name = typeof keyNameValue === 'string' ? keyNameValue.trim() : '';
  const workspaceId =
    typeof workspaceIdValue === 'string' ? workspaceIdValue.trim() : '';

  if (!name || !workspaceId) {
    redirect('/account?error=' + encodeMessage('Key name and workspace are required.'));
  }

  const result = await createDashboardApiKey({
    workspaceId,
    name,
  });

  if (result.error || !result.data) {
    redirect('/account?error=' + encodeMessage(result.error ?? 'API key creation failed.'));
  }

  const cookieStore = await cookies();
  cookieStore.set(
    NEW_API_KEY_COOKIE,
    encodeURIComponent(
      JSON.stringify({
        id: result.data.id,
        name: result.data.name,
        workspace_id: result.data.workspace_id,
        workspace_name: result.data.workspace_name,
        raw_api_key: result.data.raw_api_key,
      }),
    ),
    {
      httpOnly: true,
      sameSite: 'lax',
      secure: process.env.NODE_ENV === 'production',
      path: '/account',
      maxAge: 300,
    },
  );

  redirect('/account?created=1');
}

export async function revokeApiKeyAction(formData: FormData): Promise<never> {
  const apiKeyIdValue = formData.get('api_key_id');
  const apiKeyId = typeof apiKeyIdValue === 'string' ? apiKeyIdValue.trim() : '';

  if (!apiKeyId) {
    redirect('/account?error=' + encodeMessage('API key id is required.'));
  }

  const result = await revokeDashboardApiKey(apiKeyId);

  if (result.error || !result.data) {
    redirect('/account?error=' + encodeMessage(result.error ?? 'API key revoke failed.'));
  }

  redirect('/account?revoked=1');
}

export async function regenerateWorkspaceKeyAction(formData: FormData): Promise<never> {
  const workspaceIdValue = formData.get('workspace_id');
  const returnToValue = formData.get('return_to');

  const workspaceId =
    typeof workspaceIdValue === 'string' ? workspaceIdValue.trim() : '';
  const returnTo = typeof returnToValue === 'string' ? returnToValue.trim() : null;

  if (!workspaceId) {
    redirect('/home');
  }

  const redirectTarget = sanitizeWorkspacePath(workspaceId, returnTo);

  const result = await regenerateWorkspaceKey(workspaceId);

  if (result.error || !result.data) {
    redirect(
      `${redirectTarget}?key_error=${encodeMessage(
        result.error ?? 'Workspace key regeneration failed.',
      )}`,
    );
  }

  if (result.data.workspace_key) {
    const cookieStore = await cookies();
    cookieStore.set(
      NEW_WORKSPACE_KEY_COOKIE,
      encodeURIComponent(
        JSON.stringify({
          workspace_id: workspaceId,
          workspace_key: result.data.workspace_key,
        }),
      ),
      {
        httpOnly: true,
        sameSite: 'lax',
        secure: process.env.NODE_ENV === 'production',
        path: `/workspaces/${workspaceId}`,
        maxAge: 300,
      },
    );
  }

  redirect(`${redirectTarget}?regenerated=1`);
}
