'use server';

import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';

import { createWorkspace, deleteWorkspace } from '@/lib/api';

const NEW_WORKSPACE_KEY_COOKIE = 'daai_new_workspace_key';

function encodeMessage(message: string): string {
  return encodeURIComponent(message);
}

function friendlyWorkspaceError(message: string): string {
  const lower = message.toLowerCase();
  if (lower.includes('free beta') || lower.includes('limit reached')) {
    return 'Beta limit reached. Usage is capped during launch to protect reliability.';
  }
  return message;
}

export async function createWorkspaceAction(formData: FormData): Promise<never> {
  const workspaceNameValue = formData.get('workspace_name');
  const clientNameValue = formData.get('client_name');

  const workspaceName =
    typeof workspaceNameValue === 'string' ? workspaceNameValue.trim() : '';
  const clientName = typeof clientNameValue === 'string' ? clientNameValue.trim() : '';

  if (!workspaceName || !clientName) {
    redirect('/home?create_error=' + encodeMessage('Workspace name and client name are required.'));
  }

  const result = await createWorkspace({
    workspaceName,
    clientName,
  });

  if (result.error || !result.data) {
    redirect(
      '/home?create_error=' +
        encodeMessage(
          friendlyWorkspaceError(result.error ?? 'Workspace creation failed.'),
        ),
    );
  }

  if (result.data.workspace_key) {
    const cookieStore = await cookies();
    cookieStore.set(
      NEW_WORKSPACE_KEY_COOKIE,
      encodeURIComponent(
        JSON.stringify({
          workspace_id: result.data.id,
          workspace_key: result.data.workspace_key,
        }),
      ),
      {
        httpOnly: true,
        sameSite: 'lax',
        secure: process.env.NODE_ENV === 'production',
        path: `/workspaces/${result.data.id}/setup`,
        maxAge: 300,
      },
    );
  }

  redirect(`/workspaces/${result.data.id}/setup?created=1`);
}

export async function deleteWorkspaceAction(formData: FormData): Promise<never> {
  const workspaceIdValue = formData.get('workspace_id');
  const workspaceNameValue = formData.get('workspace_name');
  const confirmationValue = formData.get('workspace_name_confirmation');

  const workspaceId =
    typeof workspaceIdValue === 'string' ? workspaceIdValue.trim() : '';
  const workspaceName =
    typeof workspaceNameValue === 'string' ? workspaceNameValue.trim() : '';
  const confirmation =
    typeof confirmationValue === 'string' ? confirmationValue.trim() : '';

  const setupHref = workspaceId
    ? `/workspaces/${workspaceId}/setup`
    : '/home';

  if (!workspaceId || !workspaceName) {
    redirect(`${setupHref}?delete_error=${encodeMessage('Workspace details are missing.')}`);
  }

  if (confirmation !== workspaceName) {
    redirect(
      `${setupHref}?delete_error=${encodeMessage(
        'Paste the workspace name exactly to confirm deletion.',
      )}`,
    );
  }

  const result = await deleteWorkspace({
    workspaceId,
    workspaceNameConfirmation: confirmation,
  });

  if (result.error || !result.data) {
    redirect(
      `${setupHref}?delete_error=${encodeMessage(
        friendlyWorkspaceError(result.error ?? 'Workspace deletion failed.'),
      )}`,
    );
  }

  redirect(`/home?deleted=${encodeMessage(result.data.name)}`);
}
