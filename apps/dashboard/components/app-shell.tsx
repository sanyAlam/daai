import { ReactNode } from 'react';

import { Sidebar } from '@/components/sidebar';
import { TopNav } from '@/components/top-nav';

function isConfiguredAdminEmail(email: string | null): boolean {
  const normalized = email?.trim().toLowerCase();
  if (!normalized) {
    return false;
  }
  return (process.env.DAAI_ADMIN_EMAILS ?? '')
    .split(',')
    .map((candidate) => candidate.trim().toLowerCase())
    .filter(Boolean)
    .includes(normalized);
}

export function AppShell({
  children,
  userEmail,
}: {
  children: ReactNode;
  userEmail: string | null;
}) {
  if (!userEmail) {
    return (
      <div className="min-h-screen bg-background text-text">
        <div className="mx-auto flex min-h-screen w-full max-w-7xl flex-col px-4 py-8 sm:px-6 lg:px-8">
          <main className="flex flex-1 items-start justify-center pt-6 sm:pt-12">
            {children}
          </main>
        </div>
      </div>
    );
  }

  const showAdmin = isConfiguredAdminEmail(userEmail);

  return (
    <div className="min-h-screen bg-background text-text">
      <Sidebar userEmail={userEmail} showAdmin={showAdmin} />
      <div className="min-h-screen lg:pl-64">
        <TopNav userEmail={userEmail} showAdmin={showAdmin} />
        <main className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
          {children}
        </main>
      </div>
    </div>
  );
}
