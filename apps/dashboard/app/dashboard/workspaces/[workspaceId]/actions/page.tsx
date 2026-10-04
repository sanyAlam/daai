import { redirect } from 'next/navigation';

export default async function WorkspaceActionsCompatRedirect(
  props: {
    params: Promise<{ workspaceId: string }>;
  }
) {
  const params = await props.params;
  redirect(`/workspaces/${params.workspaceId}/actions`);
}
