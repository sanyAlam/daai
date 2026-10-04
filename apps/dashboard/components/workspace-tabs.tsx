'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

export function WorkspaceTabs({ workspaceId }: { workspaceId: string }) {
  const pathname = usePathname();
  const runsHref = `/workspaces/${workspaceId}/runs`;
  const links = [
    { key: 'overview', href: `/workspaces/${workspaceId}`, label: 'Overview' },
    { key: 'setup', href: `/workspaces/${workspaceId}/setup`, label: 'Setup' },
    { key: 'actions', href: `/workspaces/${workspaceId}/actions`, label: 'Actions' },
    { key: 'runs', href: runsHref, label: 'Runs' },
    { key: 'receipts', href: `/workspaces/${workspaceId}/receipts`, label: 'Receipts' },
    { key: 'documentation', href: '/dashboard/documentation', label: 'Documentation' },
  ];

  return (
    <div className="rounded-lg border border-border bg-canvas p-2 shadow-card">
      <div className="flex flex-wrap gap-2">
        {links.map((link) => {
          const isActive =
            (link.key === 'overview' && pathname === link.href) ||
            (link.key === 'setup' && pathname.startsWith(link.href)) ||
            (link.key === 'actions' && pathname.startsWith(link.href)) ||
            (link.key === 'runs' && pathname.startsWith(runsHref)) ||
            (link.key === 'receipts' && pathname.startsWith(link.href)) ||
            (link.key === 'documentation' && pathname.startsWith('/dashboard/documentation'));

          return (
            <Link
              key={link.key}
              href={link.href}
              className={`rounded-md border px-3 py-2 text-sm font-medium transition ${
                isActive
                  ? 'border-brand/40 bg-brand/10 text-brand'
                  : 'border-transparent text-muted hover:border-border hover:bg-panelHover hover:text-text'
              }`}
            >
              {link.label}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
