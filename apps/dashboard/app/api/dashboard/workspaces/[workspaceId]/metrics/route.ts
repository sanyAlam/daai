import {
  getDashboardSessionToken,
  proxyDashboardRequest,
} from '@/lib/dashboard-api-proxy';

export async function GET(
  _request: Request,
  context: { params: Promise<{ workspaceId: string }> },
) {
  const session = await getDashboardSessionToken();
  if (!session.ok) {
    return session.response;
  }

  return proxyDashboardRequest(
    `/v1/dashboard/workspaces/${(await context.params).workspaceId}/metrics`,
    {
      method: 'GET',
      token: session.token,
    },
  );
}
