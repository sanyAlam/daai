import { SectionCard } from '@/components/console-ui';

export function ShimmerBlock({ className }: { className: string }) {
  return <div className={`animate-pulse rounded bg-panelHover ${className}`} />;
}

export function PageLoaderCard({
  title = 'Loading',
}: {
  title?: string;
}) {
  return (
    <SectionCard>
      <p className="text-sm font-medium text-muted">{title}</p>
      <div className="mt-4 space-y-3">
        <ShimmerBlock className="h-4 w-2/5" />
        <ShimmerBlock className="h-4 w-3/5" />
        <ShimmerBlock className="h-4 w-1/2" />
      </div>
    </SectionCard>
  );
}

export function MetricsCardSkeletonGrid({ cards = 7 }: { cards?: number }) {
  return (
    <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
      {Array.from({ length: cards }).map((_, index) => (
        <article
          key={index}
          className="rounded-lg border border-border bg-panel px-3 py-3 shadow-card"
        >
          <ShimmerBlock className="h-3 w-24" />
          <ShimmerBlock className="mt-2 h-7 w-12" />
        </article>
      ))}
    </div>
  );
}
