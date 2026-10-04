import type { Metadata } from 'next';

import DocumentationPage from '@/app/dashboard/documentation/page';

export const metadata: Metadata = {
  title: 'Documentation | DAAI Console',
  description: 'Quickstart and developer documentation for DAAI Console.',
};

export default async function PublicDocumentationPage() {
  return (
    <main className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      <DocumentationPage />
    </main>
  );
}
