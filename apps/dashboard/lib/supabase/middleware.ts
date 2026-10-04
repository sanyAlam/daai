import { NextResponse, type NextRequest } from 'next/server';

import { getUserFromAccessToken, refreshSession } from '@/lib/supabase/auth-api';
import {
  DAAI_SUPABASE_SESSION_COOKIE,
  parseSessionCookie,
  serializeSessionCookie,
  toSessionFromTokenResponse,
} from '@/lib/supabase/session';
import { SupabaseSession, SupabaseUser } from '@/lib/supabase/types';

function cookieOptions(expiresAt: number) {
  return {
    httpOnly: true,
    sameSite: 'lax' as const,
    secure: process.env.NODE_ENV === 'production',
    path: '/',
    expires: new Date(expiresAt * 1000),
  };
}

export async function updateSupabaseSession(
  request: NextRequest,
): Promise<{ response: NextResponse; user: SupabaseUser | null }> {
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set('x-daai-pathname', request.nextUrl.pathname);

  const response = NextResponse.next({
    request: {
      headers: requestHeaders,
    },
  });

  const stored = parseSessionCookie(
    request.cookies.get(DAAI_SUPABASE_SESSION_COOKIE)?.value,
  );
  if (!stored) {
    return { response, user: null };
  }

  const userResult = await getUserFromAccessToken(stored.access_token);
  if (!userResult.error && userResult.data) {
    const normalizedSession: SupabaseSession = {
      ...stored,
      user: userResult.data,
    };
    response.cookies.set(
      DAAI_SUPABASE_SESSION_COOKIE,
      serializeSessionCookie(normalizedSession),
      cookieOptions(normalizedSession.expires_at),
    );
    return {
      response,
      user: normalizedSession.user,
    };
  }

  const refreshed = await refreshSession(stored.refresh_token);
  if (!refreshed.error && refreshed.data) {
    const refreshedSession = toSessionFromTokenResponse(refreshed.data);
    if (refreshedSession) {
      response.cookies.set(
        DAAI_SUPABASE_SESSION_COOKIE,
        serializeSessionCookie(refreshedSession),
        cookieOptions(refreshedSession.expires_at),
      );
      return {
        response,
        user: refreshedSession.user,
      };
    }
  }

  response.cookies.delete(DAAI_SUPABASE_SESSION_COOKIE);
  return { response, user: null };
}
