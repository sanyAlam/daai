import Link from 'next/link';
import { redirect } from 'next/navigation';

import { requestPasswordReset } from '@/app/auth-actions';
import { FormSubmitButton } from '@/components/form-submit-button';
import { buttonStyles, fieldStyles, Notice, SectionCard } from '@/components/console-ui';
import { createSupabaseServerClient } from '@/lib/supabase/server';

function decodeMessage(value: string | undefined): string | null {
  if (!value) {
    return null;
  }
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

export default async function ForgotPasswordPage(
  props: {
    searchParams?: Promise<{ error?: string; sent?: string }>;
  }
) {
  const searchParams = await props.searchParams;
  const supabase = createSupabaseServerClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (user) {
    redirect('/home');
  }

  const errorMessage = decodeMessage(searchParams?.error);

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

        <h1 className="text-2xl font-semibold text-text">Reset your password</h1>
        <p className="mt-2 text-sm text-muted">
          Enter the email address linked to your DAAI account.
        </p>

        {searchParams?.sent === '1' ? (
          <Notice tone="info" className="mt-4">
            If an account exists for this email, we&apos;ll send a password reset link.
          </Notice>
        ) : null}

        {errorMessage ? (
          <Notice tone="danger" className="mt-4">
            {errorMessage}
          </Notice>
        ) : null}

        <form action={requestPasswordReset} className="mt-5 space-y-3">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-text">
              Email
            </label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              required
              className={`mt-1 ${fieldStyles}`}
            />
          </div>

          <FormSubmitButton
            label="Send reset link"
            loadingLabel="Sending reset link..."
            className={`w-full ${buttonStyles.primary}`}
          />
        </form>

        <p className="mt-4 text-sm text-muted">
          <Link href="/login" className="font-medium text-brand hover:text-brand/80">
            Back to login
          </Link>
        </p>
      </SectionCard>
    </section>
  );
}
