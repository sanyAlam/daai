'use client';

import { CopyButton } from '@/components/copy-button';

export function CodeBlockWithCopy({
  code,
  label = 'Copy',
  title = 'JSON',
}: {
  code: string;
  label?: string;
  title?: string;
}) {
  return (
    <div className="mt-3 overflow-hidden rounded-lg border border-border bg-canvas">
      <div className="flex items-center justify-between gap-3 border-b border-border bg-panel px-3 py-2">
        <span className="text-xs font-medium text-muted">{title}</span>
        <CopyButton value={code} label={label} />
      </div>
      <pre className="overflow-x-auto p-4 text-xs leading-6 text-text">
        <code>{code}</code>
      </pre>
    </div>
  );
}
