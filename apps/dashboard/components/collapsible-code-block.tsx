'use client';

import { useState } from 'react';

import { CopyButton } from '@/components/copy-button';

export function CollapsibleCodeBlock({
  code,
  defaultOpen = false,
  label = 'Copy',
  title = 'Code',
}: {
  code: string;
  defaultOpen?: boolean;
  label?: string;
  title?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="mt-3 overflow-hidden rounded-lg border border-border bg-canvas">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-panel px-3 py-2">
        <span className="text-xs font-medium text-muted">{title}</span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setOpen((current) => !current)}
            className="rounded-md border border-border bg-canvas px-2.5 py-1.5 text-xs font-medium text-muted transition hover:border-borderStrong hover:bg-panelHover hover:text-text"
          >
            {open ? 'Hide code' : 'Show code'}
          </button>
          <CopyButton value={code} label={label} />
        </div>
      </div>
      {open ? (
        <pre className="overflow-x-auto p-4 text-xs leading-6 text-text">
          <code>{code}</code>
        </pre>
      ) : null}
    </div>
  );
}
