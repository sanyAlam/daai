'use client';

import {
  Background,
  BackgroundVariant,
  Controls,
  MarkerType,
  ReactFlow,
  type Edge,
  type NodeTypes,
} from '@xyflow/react';

import {
  DaaiDiagramNode,
  type DaaiDiagramNodeData,
  type DaaiFlowNode,
} from '@/components/diagrams/DaaiDiagramNode';
import {
  diagramTone,
  nodeSize,
  type DiagramNodeSize,
  type DiagramTone,
} from '@/components/diagrams/diagramStyles';

export type DaaiDiagramNodeConfig = DaaiDiagramNodeData & {
  id: string;
  x: number;
  y: number;
};

export type DaaiDiagramEdgeConfig = {
  id: string;
  source: string;
  target: string;
  label?: string;
  tone?: DiagramTone;
  dashed?: boolean;
  sourceHandle?: string;
  targetHandle?: string;
};

const nodeTypes = {
  daai: DaaiDiagramNode,
} satisfies NodeTypes;

const layoutScale = 1.28;

function toFlowNode(node: DaaiDiagramNodeConfig): DaaiFlowNode {
  const size: DiagramNodeSize = node.size ?? 'medium';

  return {
    id: node.id,
    type: 'daai',
    position: { x: node.x * layoutScale, y: node.y * layoutScale },
    data: {
      title: node.title,
      subtitle: node.subtitle,
      eyebrow: node.eyebrow,
      tone: node.tone,
      size: node.size,
      badges: node.badges,
      mono: node.mono,
    },
    draggable: false,
    selectable: false,
    style: {
      width: nodeSize[size],
      background: 'transparent',
      border: 'none',
      padding: 0,
    },
  };
}

function toFlowEdge(edge: DaaiDiagramEdgeConfig): Edge {
  const tone = edge.tone ?? 'neutral';
  const color = diagramTone[tone].line;

  return {
    id: edge.id,
    source: edge.source,
    target: edge.target,
    sourceHandle: edge.sourceHandle ?? 'source-right',
    targetHandle: edge.targetHandle ?? 'target-left',
    label: edge.label,
    interactionWidth: 18,
    style: {
      stroke: color,
      strokeWidth: 2.4,
      strokeLinecap: 'round',
      strokeDasharray: edge.dashed ? '8 8' : undefined,
    },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color,
      width: 16,
      height: 16,
    },
    labelStyle: {
      fill: color,
      fontSize: 12,
      fontWeight: 700,
    },
    labelBgStyle: {
      fill: '#151C18',
      fillOpacity: 0.94,
    },
    labelBgPadding: [8, 4],
    labelBgBorderRadius: 999,
  };
}

export function DaaiDiagramCanvas({
  nodes,
  edges,
  height = 520,
  minWidth = 1220,
}: {
  nodes: DaaiDiagramNodeConfig[];
  edges: DaaiDiagramEdgeConfig[];
  height?: number;
  minWidth?: number;
}) {
  const scaledMinWidth = Math.round(minWidth * 1.18);

  return (
    <div className="overflow-x-auto rounded-[28px] border border-borderStrong bg-background p-2 shadow-[0_24px_70px_rgba(0,0,0,0.30)]">
      <div className="rounded-[24px] bg-background" style={{ height, minWidth: scaledMinWidth }}>
        <ReactFlow
          nodes={nodes.map(toFlowNode)}
          edges={edges.map(toFlowEdge)}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.34, maxZoom: 0.72 }}
          minZoom={0.35}
          maxZoom={1.35}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          panOnDrag
          zoomOnScroll={false}
          zoomOnPinch
          zoomOnDoubleClick={false}
          preventScrolling={false}
          proOptions={{ hideAttribution: true }}
          className="daai-diagram-flow rounded-[22px]"
        >
          <Background
            variant={BackgroundVariant.Dots}
            color="#28322D"
            gap={24}
            size={1.8}
          />
          <Controls
            showInteractive={false}
            position="top-right"
            className="daai-diagram-controls"
          />
        </ReactFlow>
      </div>
    </div>
  );
}
