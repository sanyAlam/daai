import { SupabaseSession, SupabaseUser } from '@/lib/supabase/types';

export const DAAI_SUPABASE_SESSION_COOKIE = 'daai_supabase_session';

type TokenResponse = {
  access_token?: unknown;
  refresh_token?: unknown;
  expires_in?: unknown;
  user?: {
    id?: unknown;
    email?: unknown;
  } | null;
};

export function parseSessionCookie(value: string | undefined): SupabaseSession | null {
  if (!value) {
    return null;
  }
  try {
    const decoded = decodeURIComponent(value);
    const parsed = JSON.parse(decoded) as {
      access_token?: unknown;
      refresh_token?: unknown;
      expires_at?: unknown;
      user?: { id?: unknown; email?: unknown };
    };

    if (
      typeof parsed.access_token !== 'string' ||
      typeof parsed.refresh_token !== 'string' ||
      typeof parsed.expires_at !== 'number' ||
      !parsed.user ||
      typeof parsed.user.id !== 'string'
    ) {
      return null;
    }

    return {
      access_token: parsed.access_token,
      refresh_token: parsed.refresh_token,
      expires_at: parsed.expires_at,
      user: {
        id: parsed.user.id,
        email: typeof parsed.user.email === 'string' ? parsed.user.email : null,
      },
    };
  } catch {
    return null;
  }
}

export function serializeSessionCookie(session: SupabaseSession): string {
  return encodeURIComponent(JSON.stringify(session));
}

export function toSessionFromTokenResponse(
  tokenResponse: TokenResponse,
): SupabaseSession | null {
  const accessToken = tokenResponse.access_token;
  const refreshToken = tokenResponse.refresh_token;
  const expiresIn = tokenResponse.expires_in;
  const user = tokenResponse.user;

  if (
    typeof accessToken !== 'string' ||
    typeof refreshToken !== 'string' ||
    typeof expiresIn !== 'number' ||
    !user ||
    typeof user.id !== 'string'
  ) {
    return null;
  }

  const normalizedUser: SupabaseUser = {
    id: user.id,
    email: typeof user.email === 'string' ? user.email : null,
  };

  const nowEpochSeconds = Math.floor(Date.now() / 1000);
  return {
    access_token: accessToken,
    refresh_token: refreshToken,
    expires_at: nowEpochSeconds + expiresIn,
    user: normalizedUser,
  };
}
