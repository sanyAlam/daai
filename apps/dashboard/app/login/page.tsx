import Link from 'next/link';
import { redirect } from 'next/navigation';

import { loginWithPassword } from '@/app/auth-actions';
import { FormSubmitButton } from '@/components/form-submit-button';
import { buttonStyles, fieldStyles, Notice, SectionCard } from '@/components/console-ui';
import { createSupabaseServerClient } from '@/lib/supabase/server';

export default async function LoginPage(
  props: {
    searchParams?: Promise<{ error?: string; message?: string }>;
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

  const errorMessage = searchParams?.error;
  const infoMessage = searchParams?.message;

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
        <h1 className="text-2xl font-semibold text-text">Log in</h1>
        <p className="mt-2 text-sm text-muted">Use your Supabase email/password credentials.</p>

        {errorMessage ? (
          <Notice tone="danger" className="mt-4">
            {errorMessage}
          </Notice>
        ) : null}

        {infoMessage ? (
          <Notice tone="info" className="mt-4">
            {infoMessage}
          </Notice>
        ) : null}

        <form action={loginWithPassword} className="mt-5 space-y-3">
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

          <div>
            <div className="flex items-center justify-between gap-3">
              <label htmlFor="password" className="block text-sm font-medium text-text">
                Password
              </label>
              <Link
                href="/forgot-password"
                className="text-xs font-medium text-brand hover:text-brand/80"
              >
                Forgot password?
              </Link>
            </div>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              className={`mt-1 ${fieldStyles}`}
            />
          </div>

          <FormSubmitButton
            label="Log in"
            loadingLabel="Logging in..."
            className={`w-full ${buttonStyles.primary}`}
          />
        </form>

        <p className="mt-4 text-sm text-muted">
          No account yet?{' '}
          <Link href="/signup" className="font-medium text-brand hover:text-brand/80">
            Sign up
          </Link>
        </p>
      </SectionCard>
    </section>
  );
}
