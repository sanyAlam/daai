import { redirect } from 'next/navigation';

export default async function WorkspaceReceiptsCompatRedirect(
  props: {
    params: Promise<{ workspaceId: string }>;
  }
) {
  const params = await props.params;
  redirect(`/workspaces/${params.workspaceId}/receipts`);
}
