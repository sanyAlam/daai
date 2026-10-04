import { NextResponse } from 'next/server';

import { createSupabaseServerClient } from '@/lib/supabase/server';

const DEFAULT_API_BASE_URL =
  process.env.NODE_ENV === 'production'
    ? 'http://127.0.0.1:8000'
    : 'http://127.0.0.1:8000';
const API_BASE_URL = process.env.DAAI_API_BASE_URL ?? DEFAULT_API_BASE_URL;

export async function getDashboardSessionToken(): Promise<
  { ok: true; token: string } | { ok: false; response: NextResponse }
> {
  const supabase = createSupabaseServerClient();
  const {
    data: { session },
    error: sessionError,
  } = await supabase.auth.getSession();

  if (sessionError || !session?.access_token) {
    return {
      ok: false,
      response: NextResponse.json(
        { detail: 'Dashboard auth session is missing. Log in again.' },
        { status: 401 },
      ),
    };
  }

  return { ok: true, token: session.access_token };
}

function normalizeFailureStatus(status: number): number {
  if (status >= 400 && status <= 599) {
    return status;
  }
  return 502;
}

export async function proxyDashboardRequest(
  path: string,
  options: {
    method: 'GET' | 'POST';
    token: string;
    body?: Record<string, unknown>;
  },
): Promise<NextResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: options.method,
      headers: {
        Authorization: `Bearer ${options.token}`,
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
      cache: 'no-store',
    });

    const text = await response.text();
    let payload: Record<string, unknown> = {};
    if (text) {
      try {
        payload = JSON.parse(text) as Record<string, unknown>;
      } catch {
        payload = {};
      }
    }

    if (!response.ok) {
      const detail =
        typeof payload.detail === 'string' && payload.detail
          ? payload.detail
          : response.statusText || 'Request failed';
      return NextResponse.json(
        { detail },
        { status: normalizeFailureStatus(response.status) },
      );
    }

    return NextResponse.json(payload, { status: 200 });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error';
    return NextResponse.json(
      { detail: `Cannot reach dashboard API: ${message}` },
      { status: 502 },
    );
  }
}
