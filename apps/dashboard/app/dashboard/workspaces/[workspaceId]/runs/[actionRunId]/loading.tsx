export default function RunDetailLoading() {
  return (
    <div className="rounded-lg border border-border bg-panel p-6 shadow-card">
      <p className="text-sm font-medium text-muted">Loading action run detail</p>
      <div className="mt-4 space-y-3">
        <div className="h-4 w-2/5 animate-pulse rounded bg-panelHover" />
        <div className="h-4 w-3/5 animate-pulse rounded bg-panelHover" />
        <div className="h-4 w-1/2 animate-pulse rounded bg-panelHover" />
      </div>
    </div>
  );
}
