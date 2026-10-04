import type { Metadata } from 'next';
import { headers } from 'next/headers';

import { AppShell } from '@/components/app-shell';
import { createSupabaseServerClient } from '@/lib/supabase/server';

import '@xyflow/react/dist/style.css';
import './globals.css';

export const metadata: Metadata = {
  title: 'DAAI Console Dashboard',
  description: 'Visibility into governed agent action lifecycles',
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const supabase = createSupabaseServerClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  const pathname = (await headers()).get('x-daai-pathname');
  const isPublicPage =
    pathname === '/' ||
    pathname === '/documentation' ||
    (pathname === '/dashboard/documentation' && !user);

  return (
    <html lang="en">
      <body className="min-h-screen bg-background text-text antialiased">
        {isPublicPage ? (
          children
        ) : (
          <AppShell userEmail={user ? user.email ?? 'Signed in' : null}>
            {children}
          </AppShell>
        )}
      </body>
    </html>
  );
}
