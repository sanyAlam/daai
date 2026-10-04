import type { ReactNode } from 'react';

import { StatusBadge, type Tone } from '@/components/console-ui';

function cx(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(' ');
}

const cardToneClasses: Record<Tone, string> = {
  neutral: 'border-border bg-canvas',
  brand: 'border-brand/40 bg-brand/10',
  success: 'border-success/40 bg-success/10',
  warning: 'border-warning/40 bg-warning/10',
  danger: 'border-danger/40 bg-danger/10',
  info: 'border-info/40 bg-info/10',
};

const numberToneClasses: Record<Tone, string> = {
  neutral: 'border-borderStrong bg-panel text-muted',
  brand: 'border-brand/40 bg-brand/10 text-brand',
  success: 'border-success/40 bg-success/10 text-success',
  warning: 'border-warning/40 bg-warning/10 text-warning',
  danger: 'border-danger/40 bg-danger/10 text-danger',
  info: 'border-info/40 bg-info/10 text-info',
};

export type VisualFlowStep = {
  number?: number;
  title: string;
  description: ReactNode;
  tone?: Tone;
  badge?: string;
  standout?: boolean;
};

export function FlowStepCard({
  step,
  index,
}: {
  step: VisualFlowStep;
  index: number;
}) {
  const tone = step.tone ?? 'brand';
  const number = step.number ?? index + 1;

  return (
    <article
      className={cx(
        'h-full rounded-lg border p-4 shadow-card',
        cardToneClasses[tone],
        step.standout && 'ring-1 ring-brand/50',
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <span
          className={cx(
            'flex h-8 w-8 shrink-0 items-center justify-center rounded-md border font-mono text-xs font-semibold',
            numberToneClasses[tone],
          )}
        >
          {number}
        </span>
        {step.badge ? <StatusBadge label={step.badge} tone={tone} /> : null}
      </div>
      <h3 className="mt-4 text-sm font-semibold text-text">{step.title}</h3>
      <div className="mt-2 text-xs leading-5 text-muted">{step.description}</div>
    </article>
  );
}

export function VisualFlow({
  steps,
  className,
}: {
  steps: VisualFlowStep[];
  className?: string;
}) {
  return (
    <div className={cx('grid gap-3 lg:grid-flow-col lg:auto-cols-fr', className)}>
      {steps.map((step, index) => (
        <div key={step.title} className="relative">
          <FlowStepCard step={step} index={index} />
          {index < steps.length - 1 ? (
            <>
              <span className="absolute -right-3 top-1/2 z-10 hidden -translate-y-1/2 text-sm text-subtle lg:block">
                -&gt;
              </span>
              <div className="flex justify-center py-1 text-xs text-subtle lg:hidden">v</div>
            </>
          ) : null}
        </div>
      ))}
    </div>
  );
}

export function DecisionNode({
  title,
  description,
  tone = 'warning',
  children,
}: {
  title: ReactNode;
  description?: ReactNode;
  tone?: Tone;
  children?: ReactNode;
}) {
  return (
    <article className={cx('rounded-lg border p-4 shadow-card', cardToneClasses[tone])}>
      <p className="text-xs font-medium uppercase text-subtle">Decision</p>
      <h3 className="mt-2 text-base font-semibold text-text">{title}</h3>
      {description ? <div className="mt-2 text-sm text-muted">{description}</div> : null}
      {children ? <div className="mt-3">{children}</div> : null}
    </article>
  );
}

export function PolicyCard({
  name,
  label,
  explanation,
  runtimeResult,
  tone = 'neutral',
}: {
  name: string;
  label: string;
  explanation: ReactNode;
  runtimeResult: ReactNode;
  tone?: Tone;
}) {
  return (
    <article className={cx('rounded-lg border p-4', cardToneClasses[tone])}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <code className="font-mono text-sm font-semibold text-text">{name}</code>
        <StatusBadge label={label} tone={tone} />
      </div>
      <div className="mt-3 text-sm text-muted">{explanation}</div>
      <div className="mt-4 rounded-md border border-border bg-background p-3">
        <p className="text-xs font-medium uppercase text-subtle">Runtime result</p>
        <div className="mt-2 text-sm text-text">{runtimeResult}</div>
      </div>
    </article>
  );
}

export function SplitResponsibilityPanel({
  leftTitle,
  leftItems,
  rightTitle,
  rightItems,
  callout,
}: {
  leftTitle: string;
  leftItems: string[];
  rightTitle: string;
  rightItems: string[];
  callout?: ReactNode;
}) {
  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <article className="rounded-lg border border-brand/30 bg-brand/10 p-4">
          <h3 className="text-base font-semibold text-text">{leftTitle}</h3>
          <ul className="mt-4 space-y-2">
            {leftItems.map((item) => (
              <li key={item} className="flex gap-2 text-sm text-muted">
                <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-brand" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </article>
        <article className="rounded-lg border border-border bg-canvas p-4">
          <h3 className="text-base font-semibold text-text">{rightTitle}</h3>
          <ul className="mt-4 space-y-2">
            {rightItems.map((item) => (
              <li key={item} className="flex gap-2 text-sm text-muted">
                <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-muted" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </article>
      </div>
      {callout ? (
        <div className="rounded-lg border border-warning/40 bg-warning/10 p-4 text-sm text-text">
          {callout}
        </div>
      ) : null}
    </div>
  );
}

export type TimelineItem = {
  title: string;
  description: ReactNode;
  tone?: Tone;
};

export function Timeline({ items }: { items: TimelineItem[] }) {
  return (
    <div className="space-y-0">
      {items.map((item, index) => {
        const tone = item.tone ?? 'brand';
        return (
          <div key={item.title} className="grid grid-cols-[2rem_1fr] gap-3">
            <div className="flex flex-col items-center">
              <span
                className={cx(
                  'flex h-8 w-8 items-center justify-center rounded-full border font-mono text-xs font-semibold',
                  numberToneClasses[tone],
                )}
              >
                {index + 1}
              </span>
              {index < items.length - 1 ? (
                <span className="h-full min-h-8 w-px bg-border" />
              ) : null}
            </div>
            <article className="mb-3 rounded-lg border border-border bg-canvas p-4">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-sm font-semibold text-text">{item.title}</h3>
                <StatusBadge label={tone} tone={tone} />
              </div>
              <div className="mt-2 text-sm text-muted">{item.description}</div>
            </article>
          </div>
        );
      })}
    </div>
  );
}

export function EmptyIllustrationCard() {
  return (
    <div
      className="rounded-[24px] border border-borderStrong bg-background p-4 shadow-[0_18px_45px_rgba(0,0,0,0.24)]"
      style={{
        backgroundImage: 'radial-gradient(circle, rgba(40,50,45,0.9) 1.4px, transparent 1.4px)',
        backgroundSize: '22px 22px',
      }}
    >
      <div className="grid items-center gap-3 md:grid-cols-[1fr_auto_1fr_auto_1fr]">
        <div className="rounded-[18px] border border-border bg-panel px-4 py-3 shadow-card">
          <p className="text-xs font-semibold uppercase text-muted">Agent proposes</p>
          <p className="mt-2 font-mono text-xs text-text">client.intercept()</p>
        </div>
        <div className="mx-auto text-sm font-semibold text-subtle md:rotate-0 rotate-90">
          -&gt;
        </div>
        <div className="rounded-[20px] border border-brand/50 bg-panel px-4 py-3 shadow-[0_12px_32px_rgba(62,207,142,0.12)]">
          <p className="text-xs font-semibold uppercase text-brand">DAAI decides</p>
          <p className="mt-2 text-xs text-muted">policy before execution</p>
        </div>
        <div className="mx-auto text-sm font-semibold text-subtle md:rotate-0 rotate-90">
          -&gt;
        </div>
        <div className="rounded-[18px] border border-border bg-panel px-4 py-3 shadow-card">
          <p className="text-xs font-semibold uppercase text-muted">Receipt recorded</p>
          <p className="mt-2 text-xs text-muted">proposal + decision + result</p>
        </div>
      </div>
    </div>
  );
}
