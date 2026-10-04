import Link from 'next/link';

import { logout } from '@/app/auth-actions';
import { buttonStyles } from '@/components/console-ui';
import { MobileDashboardNav } from '@/components/sidebar';

export function TopNav({
  userEmail,
  showAdmin = false,
}: {
  userEmail: string | null;
  showAdmin?: boolean;
}) {
  return (
    <header className="sticky top-0 z-20 border-b border-border bg-background/90 backdrop-blur">
      <div className="px-4 py-3 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between gap-3">
          <Link href="/home" className="flex items-center gap-3 lg:hidden">
            <div className="flex h-8 w-8 items-center justify-center rounded-md border border-brand/40 bg-brand/10 text-sm font-semibold text-brand">
              D
            </div>
            <span className="text-sm font-semibold text-text">DAAI Console</span>
          </Link>

          <div className="hidden min-w-0 lg:block">
            <p className="text-sm font-medium text-text">Dashboard</p>
            <p className="truncate text-xs text-subtle">{userEmail ?? 'Signed in'}</p>
          </div>

          <form action={logout} className="ml-auto">
            <button type="submit" className={buttonStyles.subtle}>
              Log out
            </button>
          </form>
        </div>
        <MobileDashboardNav showAdmin={showAdmin} />
      </div>
    </header>
  );
}
