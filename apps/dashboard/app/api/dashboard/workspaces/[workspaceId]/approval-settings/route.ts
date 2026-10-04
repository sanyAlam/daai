import { NextRequest, NextResponse } from 'next/server';

import {
  getDashboardSessionToken,
  proxyDashboardRequest,
} from '@/lib/dashboard-api-proxy';

export async function GET(
  _request: NextRequest,
  context: { params: Promise<{ workspaceId: string }> },
) {
  const session = await getDashboardSessionToken();
  if (!session.ok) {
    return session.response;
  }

  return proxyDashboardRequest(
    `/v1/dashboard/workspaces/${(await context.params).workspaceId}/approval-settings`,
    {
      method: 'GET',
      token: session.token,
    },
  );
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ workspaceId: string }> },
) {
  const session = await getDashboardSessionToken();
  if (!session.ok) {
    return session.response;
  }

  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return NextResponse.json({ detail: 'Invalid JSON body.' }, { status: 400 });
  }

  return proxyDashboardRequest(
    `/v1/dashboard/workspaces/${(await context.params).workspaceId}/approval-settings`,
    {
      method: 'POST',
      token: session.token,
      body,
    },
  );
}
