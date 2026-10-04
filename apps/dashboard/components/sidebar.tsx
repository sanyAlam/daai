'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

function isActive(pathname: string, key: string, href: string | null): boolean {
  if (key === 'workspaces') {
    return pathname === '/home' || pathname === '/dashboard' || pathname.startsWith('/workspaces');
  }
  if (key === 'documentation') {
    return pathname.startsWith('/dashboard/documentation');
  }
  if (key === 'account') {
    return pathname.startsWith('/account');
  }
  if (key === 'security') {
    return pathname.startsWith('/dashboard/settings/security');
  }
  if (key === 'admin') {
    return pathname.startsWith('/admin');
  }
  if (!href) {
    return false;
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

function useNavItems(showAdmin: boolean) {
  const pathname = usePathname();
  const items = [
    { key: 'workspaces', label: 'Workspaces', href: '/home', disabled: false },
    {
      key: 'documentation',
      label: 'Documentation',
      href: '/dashboard/documentation',
      disabled: false,
    },
    { key: 'account', label: 'Account', href: '/account', disabled: false },
    {
      key: 'security',
      label: 'Security',
      href: '/dashboard/settings/security',
      disabled: false,
    },
  ];

  if (showAdmin) {
    items.push({ key: 'admin', label: 'Admin', href: '/admin', disabled: false });
  }

  return {
    pathname,
    items,
  };
}

function ProductMark() {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-9 w-9 items-center justify-center rounded-md border border-brand/40 bg-brand/10 text-sm font-semibold text-brand">
        D
      </div>
      <div>
        <p className="text-sm font-semibold text-text">DAAI Console</p>
        <p className="text-xs text-subtle">Governed actions</p>
      </div>
    </div>
  );
}

export function Sidebar({
  userEmail,
  showAdmin = false,
}: {
  userEmail: string | null;
  showAdmin?: boolean;
}) {
  const { pathname, items } = useNavItems(showAdmin);

  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-border bg-canvas lg:flex lg:flex-col">
      <div className="border-b border-border px-5 py-5">
        <Link href="/home" className="block rounded-md focus:outline-none">
          <ProductMark />
        </Link>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-4" aria-label="Dashboard">
        {items.map((item) => {
          const active = isActive(pathname, item.key, item.href);
          if (item.disabled || !item.href) {
            return (
              <span
                key={item.key}
                aria-disabled="true"
                className="block cursor-not-allowed rounded-md px-3 py-2 text-sm font-medium text-subtle"
                title="Open a workspace first"
              >
                {item.label}
              </span>
            );
          }

          return (
            <Link
              key={item.key}
              href={item.href}
              className={`block rounded-md px-3 py-2 text-sm font-medium transition ${
                active
                  ? 'border border-brand/30 bg-brand/10 text-brand'
                  : 'text-muted hover:bg-panelHover hover:text-text'
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-border px-5 py-4">
        <p className="truncate text-xs text-subtle">Signed in</p>
        <p className="mt-1 truncate text-sm text-muted">{userEmail ?? 'Dashboard user'}</p>
      </div>
    </aside>
  );
}

export function MobileDashboardNav({ showAdmin = false }: { showAdmin?: boolean }) {
  const { pathname, items } = useNavItems(showAdmin);

  return (
    <nav
      className="-mx-4 mt-3 flex gap-2 overflow-x-auto px-4 pb-1 sm:-mx-6 sm:px-6 lg:hidden"
      aria-label="Dashboard"
    >
      {items.map((item) => {
        const active = isActive(pathname, item.key, item.href);
        if (item.disabled || !item.href) {
          return (
            <span
              key={item.key}
              aria-disabled="true"
              className="shrink-0 cursor-not-allowed rounded-md border border-border bg-canvas px-3 py-2 text-sm font-medium text-subtle"
            >
              {item.label}
            </span>
          );
        }

        return (
          <Link
            key={item.key}
            href={item.href}
            className={`shrink-0 rounded-md border px-3 py-2 text-sm font-medium transition ${
              active
                ? 'border-brand/40 bg-brand/10 text-brand'
                : 'border-border bg-canvas text-muted hover:border-borderStrong hover:bg-panelHover hover:text-text'
            }`}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
