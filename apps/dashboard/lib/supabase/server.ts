import { cookies, type UnsafeUnwrappedCookies } from 'next/headers';

import {
  getUserFromAccessToken,
  requestPasswordResetEmail,
  refreshSession,
  signInWithPassword,
  signOut,
  signUpWithEmailPassword,
  updateUserPassword,
} from '@/lib/supabase/auth-api';
import {
  DAAI_SUPABASE_SESSION_COOKIE,
  parseSessionCookie,
  serializeSessionCookie,
  toSessionFromTokenResponse,
} from '@/lib/supabase/session';
import { SupabaseSession, SupabaseUser } from '@/lib/supabase/types';

type AuthError = {
  message: string;
};

type AuthResult<T> = {
  data: T;
  error: AuthError | null;
};

type SessionEnvelope = {
  session: SupabaseSession | null;
  user: SupabaseUser | null;
};

function cookieOptions(expiresAt: number) {
  return {
    httpOnly: true,
    sameSite: 'lax' as const,
    secure: process.env.NODE_ENV === 'production',
    path: '/',
    expires: new Date(expiresAt * 1000),
  };
}

function readStoredSession(): SupabaseSession | null {
  const cookieStore = (cookies() as unknown as UnsafeUnwrappedCookies);
  return parseSessionCookie(cookieStore.get(DAAI_SUPABASE_SESSION_COOKIE)?.value);
}

function writeStoredSession(session: SupabaseSession): void {
  const cookieStore = (cookies() as unknown as UnsafeUnwrappedCookies);
  try {
    cookieStore.set(
      DAAI_SUPABASE_SESSION_COOKIE,
      serializeSessionCookie(session),
      cookieOptions(session.expires_at),
    );
  } catch {
    // Server Components cannot always mutate cookies.
  }
}

function clearStoredSession(): void {
  const cookieStore = (cookies() as unknown as UnsafeUnwrappedCookies);
  try {
    cookieStore.delete(DAAI_SUPABASE_SESSION_COOKIE);
  } catch {
    // Server Components cannot always mutate cookies.
  }
}

function expiresAtFromExpiresIn(expiresIn: number): number {
  return Math.floor(Date.now() / 1000) + expiresIn;
}

async function resolveSession(): Promise<AuthResult<SessionEnvelope>> {
  const stored = readStoredSession();
  if (!stored) {
    return {
      data: { session: null, user: null },
      error: null,
    };
  }

  const userResult = await getUserFromAccessToken(stored.access_token);
  if (!userResult.error && userResult.data) {
    const normalizedSession: SupabaseSession = {
      ...stored,
      user: userResult.data,
    };
    writeStoredSession(normalizedSession);
    return {
      data: { session: normalizedSession, user: normalizedSession.user },
      error: null,
    };
  }

  const refreshed = await refreshSession(stored.refresh_token);
  if (!refreshed.error && refreshed.data) {
    const refreshedSession = toSessionFromTokenResponse(refreshed.data);
    if (refreshedSession) {
      writeStoredSession(refreshedSession);
      return {
        data: { session: refreshedSession, user: refreshedSession.user },
        error: null,
      };
    }
  }

  clearStoredSession();
  return {
    data: { session: null, user: null },
    error: userResult.error ? { message: userResult.error } : null,
  };
}

export function createSupabaseServerClient() {
  return {
    auth: {
      async getUser(): Promise<AuthResult<{ user: SupabaseUser | null }>> {
        const sessionResult = await resolveSession();
        return {
          data: { user: sessionResult.data.user },
          error: sessionResult.error,
        };
      },

      async getSession(): Promise<AuthResult<{ session: SupabaseSession | null }>> {
        const sessionResult = await resolveSession();
        return {
          data: { session: sessionResult.data.session },
          error: sessionResult.error,
        };
      },

      async signUp({
        email,
        password,
        options,
      }: {
        email: string;
        password: string;
        options?: {
          emailRedirectTo?: string;
        };
      }): Promise<
        AuthResult<{
          session: SupabaseSession | null;
          user: SupabaseUser | null;
        }>
      > {
        const response = await signUpWithEmailPassword(
          email,
          password,
          options?.emailRedirectTo,
        );
        if (response.error || !response.data) {
          return {
            data: { session: null, user: null },
            error: { message: response.error ?? 'Signup failed' },
          };
        }

        const session = toSessionFromTokenResponse(response.data);
        if (!session) {
          return {
            data: { session: null, user: null },
            error: null,
          };
        }

        writeStoredSession(session);
        return {
          data: { session, user: session.user },
          error: null,
        };
      },

      async signInWithPassword({
        email,
        password,
      }: {
        email: string;
        password: string;
      }): Promise<
        AuthResult<{
          session: SupabaseSession | null;
          user: SupabaseUser | null;
        }>
      > {
        const response = await signInWithPassword(email, password);
        if (response.error || !response.data) {
          return {
            data: { session: null, user: null },
            error: { message: response.error ?? 'Login failed' },
          };
        }

        const session = toSessionFromTokenResponse(response.data);
        if (!session) {
          return {
            data: { session: null, user: null },
            error: { message: 'Supabase session payload is missing tokens' },
          };
        }

        writeStoredSession(session);
        return {
          data: { session, user: session.user },
          error: null,
        };
      },

      async resetPasswordForEmail(
        email: string,
        {
          redirectTo,
        }: {
          redirectTo: string;
        },
      ): Promise<AuthResult<{ sent: boolean }>> {
        const response = await requestPasswordResetEmail(email, redirectTo);
        if (response.error || !response.data) {
          return {
            data: { sent: false },
            error: { message: response.error ?? 'Password reset request failed' },
          };
        }

        return {
          data: { sent: true },
          error: null,
        };
      },

      async setSession({
        access_token,
        refresh_token,
        expires_in,
      }: {
        access_token: string;
        refresh_token: string;
        expires_in: number;
      }): Promise<AuthResult<{ session: SupabaseSession | null }>> {
        const userResult = await getUserFromAccessToken(access_token);
        if (userResult.error || !userResult.data) {
          clearStoredSession();
          return {
            data: { session: null },
            error: { message: userResult.error ?? 'Recovery session is invalid' },
          };
        }

        const session: SupabaseSession = {
          access_token,
          refresh_token,
          expires_at: expiresAtFromExpiresIn(expires_in),
          user: userResult.data,
        };
        writeStoredSession(session);
        return {
          data: { session },
          error: null,
        };
      },

      async updateUser({
        password,
      }: {
        password: string;
      }): Promise<AuthResult<{ user: SupabaseUser | null; sessionStillValid: boolean }>> {
        const sessionResult = await resolveSession();
        const session = sessionResult.data.session;
        if (!session?.access_token) {
          clearStoredSession();
          return {
            data: { user: null, sessionStillValid: false },
            error: { message: 'Password reset session is missing or expired.' },
          };
        }

        const response = await updateUserPassword(session.access_token, password);
        if (response.error || !response.data) {
          return {
            data: { user: null, sessionStillValid: false },
            error: { message: response.error ?? 'Password update failed' },
          };
        }

        const userResult = await getUserFromAccessToken(session.access_token);
        if (userResult.error || !userResult.data) {
          clearStoredSession();
          return {
            data: { user: response.data, sessionStillValid: false },
            error: null,
          };
        }

        writeStoredSession({
          ...session,
          user: userResult.data,
        });
        return {
          data: { user: userResult.data, sessionStillValid: true },
          error: null,
        };
      },

      async signOut(): Promise<AuthResult<{ signedOut: true }>> {
        const stored = readStoredSession();
        if (stored?.access_token) {
          await signOut(stored.access_token);
        }
        clearStoredSession();
        return {
          data: { signedOut: true },
          error: null,
        };
      },
    },
  };
}
