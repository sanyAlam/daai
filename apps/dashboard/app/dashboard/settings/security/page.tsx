import { changePassword } from '@/app/auth-actions';
import { Breadcrumbs } from '@/components/breadcrumbs';
import {
  buttonStyles,
  fieldStyles,
  Notice,
  PageHeader,
  SectionCard,
} from '@/components/console-ui';
import { FormSubmitButton } from '@/components/form-submit-button';

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

export default async function SecuritySettingsPage(
  props: {
    searchParams?: Promise<{ error?: string; updated?: string }>;
  }
) {
  const searchParams = await props.searchParams;
  const errorMessage = decodeMessage(searchParams?.error);

  return (
    <section className="space-y-5">
      <Breadcrumbs
        items={[
          { label: 'Home', href: '/home' },
          { label: 'Security' },
        ]}
      />

      <PageHeader title="Security" description="Manage password access for your DAAI account." />

      {searchParams?.updated === '1' ? (
        <Notice tone="success">Password updated successfully.</Notice>
      ) : null}

      {errorMessage ? <Notice tone="danger">{errorMessage}</Notice> : null}

      <SectionCard
        title="Change password"
        description="Choose a new password for your dashboard login."
      >
        <form action={changePassword} className="mt-4 max-w-md space-y-3">
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
              className={`mt-1 ${fieldStyles}`}
            />
          </div>

          <div>
            <label htmlFor="confirm_password" className="block text-sm font-medium text-text">
              Confirm password
            </label>
            <input
              id="confirm_password"
              name="confirm_password"
              type="password"
              autoComplete="new-password"
              minLength={8}
              required
              className={`mt-1 ${fieldStyles}`}
            />
          </div>

          <FormSubmitButton
            label="Update password"
            loadingLabel="Updating password..."
            className={buttonStyles.primary}
          />
        </form>
      </SectionCard>
    </section>
  );
}
