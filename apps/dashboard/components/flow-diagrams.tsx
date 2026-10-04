'use client';

import {
  DaaiDiagramCanvas,
  type DaaiDiagramEdgeConfig,
  type DaaiDiagramNodeConfig,
} from '@/components/diagrams/DaaiDiagramCanvas';

const coreFlowNodes: DaaiDiagramNodeConfig[] = [
  {
    id: 'agent-label',
    title: 'Agent proposal',
    x: 95,
    y: 62,
    size: 'label',
  },
  {
    id: 'agent',
    title: 'Python agent',
    subtitle: 'decides action may be needed',
    x: 90,
    y: 120,
    tone: 'neutral',
    size: 'pill',
  },
  {
    id: 'intercept',
    title: 'client.intercept()',
    subtitle: 'asks DAAI before execution',
    x: 90,
    y: 205,
    tone: 'info',
    size: 'pill',
    mono: true,
  },
  {
    id: 'action-name',
    title: 'action_name',
    subtitle: 'example: send_invoice_reminder',
    x: 90,
    y: 290,
    tone: 'brand',
    size: 'pill',
    mono: true,
  },
  {
    id: 'gate',
    title: 'DAAI policy gate',
    subtitle: 'registered action • policy • approval',
    x: 455,
    y: 185,
    tone: 'brand',
    size: 'hero',
    badges: ['Lookup', 'Policy', 'Decision'],
  },
  {
    id: 'unknown',
    title: 'Unknown action',
    subtitle: 'blocked by design',
    x: 345,
    y: 430,
    tone: 'danger',
    size: 'small',
  },
  {
    id: 'threshold',
    title: 'Policy threshold',
    subtitle: 'amount/risk check',
    x: 595,
    y: 455,
    tone: 'muted',
    size: 'small',
  },
  {
    id: 'approval-needed',
    title: 'Approval needed',
    subtitle: 'human decision',
    x: 845,
    y: 430,
    tone: 'approval',
    size: 'small',
  },
  {
    id: 'audit',
    title: 'Audit trail',
    subtitle: 'receipt evidence',
    x: 1095,
    y: 455,
    tone: 'neutral',
    size: 'small',
  },
  {
    id: 'approval',
    title: 'Human approval',
    subtitle: 'if required by policy',
    x: 955,
    y: 95,
    tone: 'approval',
    size: 'medium',
  },
  {
    id: 'execute',
    title: 'Your app executes',
    subtitle: 'only when executable=true',
    x: 1010,
    y: 245,
    tone: 'success',
    size: 'large',
  },
  {
    id: 'blocked',
    title: 'Blocked / rejected',
    subtitle: 'executable=false',
    x: 995,
    y: 355,
    tone: 'danger',
    size: 'small',
  },
  {
    id: 'receipt',
    title: 'Governance receipt',
    subtitle: 'proposal + decision + result',
    x: 1350,
    y: 245,
    tone: 'brand',
    size: 'large',
  },
];

const coreFlowEdges: DaaiDiagramEdgeConfig[] = [
  { id: 'agent-gate', source: 'agent', target: 'gate' },
  { id: 'intercept-gate', source: 'intercept', target: 'gate', tone: 'info' },
  { id: 'action-name-gate', source: 'action-name', target: 'gate', tone: 'brand' },
  {
    id: 'gate-approval',
    source: 'gate',
    target: 'approval',
    label: 'approval required',
    tone: 'approval',
  },
  {
    id: 'approval-execute',
    source: 'approval',
    target: 'execute',
    label: 'approved',
    tone: 'success',
    sourceHandle: 'source-bottom',
    targetHandle: 'target-top',
  },
  {
    id: 'gate-execute',
    source: 'gate',
    target: 'execute',
    label: 'allowed',
    tone: 'success',
  },
  {
    id: 'gate-blocked',
    source: 'gate',
    target: 'blocked',
    label: 'blocked',
    tone: 'danger',
  },
  {
    id: 'approval-blocked',
    source: 'approval',
    target: 'blocked',
    label: 'rejected',
    tone: 'danger',
    sourceHandle: 'source-bottom',
    targetHandle: 'target-top',
  },
  {
    id: 'execute-receipt',
    source: 'execute',
    target: 'receipt',
    label: 'report result',
    tone: 'success',
  },
  {
    id: 'blocked-receipt',
    source: 'blocked',
    target: 'receipt',
    label: 'receipt',
    tone: 'neutral',
  },
  {
    id: 'gate-unknown',
    source: 'gate',
    target: 'unknown',
    tone: 'muted',
    dashed: true,
    sourceHandle: 'source-bottom',
    targetHandle: 'target-top',
  },
  {
    id: 'gate-threshold',
    source: 'gate',
    target: 'threshold',
    tone: 'muted',
    dashed: true,
    sourceHandle: 'source-bottom',
    targetHandle: 'target-top',
  },
  {
    id: 'gate-approval-needed',
    source: 'gate',
    target: 'approval-needed',
    tone: 'muted',
    dashed: true,
    sourceHandle: 'source-bottom',
    targetHandle: 'target-top',
  },
  {
    id: 'gate-audit',
    source: 'gate',
    target: 'audit',
    tone: 'muted',
    dashed: true,
    sourceHandle: 'source-bottom',
    targetHandle: 'target-top',
  },
];

const policyNodes: DaaiDiagramNodeConfig[] = [
  {
    id: 'start',
    title: 'Agent calls intercept()',
    subtitle: 'includes actor and reasoning',
    x: 80,
    y: 185,
    tone: 'info',
    size: 'medium',
    mono: true,
  },
  {
    id: 'payload',
    title: 'action_name + input payload',
    subtitle: 'the proposal DAAI evaluates',
    x: 80,
    y: 320,
    tone: 'brand',
    size: 'medium',
    mono: true,
  },
  {
    id: 'registered-check',
    title: 'Registered action?',
    subtitle: 'DAAI checks whether this action exists in the workspace.',
    x: 405,
    y: 220,
    tone: 'brand',
    size: 'hero',
    badges: ['Workspace', 'Lookup'],
  },
  {
    id: 'unknown-block',
    title: 'Block unknown action',
    subtitle: 'executable=false',
    x: 790,
    y: 395,
    tone: 'danger',
    size: 'medium',
  },
  {
    id: 'load-policy',
    title: 'Load policy',
    subtitle: 'evaluate deterministic rule',
    x: 810,
    y: 120,
    tone: 'success',
    size: 'medium',
  },
  {
    id: 'policy-types',
    title: 'Policy type',
    subtitle: 'MVP policy chooses one outcome.',
    x: 1115,
    y: 120,
    tone: 'muted',
    size: 'large',
  },
  {
    id: 'allow',
    title: 'always_allow',
    subtitle: 'executable=true',
    x: 1495,
    y: 20,
    tone: 'success',
    size: 'medium',
    mono: true,
  },
  {
    id: 'require-approval',
    title: 'always_require_approval',
    subtitle: 'pending_approval',
    x: 1495,
    y: 150,
    tone: 'approval',
    size: 'medium',
    mono: true,
  },
  {
    id: 'amount-policy',
    title: 'require_approval_above_amount',
    subtitle: 'threshold decides',
    x: 1495,
    y: 280,
    tone: 'approval',
    size: 'medium',
    mono: true,
  },
  {
    id: 'block',
    title: 'always_block',
    subtitle: 'executable=false',
    x: 1495,
    y: 410,
    tone: 'danger',
    size: 'medium',
    mono: true,
  },
];

const policyEdges: DaaiDiagramEdgeConfig[] = [
  { id: 'start-registered', source: 'start', target: 'registered-check' },
  { id: 'payload-registered', source: 'payload', target: 'registered-check', tone: 'brand' },
  {
    id: 'registered-unknown',
    source: 'registered-check',
    target: 'unknown-block',
    label: 'No',
    tone: 'danger',
    sourceHandle: 'source-bottom',
    targetHandle: 'target-left',
  },
  {
    id: 'registered-load',
    source: 'registered-check',
    target: 'load-policy',
    label: 'Yes',
    tone: 'success',
    sourceHandle: 'source-right',
    targetHandle: 'target-left',
  },
  {
    id: 'load-policy-type',
    source: 'load-policy',
    target: 'policy-types',
    tone: 'success',
  },
  {
    id: 'policy-allow',
    source: 'policy-types',
    target: 'allow',
    label: 'allowed',
    tone: 'success',
  },
  {
    id: 'policy-require',
    source: 'policy-types',
    target: 'require-approval',
    label: 'needs approval',
    tone: 'approval',
  },
  {
    id: 'policy-amount',
    source: 'policy-types',
    target: 'amount-policy',
    label: 'threshold',
    tone: 'approval',
  },
  {
    id: 'policy-block',
    source: 'policy-types',
    target: 'block',
    label: 'blocked',
    tone: 'danger',
  },
];

const approvalNodes: DaaiDiagramNodeConfig[] = [
  {
    id: 'proposed',
    title: 'Action proposed',
    subtitle: 'client.intercept()',
    x: 55,
    y: 215,
    tone: 'info',
    size: 'medium',
  },
  {
    id: 'action-run',
    title: 'Action run created',
    subtitle: 'input + policy snapshot',
    x: 285,
    y: 215,
    tone: 'neutral',
    size: 'medium',
  },
  {
    id: 'approval-email',
    title: 'Approval link sent',
    subtitle: 'client receives email',
    x: 525,
    y: 215,
    tone: 'approval',
    size: 'medium',
  },
  {
    id: 'client-decision',
    title: 'Client decision',
    subtitle: 'approve or reject',
    x: 785,
    y: 185,
    tone: 'approval',
    size: 'large',
  },
  {
    id: 'approved',
    title: 'Approved',
    subtitle: 'executable=true',
    x: 1095,
    y: 105,
    tone: 'success',
    size: 'small',
  },
  {
    id: 'rejected',
    title: 'Rejected',
    subtitle: 'executable=false',
    x: 1095,
    y: 345,
    tone: 'danger',
    size: 'small',
  },
  {
    id: 'runner',
    title: 'Runner checks status',
    subtitle: 'worker polls DAAI',
    x: 1340,
    y: 105,
    tone: 'info',
    size: 'medium',
  },
  {
    id: 'execute',
    title: 'Your app executes',
    subtitle: 'local risky function',
    x: 1595,
    y: 105,
    tone: 'success',
    size: 'medium',
  },
  {
    id: 'report',
    title: 'Report result',
    subtitle: 'report_executed() or report_failed()',
    x: 1850,
    y: 105,
    tone: 'brand',
    size: 'medium',
  },
  {
    id: 'receipt',
    title: 'Receipt updated',
    subtitle: 'evidence preserved',
    x: 2115,
    y: 215,
    tone: 'brand',
    size: 'large',
  },
];

const approvalEdges: DaaiDiagramEdgeConfig[] = [
  { id: 'proposed-run', source: 'proposed', target: 'action-run' },
  { id: 'run-email', source: 'action-run', target: 'approval-email', tone: 'approval' },
  { id: 'email-decision', source: 'approval-email', target: 'client-decision', tone: 'approval' },
  {
    id: 'decision-approved',
    source: 'client-decision',
    target: 'approved',
    label: 'approve',
    tone: 'success',
    sourceHandle: 'source-right',
    targetHandle: 'target-left',
  },
  {
    id: 'decision-rejected',
    source: 'client-decision',
    target: 'rejected',
    label: 'reject',
    tone: 'danger',
    sourceHandle: 'source-bottom',
    targetHandle: 'target-left',
  },
  { id: 'approved-runner', source: 'approved', target: 'runner', tone: 'success' },
  { id: 'runner-execute', source: 'runner', target: 'execute', tone: 'success' },
  { id: 'execute-report', source: 'execute', target: 'report', tone: 'success' },
  {
    id: 'report-receipt',
    source: 'report',
    target: 'receipt',
    label: 'receipt',
    tone: 'brand',
  },
  {
    id: 'rejected-receipt',
    source: 'rejected',
    target: 'receipt',
    label: 'receipt',
    tone: 'danger',
  },
];

export function MainDaaiFlowDiagram() {
  return (
    <DaaiDiagramCanvas
      nodes={coreFlowNodes}
      edges={coreFlowEdges}
      height={560}
      minWidth={1680}
    />
  );
}

export function PolicyDecisionDiagram() {
  return (
    <DaaiDiagramCanvas
      nodes={policyNodes}
      edges={policyEdges}
      height={560}
      minWidth={1840}
    />
  );
}

export function ApprovalLifecycleDiagram() {
  return (
    <DaaiDiagramCanvas
      nodes={approvalNodes}
      edges={approvalEdges}
      height={540}
      minWidth={2460}
    />
  );
}
