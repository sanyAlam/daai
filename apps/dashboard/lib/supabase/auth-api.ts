import { getSupabaseConfig } from '@/lib/supabase/config';
import { SupabaseAuthResult, SupabaseUser } from '@/lib/supabase/types';

type TokenResponse = {
  access_token?: unknown;
  refresh_token?: unknown;
  expires_in?: unknown;
  user?: {
    id?: unknown;
    email?: unknown;
  } | null;
};

type JsonRecord = Record<string, unknown>;

function readErrorMessage(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== 'object') {
    return fallback;
  }
  const record = payload as JsonRecord;
  const candidates = [
    record.error_description,
    record.msg,
    record.message,
    record.error,
  ];
  for (const candidate of candidates) {
    if (typeof candidate === 'string' && candidate.trim()) {
      return candidate;
    }
  }
  return fallback;
}

async function parseJsonSafely(response: Response): Promise<unknown> {
  try {
    return (await response.json()) as unknown;
  } catch {
    return null;
  }
}

function baseHeaders(anonKey: string): HeadersInit {
  return {
    apikey: anonKey,
    'Content-Type': 'application/json',
  };
}

function readUserPayload(payload: unknown): SupabaseAuthResult<SupabaseUser> {
  if (!payload || typeof payload !== 'object') {
    return {
      data: null,
      error: 'Invalid user payload from Supabase',
    };
  }

  const payloadRecord = payload as JsonRecord;
  const record =
    payloadRecord.user && typeof payloadRecord.user === 'object'
      ? (payloadRecord.user as JsonRecord)
      : payloadRecord;
  const id = record.id;
  const email = record.email;
  if (typeof id !== 'string' || !id) {
    return {
      data: null,
      error: 'Supabase user id is missing',
    };
  }

  return {
    data: {
      id,
      email: typeof email === 'string' ? email : null,
    },
    error: null,
  };
}

export async function signUpWithEmailPassword(
  email: string,
  password: string,
  emailRedirectTo?: string,
): Promise<SupabaseAuthResult<TokenResponse>> {
  const { url, anonKey } = getSupabaseConfig();
  const normalizedRedirectTo = emailRedirectTo?.trim() || undefined;
  const signupUrl = new URL(`${url}/auth/v1/signup`);
  if (normalizedRedirectTo) {
    // Keep query param for GoTrue compatibility with redirect-based email links.
    signupUrl.searchParams.set('redirect_to', normalizedRedirectTo);
  }

  const body: Record<string, unknown> = { email, password };
  if (normalizedRedirectTo) {
    // Supabase client APIs expose this as `options.emailRedirectTo`.
    body.options = { email_redirect_to: normalizedRedirectTo };
  }

  const response = await fetch(signupUrl.toString(), {
    method: 'POST',
    headers: baseHeaders(anonKey),
    body: JSON.stringify(body),
    cache: 'no-store',
  });
  const payload = await parseJsonSafely(response);
  if (!response.ok) {
    return {
      data: null,
      error: readErrorMessage(payload, 'Signup failed'),
    };
  }
  return {
    data: (payload as TokenResponse) ?? null,
    error: null,
  };
}

export async function signInWithPassword(
  email: string,
  password: string,
): Promise<SupabaseAuthResult<TokenResponse>> {
  const { url, anonKey } = getSupabaseConfig();
  const response = await fetch(`${url}/auth/v1/token?grant_type=password`, {
    method: 'POST',
    headers: baseHeaders(anonKey),
    body: JSON.stringify({ email, password }),
    cache: 'no-store',
  });
  const payload = await parseJsonSafely(response);
  if (!response.ok) {
    return {
      data: null,
      error: readErrorMessage(payload, 'Login failed'),
    };
  }
  return {
    data: (payload as TokenResponse) ?? null,
    error: null,
  };
}

export async function requestPasswordResetEmail(
  email: string,
  redirectTo: string,
): Promise<SupabaseAuthResult<{ sent: true }>> {
  const { url, anonKey } = getSupabaseConfig();
  const recoverUrl = new URL(`${url}/auth/v1/recover`);
  recoverUrl.searchParams.set('redirect_to', redirectTo);

  const response = await fetch(recoverUrl.toString(), {
    method: 'POST',
    headers: baseHeaders(anonKey),
    body: JSON.stringify({ email }),
    cache: 'no-store',
  });
  const payload = await parseJsonSafely(response);
  if (!response.ok) {
    return {
      data: null,
      error: readErrorMessage(payload, 'Password reset request failed'),
    };
  }
  return {
    data: { sent: true },
    error: null,
  };
}

export async function refreshSession(
  refreshToken: string,
): Promise<SupabaseAuthResult<TokenResponse>> {
  const { url, anonKey } = getSupabaseConfig();
  const response = await fetch(`${url}/auth/v1/token?grant_type=refresh_token`, {
    method: 'POST',
    headers: baseHeaders(anonKey),
    body: JSON.stringify({ refresh_token: refreshToken }),
    cache: 'no-store',
  });
  const payload = await parseJsonSafely(response);
  if (!response.ok) {
    return {
      data: null,
      error: readErrorMessage(payload, 'Session refresh failed'),
    };
  }
  return {
    data: (payload as TokenResponse) ?? null,
    error: null,
  };
}

export async function getUserFromAccessToken(
  accessToken: string,
): Promise<SupabaseAuthResult<SupabaseUser>> {
  const { url, anonKey } = getSupabaseConfig();
  const response = await fetch(`${url}/auth/v1/user`, {
    method: 'GET',
    headers: {
      apikey: anonKey,
      Authorization: `Bearer ${accessToken}`,
    },
    cache: 'no-store',
  });

  const payload = await parseJsonSafely(response);
  if (!response.ok) {
    return {
      data: null,
      error: readErrorMessage(payload, 'User session is invalid'),
    };
  }

  return readUserPayload(payload);
}

export async function updateUserPassword(
  accessToken: string,
  password: string,
): Promise<SupabaseAuthResult<SupabaseUser>> {
  const { url, anonKey } = getSupabaseConfig();
  const response = await fetch(`${url}/auth/v1/user`, {
    method: 'PUT',
    headers: {
      ...baseHeaders(anonKey),
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify({ password }),
    cache: 'no-store',
  });

  const payload = await parseJsonSafely(response);
  if (!response.ok) {
    return {
      data: null,
      error: readErrorMessage(payload, 'Password update failed'),
    };
  }

  return readUserPayload(payload);
}

export async function signOut(accessToken: string): Promise<void> {
  const { url, anonKey } = getSupabaseConfig();
  await fetch(`${url}/auth/v1/logout`, {
    method: 'POST',
    headers: {
      apikey: anonKey,
      Authorization: `Bearer ${accessToken}`,
    },
    cache: 'no-store',
  });
}
