import {
  getDashboardSessionToken,
  proxyDashboardRequest,
} from '@/lib/dashboard-api-proxy';

export async function POST(
  _request: Request,
  context: { params: Promise<{ actionRunId: string }> },
) {
  const session = await getDashboardSessionToken();
  if (!session.ok) {
    return session.response;
  }

  return proxyDashboardRequest(
    `/v1/dashboard/action-runs/${(await context.params).actionRunId}/reject`,
    {
      method: 'POST',
      token: session.token,
      body: {},
    },
  );
}
