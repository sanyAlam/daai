import { ReactNode } from 'react';
import Link from 'next/link';

export type Tone = 'neutral' | 'brand' | 'success' | 'warning' | 'danger' | 'info';

function cx(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(' ');
}

function humanize(value: string): string {
  return value.replaceAll('_', ' ');
}

const toneClasses: Record<Tone, string> = {
  neutral: 'border-borderStrong bg-panelHover text-muted',
  brand: 'border-brand/40 bg-brand/10 text-brand',
  success: 'border-success/40 bg-success/10 text-success',
  warning: 'border-warning/40 bg-warning/10 text-warning',
  danger: 'border-danger/40 bg-danger/10 text-danger',
  info: 'border-info/40 bg-info/10 text-info',
};

export const buttonStyles = {
  primary:
    'inline-flex items-center justify-center rounded-md border border-brand/70 bg-brand px-4 py-2 text-sm font-semibold text-[#062014] transition hover:bg-brand/90 disabled:cursor-not-allowed disabled:border-border disabled:bg-panelHover disabled:text-subtle',
  secondary:
    'inline-flex items-center justify-center rounded-md border border-borderStrong bg-panel px-3 py-2 text-sm font-medium text-text transition hover:border-brand/50 hover:bg-panelHover disabled:cursor-not-allowed disabled:border-border disabled:bg-canvas disabled:text-subtle',
  subtle:
    'inline-flex items-center justify-center rounded-md border border-border bg-canvas px-3 py-2 text-sm font-medium text-muted transition hover:border-borderStrong hover:bg-panelHover hover:text-text disabled:cursor-not-allowed disabled:bg-canvas disabled:text-subtle',
  danger:
    'inline-flex items-center justify-center rounded-md border border-danger/50 bg-danger/10 px-3 py-2 text-sm font-medium text-danger transition hover:bg-danger/20 disabled:cursor-not-allowed disabled:border-border disabled:bg-canvas disabled:text-subtle',
};

export const fieldStyles =
  'w-full rounded-md border border-border bg-canvas px-3 py-2 text-sm text-text transition placeholder:text-subtle focus:border-brand focus:outline-none disabled:cursor-not-allowed disabled:bg-panel disabled:text-subtle';

export const selectStyles = fieldStyles;

export const textareaStyles = fieldStyles;

export function PageHeader({
  title,
  description,
  eyebrow,
  actions,
  meta,
}: {
  title: string;
  description?: ReactNode;
  eyebrow?: string;
  actions?: ReactNode;
  meta?: ReactNode;
}) {
  return (
    <header className="rounded-lg border border-border bg-panel p-5 shadow-card shadow-inset">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          {eyebrow ? (
            <p className="mb-2 text-xs font-medium uppercase text-brand">{eyebrow}</p>
          ) : null}
          <h1 className="break-words text-2xl font-semibold text-text">{title}</h1>
          {description ? <p className="mt-2 max-w-3xl text-sm text-muted">{description}</p> : null}
          {meta ? <div className="mt-3 text-sm text-muted">{meta}</div> : null}
        </div>
        {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
      </div>
    </header>
  );
}

export function SectionCard({
  title,
  description,
  actions,
  children,
  className,
}: {
  title?: string;
  description?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <article className={cx('rounded-lg border border-border bg-panel p-5 shadow-card', className)}>
      {title || description || actions ? (
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div>
            {title ? <h2 className="text-lg font-semibold text-text">{title}</h2> : null}
            {description ? <p className="mt-1 text-sm text-muted">{description}</p> : null}
          </div>
          {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
        </div>
      ) : null}
      {children}
    </article>
  );
}

export function MetricCard({
  label,
  value,
  href,
  linkLabel,
  description,
  tone = 'neutral',
  compact = false,
}: {
  label: string;
  value: ReactNode;
  href?: string;
  linkLabel?: string;
  description?: ReactNode;
  tone?: Tone;
  compact?: boolean;
}) {
  const metricToneClasses: Record<Tone, string> = {
    neutral: 'border-border bg-panel',
    brand: 'border-brand/30 bg-brand/10',
    success: 'border-success/30 bg-success/10',
    warning: 'border-warning/30 bg-warning/10',
    danger: 'border-danger/30 bg-danger/10',
    info: 'border-info/30 bg-info/10',
  };
  const valueToneClasses: Record<Tone, string> = {
    neutral: 'text-text',
    brand: 'text-brand',
    success: 'text-success',
    warning: 'text-warning',
    danger: 'text-danger',
    info: 'text-info',
  };
  const content = (
    <>
      <p className="text-xs font-medium uppercase text-muted">{label}</p>
      <p className={cx('mt-2 font-semibold', compact ? 'text-xl' : 'text-2xl', valueToneClasses[tone])}>
        {value}
      </p>
      {description ? <p className="mt-2 text-sm text-muted">{description}</p> : null}
      {linkLabel ? <p className="mt-3 text-sm font-medium text-brand">{linkLabel}</p> : null}
    </>
  );

  if (href) {
    return (
      <Link
        href={href}
        className={cx(
          'block rounded-lg border p-5 shadow-card transition hover:border-brand/50 hover:bg-panelHover',
          metricToneClasses[tone],
        )}
      >
        {content}
      </Link>
    );
  }

  return (
    <article className={cx('rounded-lg border p-5 shadow-card', metricToneClasses[tone])}>
      {content}
    </article>
  );
}

export function StatusBadge({
  label,
  tone = 'neutral',
  mono = false,
}: {
  label: string;
  tone?: Tone;
  mono?: boolean;
}) {
  return (
    <span
      className={cx(
        'inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium',
        toneClasses[tone],
        mono && 'font-mono',
      )}
    >
      {label}
    </span>
  );
}

export function RiskBadge({ value }: { value: string | null | undefined }) {
  const normalized = value ?? 'unknown';
  const tone: Tone =
    normalized === 'critical'
      ? 'danger'
      : normalized === 'high'
        ? 'warning'
        : 'neutral';
  return <StatusBadge label={humanize(normalized)} tone={tone} />;
}

export function PolicyBadge({ value }: { value: string | null | undefined }) {
  const normalized = value ?? 'unknown';
  const tone: Tone =
    normalized === 'always_block'
      ? 'danger'
      : normalized === 'always_allow'
        ? 'success'
        : normalized.includes('approval')
          ? 'warning'
          : 'neutral';
  return <StatusBadge label={humanize(normalized)} tone={tone} mono />;
}

export function KeyValueGrid({
  items,
}: {
  items: Array<{
    label: string;
    value: ReactNode;
    mono?: boolean;
  }>;
}) {
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-canvas">
      {items.map((item) => (
        <div
          key={item.label}
          className="grid gap-2 border-t border-border px-4 py-3 text-sm first:border-t-0 sm:grid-cols-3"
        >
          <p className="font-medium text-text">{item.label}</p>
          <div
            className={cx(
              'min-w-0 break-words text-muted sm:col-span-2',
              item.mono && 'font-mono text-xs',
            )}
          >
            {item.value}
          </div>
        </div>
      ))}
    </div>
  );
}

export function TableShell({ children }: { children: ReactNode }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-canvas">
      {children}
    </div>
  );
}

export function Notice({
  children,
  tone = 'neutral',
  className,
}: {
  children: ReactNode;
  tone?: Tone;
  className?: string;
}) {
  return (
    <div className={cx('rounded-md border px-3 py-2 text-sm', toneClasses[tone], className)}>
      {children}
    </div>
  );
}
