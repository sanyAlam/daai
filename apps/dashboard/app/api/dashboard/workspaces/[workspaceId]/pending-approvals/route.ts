import { NextRequest } from 'next/server';

import {
  getDashboardSessionToken,
  proxyDashboardRequest,
} from '@/lib/dashboard-api-proxy';

function copyAllowedQueryParams(source: URLSearchParams): URLSearchParams {
  const target = new URLSearchParams();
  const limit = source.get('limit');
  if (limit && limit.trim()) {
    target.set('limit', limit);
  }
  return target;
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ workspaceId: string }> },
) {
  const session = await getDashboardSessionToken();
  if (!session.ok) {
    return session.response;
  }

  const queryParams = copyAllowedQueryParams(request.nextUrl.searchParams);
  const queryString = queryParams.toString();

  return proxyDashboardRequest(
    `/v1/dashboard/workspaces/${(await context.params).workspaceId}/pending-approvals${
      queryString ? `?${queryString}` : ''
    }`,
    {
      method: 'GET',
      token: session.token,
    },
  );
}
