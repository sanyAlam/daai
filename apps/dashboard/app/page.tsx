import type { Metadata } from 'next';

import { LandingPage } from '@/components/landing-page';

export const metadata: Metadata = {
  title: 'DAAI Console | Auditable history for registered agent actions',
  description:
    'Log registered agent action proposals, add approval gates, track execution, and keep client-ready receipts with a simple Python SDK.',
};

export default function RootLandingPage() {
  return <LandingPage />;
}
