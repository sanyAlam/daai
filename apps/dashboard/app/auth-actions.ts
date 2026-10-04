'use server';

import { redirect } from 'next/navigation';

import { createSupabaseServerClient } from '@/lib/supabase/server';

function readCredentials(formData: FormData): { email: string; password: string } {
  const emailValue = formData.get('email');
  const passwordValue = formData.get('password');

  const email = typeof emailValue === 'string' ? emailValue.trim() : '';
  const password = typeof passwordValue === 'string' ? passwordValue : '';

  return { email, password };
}

function readPasswordPair(formData: FormData): {
  password: string;
  confirmPassword: string;
} {
  const passwordValue = formData.get('password');
  const confirmPasswordValue = formData.get('confirm_password');

  return {
    password: typeof passwordValue === 'string' ? passwordValue : '',
    confirmPassword:
      typeof confirmPasswordValue === 'string' ? confirmPasswordValue : '',
  };
}

function encodeMessage(message: string): string {
  return encodeURIComponent(message);
}

function resolveSignupEmailRedirectTo(): string | undefined {
  const baseUrl = process.env.DAAI_DASHBOARD_BASE_URL?.trim();
  if (!baseUrl) {
    return undefined;
  }

  const normalizedBase = baseUrl.endsWith('/')
    ? baseUrl.slice(0, -1)
    : baseUrl;
  return `${normalizedBase}/login`;
}

function resolveSiteUrl(): string {
  const configuredSiteUrl = process.env.NEXT_PUBLIC_SITE_URL?.trim();
  const dashboardBaseUrl = process.env.DAAI_DASHBOARD_BASE_URL?.trim();
  const baseUrl = configuredSiteUrl || dashboardBaseUrl || 'http://localhost:3000';
  return baseUrl.endsWith('/') ? baseUrl.slice(0, -1) : baseUrl;
}

function resolvePasswordResetRedirectTo(): string {
  return `${resolveSiteUrl()}/reset-password`;
}

function validateNewPassword(
  password: string,
  confirmPassword: string,
): string | null {
  if (!password) {
    return 'New password is required.';
  }
  if (password.length < 8) {
    return 'Password must be at least 8 characters.';
  }
  if (password !== confirmPassword) {
    return 'Passwords do not match.';
  }
  return null;
}

export async function signupWithPassword(formData: FormData): Promise<never> {
  const { email, password } = readCredentials(formData);
  if (!email || !password) {
    redirect('/signup?error=' + encodeMessage('Email and password are required.'));
  }

  const supabase = createSupabaseServerClient();
  const { data, error } = await supabase.auth.signUp({
    email,
    password,
    options: {
      emailRedirectTo: resolveSignupEmailRedirectTo(),
    },
  });

  if (error) {
    redirect('/signup?error=' + encodeMessage(error.message));
  }

  if (!data.session) {
    redirect(
      '/login?message=' +
        encodeMessage(
          'Signup succeeded. Confirm your email if confirmation is enabled, then log in.',
        ),
    );
  }

  redirect('/home');
}

export async function requestPasswordReset(formData: FormData): Promise<never> {
  const emailValue = formData.get('email');
  const email = typeof emailValue === 'string' ? emailValue.trim() : '';
  if (!email) {
    redirect(
      '/forgot-password?error=' +
        encodeMessage('Enter the email address linked to your DAAI account.'),
    );
  }

  const supabase = createSupabaseServerClient();
  const { error } = await supabase.auth.resetPasswordForEmail(email, {
    redirectTo: resolvePasswordResetRedirectTo(),
  });

  if (error) {
    redirect(
      '/forgot-password?error=' +
        encodeMessage('We could not send a reset link right now. Please try again shortly.'),
    );
  }

  redirect('/forgot-password?sent=1');
}

export async function loginWithPassword(formData: FormData): Promise<never> {
  const { email, password } = readCredentials(formData);
  if (!email || !password) {
    redirect('/login?error=' + encodeMessage('Email and password are required.'));
  }

  const supabase = createSupabaseServerClient();
  const { error } = await supabase.auth.signInWithPassword({
    email,
    password,
  });

  if (error) {
    redirect('/login?error=' + encodeMessage(error.message));
  }

  redirect('/home');
}

export async function establishPasswordRecoverySession({
  accessToken,
  refreshToken,
  expiresIn,
}: {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
}): Promise<{ ok: boolean; message?: string }> {
  if (!accessToken || !refreshToken || !Number.isFinite(expiresIn) || expiresIn <= 0) {
    return {
      ok: false,
      message: 'This reset link is invalid or expired.',
    };
  }

  const supabase = createSupabaseServerClient();
  const { error } = await supabase.auth.setSession({
    access_token: accessToken,
    refresh_token: refreshToken,
    expires_in: expiresIn,
  });

  if (error) {
    return {
      ok: false,
      message: 'This reset link is invalid or expired.',
    };
  }

  return { ok: true };
}

export async function updateRecoveredPassword(
  formData: FormData,
): Promise<{ ok: boolean; message: string; canContinueToDashboard: boolean }> {
  const { password, confirmPassword } = readPasswordPair(formData);
  const validationError = validateNewPassword(password, confirmPassword);
  if (validationError) {
    return {
      ok: false,
      message: validationError,
      canContinueToDashboard: false,
    };
  }

  const supabase = createSupabaseServerClient();
  const { data, error } = await supabase.auth.updateUser({ password });
  if (error) {
    return {
      ok: false,
      message: 'We could not update your password. Please request a new reset link.',
      canContinueToDashboard: false,
    };
  }

  return {
    ok: true,
    message: 'Your password has been updated.',
    canContinueToDashboard: data.sessionStillValid,
  };
}

export async function changePassword(formData: FormData): Promise<never> {
  const { password, confirmPassword } = readPasswordPair(formData);
  const validationError = validateNewPassword(password, confirmPassword);
  if (validationError) {
    redirect('/dashboard/settings/security?error=' + encodeMessage(validationError));
  }

  const supabase = createSupabaseServerClient();
  const { error } = await supabase.auth.updateUser({ password });
  if (error) {
    redirect(
      '/dashboard/settings/security?error=' +
        encodeMessage('We could not update your password. Please try again.'),
    );
  }

  redirect('/dashboard/settings/security?updated=1');
}

export async function logout(): Promise<never> {
  const supabase = createSupabaseServerClient();
  await supabase.auth.signOut();
  redirect('/login');
}
