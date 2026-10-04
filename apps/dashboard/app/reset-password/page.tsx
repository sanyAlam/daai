import { ResetPasswordForm } from '@/app/reset-password/reset-password-form';
import { createSupabaseServerClient } from '@/lib/supabase/server';

export default async function ResetPasswordPage() {
  const supabase = createSupabaseServerClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  return <ResetPasswordForm hasSession={Boolean(session)} />;
}
