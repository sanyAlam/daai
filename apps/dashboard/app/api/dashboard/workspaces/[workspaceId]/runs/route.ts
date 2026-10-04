import { NextRequest } from 'next/server';

import {
  getDashboardSessionToken,
  proxyDashboardRequest,
} from '@/lib/dashboard-api-proxy';

function copyAllowedQueryParams(source: URLSearchParams): URLSearchParams {
  const allowed = new Set([
    'page',
    'page_size',
    'search',
    'governance_status',
    'execution_status',
  ]);
  const target = new URLSearchParams();

  for (const [key, value] of source.entries()) {
    if (allowed.has(key) && value.trim()) {
      target.set(key, value);
    }
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
  const path = `/v1/dashboard/workspaces/${
    (await context.params).workspaceId
  }/runs${queryString ? `?${queryString}` : ''}`;
  return proxyDashboardRequest(path, {
    method: 'GET',
    token: session.token,
  });
}
