import { redirect } from 'next/navigation';

export default async function WorkspaceRunDetailCompatRedirect(
  props: {
    params: Promise<{ workspaceId: string; actionRunId: string }>;
  }
) {
  const params = await props.params;
  redirect(`/workspaces/${params.workspaceId}/runs/${params.actionRunId}`);
}
