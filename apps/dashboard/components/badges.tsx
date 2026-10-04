import { ExecutionStatus, GovernanceStatus } from '@/lib/types';
import { StatusBadge } from '@/components/console-ui';

function humanizeStatus(value: string): string {
  return value.replaceAll('_', ' ');
}

function governanceTone(value: GovernanceStatus) {
  if (value === 'allowed' || value === 'approved') {
    return 'success';
  }
  if (value === 'pending_approval') {
    return 'warning';
  }
  return 'danger';
}

function executionTone(value: ExecutionStatus) {
  if (value === 'executed') {
    return 'success';
  }
  if (value === 'failed') {
    return 'danger';
  }
  if (value === 'awaiting_execution_report') {
    return 'warning';
  }
  return 'neutral';
}

export function GovernanceStatusBadge({
  value,
}: {
  value: GovernanceStatus;
}) {
  return <StatusBadge label={humanizeStatus(value)} tone={governanceTone(value)} />;
}

export function ExecutionStatusBadge({ value }: { value: ExecutionStatus }) {
  return <StatusBadge label={humanizeStatus(value)} tone={executionTone(value)} />;
}

export function ExecutableBadge({ value }: { value: boolean }) {
  return (
    <StatusBadge
      label={value ? 'yes' : 'no'}
      tone={value ? 'success' : 'neutral'}
    />
  );
}
