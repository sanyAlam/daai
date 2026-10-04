import Link from 'next/link';

import { buttonStyles, Notice, SectionCard } from '@/components/console-ui';
import type { Tone } from '@/components/console-ui';

type DecisionKind = 'approve' | 'reject' | 'block';

type PublicDecisionResult =
  | {
      kind: 'success';
      title: string;
      message: string;
      actionRunId: string | null;
      governanceStatus: string | null;
    }
  | {
      kind: 'invalid';
      title: string;
      message: string;
      detail: string;
    }
  | {
      kind: 'expired';
      title: string;
      message: string;
      detail: string;
    }
  | {
      kind: 'used';
      title: string;
      message: string;
      detail: string;
    }
  | {
      kind: 'error';
      title: string;
      message: string;
      detail: string;
    };

type ApiPayload = {
  action_run_id?: string;
  governance_status?: string;
  detail?: string;
  message?: string;
  error?: string;
};

const DEFAULT_API_BASE_URL =
  process.env.NODE_ENV === 'production'
    ? 'http://127.0.0.1:8000'
    : 'http://127.0.0.1:8000';
const API_BASE_URL = process.env.DAAI_API_BASE_URL ?? DEFAULT_API_BASE_URL;

function decisionLabel(decision: DecisionKind): string {
  switch (decision) {
    case 'approve':
      return 'approved';
    case 'reject':
      return 'rejected';
    default:
      return 'blocked';
  }
}

function readDetail(payload: ApiPayload | null, fallback: string): string {
  if (payload?.message && payload.message.trim()) {
    return payload.message;
  }
  if (payload?.detail && payload.detail.trim()) {
    return payload.detail;
  }
  return fallback;
}

async function submitDecision(
  decision: DecisionKind,
  token: string,
): Promise<PublicDecisionResult> {
  let response: Response;
  try {
    response = await fetch(
      `${API_BASE_URL}/v1/public/${decision}/${encodeURIComponent(token)}`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        cache: 'no-store',
      },
    );
  } catch {
    return {
      kind: 'error',
      title: 'Decision Unavailable',
      message: 'We could not reach the governance service right now.',
      detail: 'Please try again in a moment.',
    };
  }

  let payload: ApiPayload | null = null;
  try {
    payload = (await response.json()) as ApiPayload;
  } catch {
    payload = null;
  }

  if (response.ok) {
    return {
      kind: 'success',
      title: `Action ${decisionLabel(decision)}`,
      message: `Your decision has been recorded and the action run has been ${decisionLabel(
        decision,
      )}.`,
      actionRunId:
        typeof payload?.action_run_id === 'string' ? payload.action_run_id : null,
      governanceStatus:
        typeof payload?.governance_status === 'string'
          ? payload.governance_status
          : null,
    };
  }

  if (response.status === 404) {
    return {
      kind: 'invalid',
      title: 'Invalid Link',
      message: 'This decision link is invalid or no longer available.',
      detail: readDetail(payload, 'The token could not be found.'),
    };
  }

  if (response.status === 410) {
    return {
      kind: 'expired',
      title: 'Link Expired',
      message: 'This decision link has expired.',
      detail: readDetail(payload, 'Request a new approval link from the workspace owner.'),
    };
  }

  if (response.status === 409) {
    return {
      kind: 'used',
      title: 'Decision Already Processed',
      message: 'This decision link has already been used.',
      detail: readDetail(payload, 'The action decision has already been finalized.'),
    };
  }

  return {
    kind: 'error',
    title: 'Decision Failed',
    message: 'We could not process this decision.',
    detail: readDetail(payload, `Request failed with status ${response.status}.`),
  };
}

function accentClass(kind: PublicDecisionResult['kind']): Tone {
  if (kind === 'success') {
    return 'success';
  }
  if (kind === 'error') {
    return 'danger';
  }
  return 'warning';
}

export async function PublicDecisionPage({
  decision,
  token,
}: {
  decision: DecisionKind;
  token: string;
}) {
  const result = await submitDecision(decision, token);

  return (
    <section className="mx-auto max-w-2xl space-y-4">
      <SectionCard>
        <h1 className="text-2xl font-semibold text-text">{result.title}</h1>
        <p className="mt-2 text-sm text-muted">{result.message}</p>

        <Notice tone={accentClass(result.kind)} className="mt-4">
          {'detail' in result ? result.detail : 'Decision processed successfully.'}
        </Notice>

        {'actionRunId' in result && result.actionRunId ? (
          <p className="mt-4 break-all text-xs text-muted">Action Run ID: {result.actionRunId}</p>
        ) : null}

        {'governanceStatus' in result && result.governanceStatus ? (
          <p className="mt-1 text-xs text-muted">
            Governance status: {result.governanceStatus}
          </p>
        ) : null}

        <div className="mt-5 flex flex-wrap gap-2">
          <Link
            href="/login"
            className={buttonStyles.primary}
          >
            Go to Log in
          </Link>
          <Link
            href="/home"
            className={buttonStyles.secondary}
          >
            Go to Home
          </Link>
        </div>
      </SectionCard>
    </section>
  );
}
