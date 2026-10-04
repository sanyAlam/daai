'use client';

import { Handle, Position, type Node, type NodeProps } from '@xyflow/react';

import { diagramTone, type DiagramNodeSize, type DiagramTone } from '@/components/diagrams/diagramStyles';

export type DaaiDiagramNodeData = {
  title: string;
  subtitle?: string;
  eyebrow?: string;
  tone?: DiagramTone;
  size?: DiagramNodeSize;
  badges?: string[];
  mono?: boolean;
};

function HandleDot({ type, position }: { type: 'source' | 'target'; position: Position }) {
  return (
    <Handle
      id={`${type}-${position}`}
      type={type}
      position={position}
      className="!h-2.5 !w-2.5 !border !border-borderStrong !bg-canvas !opacity-90"
      isConnectable={false}
    />
  );
}

function BranchMark() {
  return (
    <div className="relative h-8 w-10">
      <span className="absolute left-0 top-1/2 h-1.5 w-1.5 -translate-y-1/2 rounded-full bg-muted" />
      <span className="absolute left-4 top-1 h-1.5 w-1.5 rounded-full bg-muted" />
      <span className="absolute left-4 bottom-1 h-1.5 w-1.5 rounded-full bg-muted" />
      <span
        className="absolute left-1.5 top-[14px] h-px w-4 bg-muted"
        style={{ transform: 'rotate(-28deg)' }}
      />
      <span
        className="absolute left-1.5 top-[17px] h-px w-4 bg-muted"
        style={{ transform: 'rotate(28deg)' }}
      />
    </div>
  );
}

export type DaaiFlowNode = Node<DaaiDiagramNodeData, 'daai'>;

export function DaaiDiagramNode({ data }: NodeProps<DaaiFlowNode>) {
  const tone = data.tone ?? 'neutral';
  const size = data.size ?? 'medium';
  const styles = diagramTone[tone];

  if (size === 'label') {
    return (
      <div className="px-2 text-sm font-semibold text-muted">
        {data.title}
      </div>
    );
  }

  const isHero = size === 'hero';
  const isPill = size === 'pill';
  const isLarge = size === 'large';

  return (
    <div
      className={`relative rounded-[22px] border ${styles.border} ${styles.bg} ${styles.text} shadow-[0_18px_44px_rgba(0,0,0,0.30)] ${
        isHero ? 'px-7 py-6' : isPill ? 'px-5 py-3.5' : isLarge ? 'px-6 py-5' : 'px-5 py-4'
      }`}
    >
      <HandleDot type="target" position={Position.Left} />
      <HandleDot type="source" position={Position.Right} />
      <HandleDot type="target" position={Position.Top} />
      <HandleDot type="source" position={Position.Bottom} />

      <div className="flex items-start gap-3">
        {isHero ? <BranchMark /> : <span className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${styles.accent}`} />}
        <div className="min-w-0 flex-1">
          {data.eyebrow ? (
            <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-subtle">
              {data.eyebrow}
            </p>
          ) : null}
          <h3
            className={
              data.mono
                ? 'font-mono text-sm font-semibold text-text'
                : isHero
                  ? 'text-2xl font-semibold text-text'
                  : isLarge
                    ? 'text-lg font-semibold text-text'
                  : 'text-sm font-semibold text-text'
            }
          >
            {data.title}
          </h3>
          {data.subtitle ? (
            <p className={isHero ? 'mt-2 text-sm text-muted' : 'mt-1 text-xs leading-5 text-muted'}>
              {data.subtitle}
            </p>
          ) : null}
        </div>
      </div>

      {data.badges?.length ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {data.badges.map((badge) => (
            <span
              key={badge}
              className={`rounded-full border px-2.5 py-1 text-[11px] font-medium ${styles.badge}`}
            >
              {badge}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}
