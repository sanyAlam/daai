import Link from 'next/link';
import type { ReactNode } from 'react';

import { submitPricingInterest } from '@/app/pricing-interest-actions';

type StatusTone = 'neutral' | 'pending' | 'success' | 'danger' | 'policy';

const DEFAULT_DASHBOARD_BASE_URL = 'http://localhost:3000';
const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000';

function normalizeBaseUrl(value: string | undefined, fallback: string): string {
  const trimmed = value?.trim();
  const baseUrl = trimmed || fallback;
  return baseUrl.endsWith('/') ? baseUrl.slice(0, -1) : baseUrl;
}

function dashboardHref(path = ''): string {
  return `${normalizeBaseUrl(process.env.DAAI_DASHBOARD_BASE_URL, DEFAULT_DASHBOARD_BASE_URL)}${path}`;
}

const statusToneClasses: Record<StatusTone, string> = {
  neutral: 'border-white/[0.12] bg-white/[0.04] text-zinc-300',
  pending: 'border-amber-300/35 bg-amber-300/10 text-amber-200',
  success: 'border-emerald-300/35 bg-emerald-300/10 text-emerald-200',
  danger: 'border-red-300/35 bg-red-300/10 text-red-200',
  policy: 'border-indigo-300/35 bg-indigo-300/10 text-indigo-200',
};

const navLinks = [
  { label: 'Product', href: '#product' },
  { label: 'How it works', href: '#how-it-works' },
  { label: 'Documentation', href: '/documentation' },
  { label: 'SDK', href: '#sdk' },
  { label: 'Pricing', href: '#pricing' },
];

const lifecycleSteps = [
  {
    title: 'Register a risky action',
    copy: 'Define the action your agent may propose, such as sending an invoice reminder or marking an invoice paid.',
    tone: 'policy' as const,
  },
  {
    title: 'Add the Python SDK gate',
    copy: 'Place DAAI before the real business function so the action can be logged, evaluated, and controlled.',
    tone: 'policy' as const,
  },
  {
    title: 'DAAI records the proposal',
    copy: 'DAAI creates an action run with input details, source context, reasoning, policy decision, and status.',
    tone: 'neutral' as const,
  },
  {
    title: 'Approve, block, or allow',
    copy: 'Low-risk actions can be logged automatically. Risky actions can require approval before execution.',
    tone: 'pending' as const,
  },
  {
    title: 'Track execution and receipts',
    copy: 'After execution, report the result back to DAAI and keep a clear receipt for client review.',
    tone: 'success' as const,
  },
];

const sdkCode = `import os
from daai import DaaiClient, PendingActionManager, SQLitePendingStore

client = DaaiClient(
    api_key=os.environ["DAAI_API_KEY"],
    workspace_key=os.environ["DAAI_WORKSPACE_KEY"],
    base_url=os.environ.get("DAAI_BASE_URL", "${DEFAULT_API_BASE_URL}"),
)

store = SQLitePendingStore("daai_pending.db")
manager = PendingActionManager(client=client, pending_store=store)

ticket = manager.propose(
    action="send_invoice_reminder",
    payload={
        "actor": "finance_agent",
        "invoice_id": "INV-1025",
        "customer_name": "ABC Pty Ltd",
        "amount": 1250,
        "reasoning": "Invoice is overdue and needs a polite follow-up.",
    },
)

if ticket.executable:
    send_invoice_reminder(ticket.payload)`;

const featureCode = `ticket = manager.propose(
    action="send_invoice_reminder",
    payload=payload,
)

if ticket.executable:
    send_invoice_reminder(payload)`;

function cx(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(' ');
}

function StatusPill({
  children,
  tone = 'neutral',
  mono = false,
}: {
  children: ReactNode;
  tone?: StatusTone;
  mono?: boolean;
}) {
  return (
    <span
      className={cx(
        'inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium',
        statusToneClasses[tone],
        mono && 'font-mono',
      )}
    >
      {children}
    </span>
  );
}

function SectionHeading({
  eyebrow,
  title,
  subtitle,
  align = 'center',
}: {
  eyebrow?: string;
  title: string;
  subtitle: string;
  align?: 'center' | 'left';
}) {
  return (
    <div className={cx('mx-auto max-w-3xl', align === 'center' ? 'text-center' : 'text-left')}>
      {eyebrow ? (
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-zinc-500">
          {eyebrow}
        </p>
      ) : null}
      <h2 className="mt-4 text-3xl font-semibold tracking-tight text-zinc-50 sm:text-4xl lg:text-5xl">
        {title}
      </h2>
      <p className="mt-4 text-base leading-7 text-zinc-400 sm:text-lg">{subtitle}</p>
    </div>
  );
}

function LandingButton({
  href,
  children,
  variant = 'primary',
}: {
  href: string;
  children: ReactNode;
  variant?: 'primary' | 'secondary';
}) {
  return (
    <Link
      href={href}
      className={cx(
        'inline-flex min-h-11 items-center justify-center rounded-lg px-5 text-sm font-semibold transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-300',
        variant === 'primary'
          ? 'border border-white/80 bg-zinc-50 text-zinc-950 hover:bg-white'
          : 'border border-white/[0.12] bg-white/[0.03] text-zinc-100 hover:border-white/25 hover:bg-white/[0.06]',
      )}
    >
      {children}
    </Link>
  );
}

export function LandingHeader() {
  return (
    <header className="sticky top-0 z-50 border-b border-white/[0.07] bg-[#050505]/[0.78] backdrop-blur-xl">
      <nav className="mx-auto flex h-16 w-full max-w-7xl items-center justify-between gap-4 px-5 sm:px-6 lg:px-8">
        <Link
          href="/"
          className="group flex items-center gap-3 rounded-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-indigo-300"
          aria-label="DAAI Console home"
        >
          <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/[0.12] bg-white/[0.04] text-sm font-semibold text-zinc-50 transition group-hover:border-emerald-300/40 group-hover:text-emerald-200">
            D
          </span>
          <span className="flex items-baseline gap-2">
            <span className="text-sm font-semibold tracking-[0.2em] text-zinc-50">DAAI</span>
            <span className="hidden text-xs text-zinc-500 sm:inline">Console</span>
          </span>
        </Link>

        <div className="hidden items-center gap-7 md:flex">
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="rounded-md text-sm font-medium text-zinc-400 transition hover:text-zinc-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-indigo-300"
            >
              {link.label}
            </Link>
          ))}
        </div>

        <div className="flex items-center gap-2 sm:gap-3">
          <Link
            href={dashboardHref('/login')}
            className="hidden rounded-lg px-3 py-2 text-sm font-medium text-zinc-400 transition hover:text-zinc-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-indigo-300 sm:inline-flex"
          >
            Log in
          </Link>
          <Link
            href={dashboardHref('/signup')}
            className="inline-flex min-h-9 items-center justify-center rounded-lg border border-white/[0.12] bg-white/[0.04] px-3.5 text-sm font-semibold text-zinc-50 transition hover:border-white/25 hover:bg-white/[0.08] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-indigo-300 sm:px-4"
          >
            Start free
          </Link>
        </div>
      </nav>
    </header>
  );
}

export function ProductMockup() {
  const timeline = [
    { label: 'Action logged', tone: 'success' as const },
    { label: 'Policy evaluated', tone: 'policy' as const },
    { label: 'Approval requested', tone: 'pending' as const },
    { label: 'Awaiting execution', tone: 'pending' as const },
  ];

  return (
    <div className="relative mx-auto mt-16 max-w-6xl">
      <div className="landing-glow absolute -inset-x-8 -top-12 h-72 rounded-full bg-[radial-gradient(circle_at_center,rgba(79,70,229,0.22),rgba(14,165,233,0.09)_34%,transparent_68%)] blur-3xl" />
      <article className="relative overflow-hidden rounded-2xl border border-white/[0.12] bg-[#0a0a0b]/[0.92] shadow-[0_34px_120px_rgba(0,0,0,0.58)] backdrop-blur">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.08] bg-white/[0.025] px-4 py-3 sm:px-5">
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-red-300/70" />
            <span className="h-2.5 w-2.5 rounded-full bg-amber-300/70" />
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-300/70" />
          </div>
          <div className="flex min-w-0 items-center gap-3 text-sm">
            <span className="font-medium text-zinc-200">Action run</span>
            <StatusPill tone="pending">Pending approval</StatusPill>
          </div>
        </div>

        <div className="grid gap-px bg-white/[0.08] md:grid-cols-2">
          <section className="bg-[#0d0d0f] p-5 sm:p-7">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold text-zinc-100">Proposed action</p>
              <StatusPill tone="neutral" mono>
                run_8c4f
              </StatusPill>
            </div>
            <dl className="mt-7 grid gap-4">
              {[
                ['Action', 'send_invoice_reminder'],
                ['Actor', 'finance_agent'],
                ['Amount', '$1,250'],
                ['Source', 'finance_admin_agent'],
              ].map(([label, value]) => (
                <div
                  key={label}
                  className="grid grid-cols-[6.5rem_1fr] gap-3 border-b border-white/[0.06] pb-3 last:border-0 last:pb-0"
                >
                  <dt className="text-sm text-zinc-500">{label}</dt>
                  <dd className="min-w-0 break-words font-mono text-sm text-zinc-100">{value}</dd>
                </div>
              ))}
            </dl>
            <div className="mt-7 rounded-xl border border-white/[0.08] bg-white/[0.025] p-4">
              <p className="text-xs uppercase tracking-[0.16em] text-zinc-500">Input summary</p>
              <p className="mt-2 text-sm leading-6 text-zinc-300">
                Follow up on overdue invoice INV-1025 for ABC Pty Ltd before a finance
                workflow sends email.
              </p>
            </div>
          </section>

          <section className="bg-[#0d0d0f] p-5 sm:p-7">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold text-zinc-100">Policy decision</p>
              <StatusPill tone="policy">Policy gate</StatusPill>
            </div>
            <div className="mt-7 space-y-4">
              <div className="rounded-xl border border-indigo-300/[0.18] bg-indigo-300/[0.035] p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-indigo-200/70">Policy</p>
                <p className="mt-2 text-sm font-medium text-zinc-100">
                  Require approval above $500
                </p>
              </div>
              <div className="rounded-xl border border-amber-300/20 bg-amber-300/[0.055] p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-amber-200/75">
                  Decision
                </p>
                <p className="mt-2 text-sm font-medium text-amber-100">
                  Human approval required
                </p>
              </div>
              <div className="rounded-xl border border-white/[0.08] bg-white/[0.025] p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-zinc-500">Approver</p>
                <p className="mt-2 font-mono text-sm text-zinc-100">client@example.com</p>
              </div>
            </div>
          </section>
        </div>

        <section className="border-t border-white/[0.08] bg-[#0b0b0c] p-5 sm:p-6">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {timeline.map((item, index) => (
              <div
                key={item.label}
                className="relative rounded-xl border border-white/[0.08] bg-white/[0.025] p-4"
              >
                <div className="flex items-center justify-between gap-3">
                  <span
                    className={cx(
                      'h-2.5 w-2.5 rounded-full',
                      item.tone === 'success'
                        ? 'bg-emerald-300'
                        : item.tone === 'policy'
                          ? 'bg-indigo-300'
                          : 'bg-amber-300',
                    )}
                  />
                  <span className="font-mono text-xs text-zinc-600">
                    0{index + 1}
                  </span>
                </div>
                <p className="mt-4 text-sm font-medium text-zinc-100">{item.label}</p>
              </div>
            ))}
          </div>
        </section>
      </article>
    </div>
  );
}

export function HeroSection() {
  return (
    <section className="relative mx-auto max-w-7xl px-5 pb-24 pt-24 text-center sm:px-6 sm:pb-32 sm:pt-32 lg:px-8 lg:pb-40">
      <div className="mx-auto max-w-5xl">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-zinc-500">
          ACTION RUN AUDIT TRAIL
        </p>
        <h1 className="mt-7 text-[2.2rem] font-semibold leading-[1.02] tracking-tight text-zinc-50 sm:text-5xl md:text-6xl lg:text-[76px]">
          Auditable history for registered agent actions.
        </h1>
        <p className="mx-auto mt-7 max-w-3xl text-base leading-7 text-zinc-400 sm:text-lg md:text-xl md:leading-8">
          Log proposals, add approval gates, track execution, and keep client-ready
          receipts with a simple Python SDK.
        </p>
        <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <LandingButton href={dashboardHref('/signup')}>Try for free</LandingButton>
          <LandingButton href="/documentation" variant="secondary">
            View Python example
          </LandingButton>
        </div>
        <p className="mt-5 text-sm text-zinc-500">
          Registered actions only. Deterministic policies. Approval gates where needed.
        </p>
      </div>

      <ProductMockup />
    </section>
  );
}

function MiniStepIcon({ tone }: { tone: StatusTone }) {
  return (
    <span
      className={cx(
        'flex h-9 w-9 items-center justify-center rounded-lg border',
        statusToneClasses[tone],
      )}
      aria-hidden="true"
    >
      <span className="h-2 w-2 rounded-full bg-current" />
    </span>
  );
}

function BoundaryPanel({
  title,
  items,
  accent,
}: {
  title: string;
  items: string[];
  accent: 'daai' | 'app';
}) {
  return (
    <article
      className={cx(
        'rounded-2xl border bg-[#0d0d0f] p-6 transition hover:-translate-y-0.5',
        accent === 'daai'
          ? 'border-indigo-300/20 hover:border-indigo-300/35'
          : 'border-emerald-300/[0.16] hover:border-emerald-300/30',
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-lg font-semibold text-zinc-50">{title}</h3>
        <span
          className={cx(
            'h-2.5 w-2.5 rounded-full',
            accent === 'daai' ? 'bg-indigo-300' : 'bg-emerald-300',
          )}
        />
      </div>
      <ul className="mt-6 space-y-3">
        {items.map((item) => (
          <li key={item} className="flex gap-3 text-sm text-zinc-400">
            <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-zinc-600" />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </article>
  );
}

function HowItWorksSection() {
  return (
    <section id="how-it-works" className="mx-auto max-w-7xl px-5 py-24 sm:px-6 sm:py-32 lg:px-8">
      <SectionHeading
        title="Audit trail for every meaningful agent action."
        subtitle="DAAI gives consultants and clients a shared record of what the agent proposed, what policy decided, what humans approved, and what actually executed."
      />

      <div className="mt-14 grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        {lifecycleSteps.map((step, index) => (
          <article
            key={step.title}
            className="rounded-2xl border border-white/[0.08] bg-[#0d0d0f] p-5 transition hover:-translate-y-0.5 hover:border-white/[0.16]"
          >
            <div className="flex items-center justify-between gap-3">
              <MiniStepIcon tone={step.tone} />
              <span className="font-mono text-xs text-zinc-600">0{index + 1}</span>
            </div>
            <h3 className="mt-6 text-base font-semibold text-zinc-50">{step.title}</h3>
            <p className="mt-3 text-sm leading-6 text-zinc-500">{step.copy}</p>
          </article>
        ))}
      </div>

      <div className="mt-10 grid gap-4 lg:grid-cols-2">
        <BoundaryPanel
          title="DAAI tracks"
          accent="daai"
          items={['Action proposals', 'Policy decisions', 'Approval gates', 'Governance status', 'Client-ready receipts']}
        />
        <BoundaryPanel
          title="Developer app owns"
          accent="app"
          items={[
            'Actual business execution',
            'Executor functions',
            'External integrations',
            'Local worker or cron trigger',
          ]}
        />
      </div>
    </section>
  );
}

function FeatureCard({
  title,
  description,
  children,
  className,
}: {
  title: string;
  description: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <article
      className={cx(
        'group overflow-hidden rounded-3xl border border-white/[0.08] bg-[#0d0d0f] transition duration-300 hover:-translate-y-1 hover:border-white/[0.18]',
        className,
      )}
    >
      <div className="flex h-full flex-col">
        <div className="p-6 sm:p-7">
          <h3 className="text-xl font-semibold tracking-tight text-zinc-50">{title}</h3>
          <p className="mt-3 max-w-xl text-sm leading-6 text-zinc-400">{description}</p>
        </div>
        <div className="mt-auto border-t border-white/[0.06] bg-[radial-gradient(circle_at_top_right,rgba(99,102,241,0.08),transparent_38%)] p-5 sm:p-6">
          {children}
        </div>
      </div>
    </article>
  );
}

function RegisteredActionsIllustration() {
  const rows = [
    ['send_invoice_reminder', 'medium', 'approval > $500', 'pending'],
    ['mark_invoice_paid', 'high', 'always approval', 'policy'],
    ['escalate_overdue_invoice', 'medium', 'always allow', 'success'],
  ] as const;

  return (
    <div className="rounded-2xl border border-white/[0.08] bg-[#09090a]">
      <div className="grid grid-cols-[1fr_5.5rem_8rem] gap-3 border-b border-white/[0.08] px-4 py-3 text-xs uppercase tracking-[0.14em] text-zinc-600">
        <span>Action</span>
        <span>Risk</span>
        <span>Policy</span>
      </div>
      <div className="divide-y divide-white/[0.06]">
        {rows.map(([action, risk, policy, tone]) => (
          <div
            key={action}
            className="grid grid-cols-[1fr_5.5rem_8rem] items-center gap-3 px-4 py-4"
          >
            <span className="min-w-0 truncate font-mono text-sm text-zinc-200">{action}</span>
            <StatusPill>{risk}</StatusPill>
            <StatusPill tone={tone} mono>
              {policy}
            </StatusPill>
          </div>
        ))}
      </div>
    </div>
  );
}

function PolicyIllustration() {
  return (
    <div className="rounded-2xl border border-white/[0.08] bg-[#09090a] p-4">
      <div className="rounded-xl border border-indigo-300/[0.18] bg-indigo-300/[0.04] p-4 font-mono text-sm">
        <p className="text-zinc-500">IF</p>
        <p className="mt-1 text-zinc-100">amount &gt; $500</p>
        <p className="mt-5 text-zinc-500">THEN</p>
        <p className="mt-1 text-amber-200">require approval</p>
      </div>
      <div className="mt-4 grid grid-cols-3 gap-2">
        <StatusPill tone="success">allow</StatusPill>
        <StatusPill tone="pending">ask</StatusPill>
        <StatusPill tone="danger">block</StatusPill>
      </div>
    </div>
  );
}

function ApprovalLinkIllustration() {
  return (
    <div className="rounded-2xl border border-white/[0.08] bg-[#09090a] p-4">
      <div className="border-b border-white/[0.08] pb-3">
        <p className="text-xs uppercase tracking-[0.16em] text-zinc-600">Client view</p>
        <p className="mt-2 text-sm font-medium text-zinc-100">Action history and receipts</p>
      </div>
      <p className="mt-4 text-sm leading-6 text-zinc-400">
        Coming soon: shareable client access links for action history and receipts.
      </p>
      <div className="mt-5 grid grid-cols-2 gap-3">
        <button
          type="button"
          className="rounded-lg border border-emerald-300/30 bg-emerald-300/10 px-3 py-2 text-sm font-semibold text-emerald-200"
        >
          Activity
        </button>
        <button
          type="button"
          className="rounded-lg border border-red-300/30 bg-red-300/10 px-3 py-2 text-sm font-semibold text-red-200"
        >
          Receipts
        </button>
      </div>
    </div>
  );
}

function PythonSdkIllustration() {
  return (
    <div className="overflow-hidden rounded-2xl border border-white/[0.08] bg-[#09090a]">
      <pre className="overflow-x-auto p-4 text-xs leading-6 text-zinc-300">
        <code>{featureCode}</code>
      </pre>
    </div>
  );
}

function ReceiptIllustration() {
  return (
    <div className="rounded-2xl border border-white/[0.08] bg-[#09090a] p-4">
      {[
        ['Decision', <StatusPill key="approved" tone="success">approved</StatusPill>],
        ['Status', <StatusPill key="awaiting" tone="pending">awaiting execution report</StatusPill>],
        ['Policy snapshot', 'require_approval_above_amount'],
        ['Timestamp', '2026-05-23T13:31:08Z'],
      ].map(([label, value]) => (
        <div
          key={label as string}
          className="grid grid-cols-[8.5rem_1fr] gap-3 border-b border-white/[0.06] py-3 text-sm first:pt-0 last:border-0 last:pb-0"
        >
          <span className="text-zinc-500">{label}</span>
          <span className="min-w-0 break-words font-mono text-zinc-200">{value}</span>
        </div>
      ))}
    </div>
  );
}

function QueueIllustration() {
  const queue = [
    ['allowed', 'logged by DAAI', 'success'],
    ['approved', 'ready for worker', 'success'],
    ['failed', 'reported by app', 'danger'],
  ] as const;

  return (
    <div className="rounded-2xl border border-white/[0.08] bg-[#09090a] p-4">
      <div className="space-y-3">
        {queue.map(([title, detail, tone], index) => (
          <div key={title} className="flex items-center gap-3 rounded-xl bg-white/[0.03] p-3">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-white/10 font-mono text-xs text-zinc-500">
              {index + 1}
            </span>
            <div className="min-w-0 flex-1">
              <p className="font-mono text-sm text-zinc-100">{title}</p>
              <p className="text-xs text-zinc-500">{detail}</p>
            </div>
            <StatusPill tone={tone}>run</StatusPill>
          </div>
        ))}
      </div>
    </div>
  );
}

export function FeatureGrid() {
  return (
    <section id="product" className="mx-auto max-w-7xl px-5 py-24 sm:px-6 sm:py-32 lg:px-8">
      <SectionHeading
        title="Lightweight audit and control for registered agent actions."
        subtitle="Built for consultants and agencies who need action visibility, execution status, approval gates where needed, and receipts clients can review."
      />

      <div className="mt-14 grid gap-4 lg:grid-cols-6">
        <FeatureCard
          title="Action logs"
          description="Capture every proposed agent action with actor, payload summary, reasoning, policy decision, and status."
          className="lg:col-span-4"
        >
          <RegisteredActionsIllustration />
        </FeatureCard>

        <FeatureCard
          title="Approval gates"
          description="Require human approval for sensitive or high-risk actions before the connected automation executes them."
          className="lg:col-span-2"
        >
          <PolicyIllustration />
        </FeatureCard>

        <FeatureCard
          title="Client visibility"
          description="Coming soon: shareable client access links for action history and receipts."
          className="lg:col-span-3"
        >
          <ApprovalLinkIllustration />
        </FeatureCard>

        <FeatureCard
          title="Python SDK"
          description="Add DAAI before risky functions in your existing Python automation without rebuilding the whole workflow."
          className="lg:col-span-3"
        >
          <PythonSdkIllustration />
        </FeatureCard>

        <FeatureCard
          title="Client-ready receipts"
          description="Generate clear governance receipts that explain what happened and why."
          className="lg:col-span-3"
        >
          <ReceiptIllustration />
        </FeatureCard>

        <FeatureCard
          title="Execution status"
          description="Track whether an action was allowed, blocked, approved, rejected, executed, or failed."
          className="lg:col-span-3"
        >
          <QueueIllustration />
        </FeatureCard>
      </div>
    </section>
  );
}

function DashboardMockup() {
  const rows = [
    [
      'send_invoice_reminder',
      'finance_agent',
      'approval > $500',
      <StatusPill key="pending" tone="pending">Pending approval</StatusPill>,
      <StatusPill key="not-executed">Not executed</StatusPill>,
      '2m ago',
    ],
    [
      'update_invoice_status',
      'finance_agent',
      'always allow',
      <StatusPill key="allowed" tone="success">Allowed</StatusPill>,
      <StatusPill key="executed" tone="success">Executed</StatusPill>,
      '11m ago',
    ],
    [
      'mark_invoice_paid',
      'finance_agent',
      'always approval',
      <StatusPill key="approved" tone="success">Approved</StatusPill>,
      <StatusPill key="awaiting" tone="pending">Awaiting report</StatusPill>,
      '18m ago',
    ],
    [
      'unknown_action',
      'agent',
      'not registered',
      <StatusPill key="blocked" tone="danger">Blocked</StatusPill>,
      <StatusPill key="not-executed-2">Not executed</StatusPill>,
      '32m ago',
    ],
  ] as const;

  return (
    <div className="relative mt-14 overflow-hidden rounded-3xl border border-white/[0.12] bg-[#09090a] shadow-[0_34px_130px_rgba(0,0,0,0.58)]">
      <div className="absolute -right-16 -top-20 h-64 w-64 rounded-full bg-indigo-500/10 blur-3xl" />
      <div className="overflow-x-auto">
        <div className="grid min-w-[920px] grid-cols-[14rem_1fr]">
          <aside className="border-r border-white/[0.08] bg-white/[0.025] p-5">
            <div className="flex items-center gap-3">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/[0.12] bg-white/[0.04] text-sm font-semibold">
                D
              </span>
              <span className="text-sm font-semibold text-zinc-100">DAAI</span>
            </div>
            <nav className="mt-10 space-y-1 text-sm">
              {['Workspaces', 'Actions', 'Runs', 'Receipts', 'Settings'].map((item) => (
                <div
                  key={item}
                  className={cx(
                    'rounded-lg px-3 py-2',
                    item === 'Runs'
                      ? 'border border-white/10 bg-white/[0.05] text-zinc-100'
                      : 'text-zinc-500',
                  )}
                >
                  {item}
                </div>
              ))}
            </nav>
          </aside>

          <main className="p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.18em] text-zinc-600">
                  Workspace
                </p>
                <h3 className="mt-2 text-2xl font-semibold text-zinc-50">
                  Acme Finance Admin
                </h3>
              </div>
              <StatusPill tone="policy">Action audit layer</StatusPill>
            </div>

            <div className="mt-7 grid grid-cols-4 gap-3">
              {[
                ['24', 'action runs', 'neutral'],
                ['7', 'pending approval', 'pending'],
                ['14', 'executed', 'success'],
                ['3', 'blocked', 'danger'],
              ].map(([value, label, tone]) => (
                <div key={label} className="rounded-xl border border-white/[0.08] bg-white/[0.025] p-4">
                  <p
                    className={cx(
                      'text-2xl font-semibold',
                      tone === 'pending'
                        ? 'text-amber-200'
                        : tone === 'success'
                          ? 'text-emerald-200'
                          : tone === 'danger'
                            ? 'text-red-200'
                            : 'text-zinc-50',
                    )}
                  >
                    {value}
                  </p>
                  <p className="mt-1 text-xs uppercase tracking-[0.14em] text-zinc-600">
                    {label}
                  </p>
                </div>
              ))}
            </div>

            <div className="mt-6 overflow-hidden rounded-2xl border border-white/[0.08]">
              <table className="w-full border-collapse text-left text-sm">
                <thead className="bg-white/[0.04] text-xs uppercase tracking-[0.14em] text-zinc-600">
                  <tr>
                    {['Action', 'Actor', 'Policy', 'Status', 'Execution', 'Time'].map((heading) => (
                      <th key={heading} className="px-4 py-3 font-medium">
                        {heading}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.06]">
                  {rows.map((row) => (
                    <tr key={row[0]} className="bg-[#0d0d0f]">
                      <td className="px-4 py-4 font-mono text-zinc-100">{row[0]}</td>
                      <td className="px-4 py-4 font-mono text-zinc-400">{row[1]}</td>
                      <td className="px-4 py-4 font-mono text-zinc-400">{row[2]}</td>
                      <td className="px-4 py-4">{row[3]}</td>
                      <td className="px-4 py-4">{row[4]}</td>
                      <td className="px-4 py-4 text-zinc-500">{row[5]}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}

function ProductScreenshotSection() {
  return (
    <section className="mx-auto max-w-7xl px-5 py-24 sm:px-6 sm:py-32 lg:px-8">
      <SectionHeading
        title="Action visibility for consultants and clients."
        subtitle="Track what the agent proposed, what policy decided, what needed approval, what was blocked, and what actually executed."
      />
      <DashboardMockup />
    </section>
  );
}

export function CodeBlock({ code }: { code: string }) {
  const lines = code.split('\n');

  return (
    <div className="overflow-hidden rounded-3xl border border-white/[0.08] bg-[#09090a] shadow-[0_24px_80px_rgba(0,0,0,0.42)]">
      <div className="flex items-center justify-between gap-3 border-b border-white/[0.08] bg-white/[0.025] px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-red-300/60" />
          <span className="h-2.5 w-2.5 rounded-full bg-amber-300/60" />
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-300/60" />
        </div>
        <span className="font-mono text-xs text-zinc-500">agent_action_audit.py</span>
      </div>
      <pre className="max-h-[430px] overflow-auto p-4 text-xs leading-6 text-zinc-300 sm:max-h-[560px] sm:p-6 sm:text-sm">
        <code>
          {lines.map((line, index) => (
            <span key={`${index}-${line}`} className="grid grid-cols-[2.25rem_1fr] gap-4">
              <span className="select-none text-right text-zinc-700">{index + 1}</span>
              <span className="whitespace-pre">{line || ' '}</span>
            </span>
          ))}
        </code>
      </pre>
    </div>
  );
}

function SDKSection() {
  const bullets = [
    'Log registered action proposals',
    'Store pending runs locally',
    'Check whether approval is needed',
    'Execute only when policy permits',
    'Report success or failure',
  ];

  return (
    <section id="sdk" className="mx-auto max-w-7xl px-5 py-24 sm:px-6 sm:py-32 lg:px-8">
      <div className="grid gap-10 lg:grid-cols-[0.82fr_1.18fr] lg:items-start">
        <div className="max-w-xl">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-zinc-500">
            Python SDK
          </p>
          <h2 className="mt-4 text-3xl font-semibold tracking-tight text-zinc-50 sm:text-4xl lg:text-5xl">
            Add the audit gate in Python.
          </h2>
          <p className="mt-5 text-base leading-7 text-zinc-400 sm:text-lg">
            Place the SDK before risky functions so the proposal is logged, evaluated,
            and controlled before your automation performs the real action.
          </p>
          <ul className="mt-8 space-y-3">
            {bullets.map((bullet) => (
              <li key={bullet} className="flex items-center gap-3 text-sm text-zinc-400">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-300" />
                {bullet}
              </li>
            ))}
          </ul>
        </div>
        <CodeBlock code={sdkCode} />
      </div>
    </section>
  );
}

function ApprovalFlowSection() {
  const flow = [
    ['Agent proposes', 'Registered action and payload', 'policy'],
    ['DAAI logs', 'Action run records context and reasoning', 'neutral'],
    ['Policy decides', 'Allowed, pending approval, or blocked', 'policy'],
    ['Approval if needed', 'Human decision before connected automation executes', 'pending'],
    ['Receipt updated', 'Decision and execution result recorded', 'success'],
  ] as const;

  return (
    <section className="mx-auto max-w-7xl px-5 py-24 sm:px-6 sm:py-32 lg:px-8">
      <SectionHeading
        title="Control where it matters, audit throughout."
        subtitle="DAAI logs registered proposals first. Approval gates are applied only where policy says a human decision is needed."
      />
      <div className="mt-14 rounded-3xl border border-white/[0.08] bg-[#0d0d0f] p-5 sm:p-7">
        <div className="grid gap-4 lg:grid-cols-5">
          {flow.map(([title, detail, tone], index) => (
            <div key={title} className="relative">
              <article className="h-full rounded-2xl border border-white/[0.08] bg-[#09090a] p-5">
                <MiniStepIcon tone={tone} />
                <h3 className="mt-5 text-base font-semibold text-zinc-50">{title}</h3>
                <p className="mt-2 text-sm leading-6 text-zinc-500">{detail}</p>
              </article>
              {index < flow.length - 1 ? (
                <div className="absolute -right-3 top-1/2 hidden h-px w-6 bg-white/[0.16] lg:block" />
              ) : null}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function PricingSection() {
  const plans = [
    {
      name: 'Free',
      price: '$0',
      priceSuffix: '/month',
      description: 'For proving the audit, approval, execution, and receipt path with real clients.',
      limits: [
        ['Client workspaces', '2 active'],
        ['Actions per workspace', '3 active'],
        ['Action-run audit records', '1,000 / month'],
        ['Approval emails', '100 / month'],
      ],
      note: 'These limits are enforced in the backend during beta.',
      badge: 'Live beta',
      highlighted: true,
    },
    {
      name: 'Starter',
      price: 'After beta',
      priceSuffix: '',
      description: 'For consultants auditing and controlling a small set of client automations after launch validation.',
      limits: [
        ['Client workspaces', 'Higher cap'],
        ['Actions per workspace', 'Higher cap'],
        ['Action-run audit records', 'Higher monthly cap'],
        ['Approval emails', 'Higher monthly cap'],
      ],
      note: 'Paid tiers will be available after a successful beta test.',
      badge: 'Coming later',
      highlighted: false,
    },
    {
      name: 'Growth',
      price: 'After beta',
      priceSuffix: '',
      description: 'Built for small agencies standardizing action visibility and controls after the beta proves reliability.',
      limits: [
        ['Client workspaces', 'Agency scale'],
        ['Actions per workspace', 'Agency scale'],
        ['Action-run audit records', 'Higher monthly cap'],
        ['Approval emails', 'Higher monthly cap'],
      ],
      note: 'Paid tiers will be available after a successful beta test.',
      badge: 'Coming later',
      highlighted: false,
    },
  ];

  return (
    <section id="pricing" className="mx-auto max-w-7xl px-5 py-24 sm:px-6 sm:py-32 lg:px-8">
      <SectionHeading
        title="Beta launch limits are enforced."
        subtitle="Start with the limits enforced by the backend today. Paid tiers will be available after a successful beta test."
      />
      <div className="mx-auto mt-8 max-w-3xl rounded-2xl border border-amber-300/20 bg-amber-300/[0.055] p-4 text-center">
        <p className="text-sm font-medium text-amber-100">
          Paid tiers will be available after a successful beta test.
        </p>
        <p className="mt-1 text-sm text-amber-100/75">
          Beta access is intentionally limited during launch to protect system reliability.
        </p>
      </div>
      <div className="mt-14 grid gap-4 lg:grid-cols-3">
        {plans.map((plan) => (
          <article
            key={plan.name}
            className={cx(
              'flex min-h-[31rem] flex-col rounded-3xl border bg-[#0d0d0f] p-6 transition hover:-translate-y-0.5',
              plan.highlighted
                ? 'border-indigo-300/[0.26] shadow-[0_0_80px_rgba(99,102,241,0.12)]'
                : 'border-white/[0.08]',
            )}
          >
            <div className="flex items-start justify-between gap-3">
              <h3 className="text-xl font-semibold text-zinc-50">{plan.name}</h3>
              <StatusPill tone={plan.highlighted ? 'success' : 'neutral'}>
                {plan.badge}
              </StatusPill>
            </div>
            <p className="mt-5 flex items-baseline gap-1">
              <span
                className={cx(
                  'font-semibold tracking-tight text-zinc-50',
                  plan.price === '$0' ? 'text-5xl' : 'text-3xl',
                )}
              >
                {plan.price}
              </span>
              {plan.priceSuffix ? (
                <span className="text-sm text-zinc-500">{plan.priceSuffix}</span>
              ) : null}
            </p>
            <p className="mt-5 min-h-12 text-sm leading-6 text-zinc-400">{plan.description}</p>

            <div className="mt-8 overflow-hidden rounded-2xl border border-white/[0.08] bg-[#09090a]">
              {plan.limits.map(([label, value]) => (
                <div
                  key={label}
                  className="grid grid-cols-[1fr_auto] items-center gap-4 border-t border-white/[0.06] px-4 py-4 first:border-t-0"
                >
                  <span className="text-sm text-zinc-500">{label}</span>
                  <span className="text-right font-mono text-sm font-semibold text-zinc-100">
                    {value}
                  </span>
                </div>
              ))}
            </div>

            <p className="mt-auto pt-7 text-sm leading-6 text-zinc-500">{plan.note}</p>
          </article>
        ))}
      </div>
      <div
        id="paid-interest"
        className="mx-auto mt-10 max-w-3xl rounded-3xl border border-white/[0.08] bg-[#0d0d0f] p-6"
      >
        <div className="grid gap-5 md:grid-cols-[0.9fr_1.1fr] md:items-end">
          <div>
            <h3 className="text-lg font-semibold text-zinc-50">
              Interested in higher capacity access?
            </h3>
            <p className="mt-2 text-sm leading-6 text-zinc-400">
              Leave an email and a short note. We will follow up when paid tiers are ready after beta.
            </p>
          </div>
          <form
            action={submitPricingInterest}
            className="grid gap-3 sm:grid-cols-[1fr_auto]"
          >
            <label htmlFor="pricing_interest_company_website" className="hidden">
              Company website
            </label>
            <input
              id="pricing_interest_company_website"
              name="company_website"
              type="text"
              tabIndex={-1}
              autoComplete="off"
              className="hidden"
            />
            <label htmlFor="pricing_interest_email" className="sr-only">
              Email
            </label>
            <input
              id="pricing_interest_email"
              name="email"
              type="email"
              required
              placeholder="you@example.com"
              className="min-h-11 rounded-lg border border-white/[0.12] bg-[#09090a] px-3 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-indigo-300/60 focus:outline-none"
            />
            <button
              type="submit"
              className="inline-flex min-h-11 items-center justify-center rounded-lg border border-white/80 bg-zinc-50 px-4 text-sm font-semibold text-zinc-950 transition hover:bg-white"
            >
              Reach out
            </button>
            <label htmlFor="pricing_interest_note" className="sr-only">
              Note
            </label>
            <input
              id="pricing_interest_note"
              name="note"
              type="text"
              placeholder="Optional: team size or use case"
              className="min-h-11 rounded-lg border border-white/[0.12] bg-[#09090a] px-3 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-indigo-300/60 focus:outline-none sm:col-span-2"
            />
          </form>
        </div>
      </div>
    </section>
  );
}

export function FinalCTA() {
  return (
    <section className="mx-auto max-w-5xl px-5 py-24 text-center sm:px-6 sm:py-32 lg:px-8">
      <div className="relative overflow-hidden rounded-3xl border border-white/[0.08] bg-[#0d0d0f] px-6 py-14 sm:px-10 sm:py-16">
        <div className="landing-glow absolute inset-x-8 -top-24 h-56 rounded-full bg-[radial-gradient(circle_at_center,rgba(79,70,229,0.18),transparent_65%)] blur-3xl" />
        <div className="relative">
          <h2 className="text-3xl font-semibold tracking-tight text-zinc-50 sm:text-4xl lg:text-5xl">
            Give your AI automations an audit trail clients can understand.
          </h2>
          <p className="mx-auto mt-5 max-w-2xl text-base leading-7 text-zinc-400 sm:text-lg">
            Start with one client workspace. Register one risky action. Log the
            proposal, control execution when needed, and keep the receipt.
          </p>
          <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <LandingButton href={dashboardHref('/signup')}>Try for free</LandingButton>
            <LandingButton href="/documentation" variant="secondary">
              View Python example
            </LandingButton>
          </div>
        </div>
      </div>
    </section>
  );
}

function LandingFooter() {
  return (
    <footer className="border-t border-white/[0.07] px-5 py-10 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-semibold tracking-[0.2em] text-zinc-50">DAAI</p>
          <p className="mt-2 text-sm text-zinc-500">
            Lightweight audit and control for registered AI-agent actions.
          </p>
        </div>
        <nav className="flex flex-wrap gap-x-6 gap-y-3 text-sm text-zinc-500">
          {[
            ['Product', '#product'],
            ['Documentation', '/documentation'],
            ['Pricing', '#pricing'],
            ['Login', dashboardHref('/login')],
          ].map(([label, href]) => (
            <Link
              key={label}
              href={href}
              className="rounded-md transition hover:text-zinc-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-indigo-300"
            >
              {label}
            </Link>
          ))}
        </nav>
      </div>
    </footer>
  );
}

export function LandingPage() {
  return (
    <div className="min-h-screen overflow-hidden bg-[#050505] text-zinc-50">
      <LandingHeader />
      <main>
        <HeroSection />
        <HowItWorksSection />
        <FeatureGrid />
        <ProductScreenshotSection />
        <SDKSection />
        <ApprovalFlowSection />
        <PricingSection />
        <FinalCTA />
      </main>
      <LandingFooter />
    </div>
  );
}
