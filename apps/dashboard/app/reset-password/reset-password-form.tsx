'use client';

import { FormEvent, useEffect, useState } from 'react';
import Link from 'next/link';

import {
  establishPasswordRecoverySession,
  updateRecoveredPassword,
} from '@/app/auth-actions';
import { buttonStyles, fieldStyles, Notice, SectionCard } from '@/components/console-ui';

type Stage = 'checking' | 'ready' | 'invalid' | 'success';

function parseRecoveryParams(): {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
} | null {
  const hash = window.location.hash.startsWith('#')
    ? window.location.hash.slice(1)
    : window.location.hash;
  const params = new URLSearchParams(hash);
  const accessToken = params.get('access_token') ?? '';
  const refreshToken = params.get('refresh_token') ?? '';
  const expiresIn = Number(params.get('expires_in') ?? '');

  if (!accessToken || !refreshToken || !Number.isFinite(expiresIn)) {
    return null;
  }

  return { accessToken, refreshToken, expiresIn };
}

function validatePassword(password: string, confirmPassword: string): string | null {
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

export function ResetPasswordForm({ hasSession }: { hasSession: boolean }) {
  const [stage, setStage] = useState<Stage>(hasSession ? 'ready' : 'checking');
  const [message, setMessage] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [isPreparingSession, setIsPreparingSession] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [canContinueToDashboard, setCanContinueToDashboard] = useState(hasSession);

  useEffect(() => {
    const recoveryParams = parseRecoveryParams();
    if (!recoveryParams) {
      if (hasSession) {
        return;
      }
      setStage('invalid');
      return;
    }

    setStage('checking');
    setIsPreparingSession(true);
    establishPasswordRecoverySession(recoveryParams)
      .then((result) => {
        window.history.replaceState(null, '', '/reset-password');
        if (!result.ok) {
          setMessage(result.message ?? 'This reset link is invalid or expired.');
          setStage('invalid');
          return;
        }
        setMessage(null);
        setStage('ready');
        setCanContinueToDashboard(true);
      })
      .catch(() => {
        setMessage('This reset link is invalid or expired.');
        setStage('invalid');
      })
      .finally(() => {
        setIsPreparingSession(false);
      });
  }, [hasSession]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    setPasswordError(null);

    const form = event.currentTarget;
    const formData = new FormData(form);
    const password = String(formData.get('password') ?? '');
    const confirmPassword = String(formData.get('confirm_password') ?? '');
    const validationError = validatePassword(password, confirmPassword);
    if (validationError) {
      setPasswordError(validationError);
      return;
    }

    setIsSubmitting(true);
    const result = await updateRecoveredPassword(formData);
    setIsSubmitting(false);

    if (!result.ok) {
      setMessage(result.message);
      return;
    }

    form.reset();
    setMessage(result.message);
    setCanContinueToDashboard(result.canContinueToDashboard);
    setStage('success');
  }

  return (
    <section className="w-full max-w-md space-y-4">
      <SectionCard>
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-md border border-brand/40 bg-brand/10 text-sm font-semibold text-brand">
            D
          </div>
          <div>
            <p className="text-sm font-semibold text-text">DAAI Console</p>
            <p className="text-xs text-subtle">Cooperative action governance</p>
          </div>
        </div>

        <h1 className="text-2xl font-semibold text-text">Choose a new password</h1>

        {stage === 'checking' || isPreparingSession ? (
          <p className="mt-4 text-sm text-muted">Checking your reset link...</p>
        ) : null}

        {stage === 'invalid' ? (
          <div className="mt-4 space-y-4">
            <Notice tone="warning">
              {message ??
                'This reset link is invalid or expired. Please request a new password reset link.'}
            </Notice>
            <Link href="/forgot-password" className={buttonStyles.secondary}>
              Request a new reset link
            </Link>
          </div>
        ) : null}

        {stage === 'success' ? (
          <div className="mt-4 space-y-4">
            <Notice tone="success">{message ?? 'Your password has been updated.'}</Notice>
            <Link
              href={canContinueToDashboard ? '/home' : '/login'}
              className={buttonStyles.primary}
            >
              {canContinueToDashboard ? 'Continue to dashboard' : 'Back to login'}
            </Link>
          </div>
        ) : null}

        {stage === 'ready' ? (
          <>
            {message ? (
              <Notice tone="danger" className="mt-4">
                {message}
              </Notice>
            ) : null}

            <form onSubmit={handleSubmit} className="mt-5 space-y-3">
              <div>
                <label htmlFor="password" className="block text-sm font-medium text-text">
                  New password
                </label>
                <input
                  id="password"
                  name="password"
                  type="password"
                  autoComplete="new-password"
                  minLength={8}
                  required
                  aria-describedby={passwordError ? 'password-error' : undefined}
                  className={`mt-1 ${fieldStyles}`}
                />
              </div>

              <div>
                <label
                  htmlFor="confirm_password"
                  className="block text-sm font-medium text-text"
                >
                  Confirm password
                </label>
                <input
                  id="confirm_password"
                  name="confirm_password"
                  type="password"
                  autoComplete="new-password"
                  minLength={8}
                  required
                  aria-describedby={passwordError ? 'password-error' : undefined}
                  className={`mt-1 ${fieldStyles}`}
                />
                {passwordError ? (
                  <p id="password-error" className="mt-2 text-sm text-danger">
                    {passwordError}
                  </p>
                ) : null}
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className={`w-full ${buttonStyles.primary}`}
              >
                {isSubmitting ? 'Updating password...' : 'Update password'}
              </button>
            </form>
          </>
        ) : null}
      </SectionCard>
    </section>
  );
}
