import Link from 'next/link';

import { buttonStyles, Notice, SectionCard } from '@/components/console-ui';

export function ErrorState({ title, message }: { title: string; message: string }) {
  return (
    <SectionCard>
      <h2 className="text-base font-semibold text-text">{title}</h2>
      <Notice tone="danger" className="mt-3">
        {message}
      </Notice>
    </SectionCard>
  );
}

export function EmptyState({ title, message }: { title: string; message: string }) {
  return (
    <div className="rounded-lg border border-border bg-canvas p-6 text-center">
      <h2 className="text-base font-semibold text-text">{title}</h2>
      <p className="mt-2 text-sm text-muted">{message}</p>
    </div>
  );
}

export function LoadingState({ title = 'Loading' }: { title?: string }) {
  return (
    <SectionCard>
      <p className="text-sm font-medium text-muted">{title}</p>
      <div className="mt-4 space-y-3">
        <div className="h-4 w-2/5 animate-pulse rounded bg-panelHover" />
        <div className="h-4 w-3/5 animate-pulse rounded bg-panelHover" />
        <div className="h-4 w-1/2 animate-pulse rounded bg-panelHover" />
      </div>
    </SectionCard>
  );
}

export function NotFoundState({ title, message }: { title: string; message: string }) {
  return (
    <div className="rounded-lg border border-border bg-panel p-6 shadow-card">
      <h2 className="text-lg font-semibold text-text">{title}</h2>
      <p className="mt-2 text-sm text-muted">{message}</p>
      <Link
        href="/home"
        className={`mt-4 ${buttonStyles.secondary}`}
      >
        Back to Home
      </Link>
    </div>
  );
}
