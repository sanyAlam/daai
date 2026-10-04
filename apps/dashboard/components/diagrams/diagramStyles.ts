export type DiagramTone = 'neutral' | 'brand' | 'approval' | 'success' | 'danger' | 'muted' | 'info';
export type DiagramNodeSize = 'label' | 'pill' | 'small' | 'medium' | 'large' | 'hero';

export const diagramTone = {
  neutral: {
    line: '#6E7681',
    border: 'border-border',
    bg: 'bg-panel',
    text: 'text-text',
    accent: 'bg-subtle',
    badge: 'border-borderStrong bg-canvas text-muted',
  },
  brand: {
    line: '#3ECF8E',
    border: 'border-brand/50',
    bg: 'bg-panel',
    text: 'text-text',
    accent: 'bg-brand',
    badge: 'border-brand/40 bg-brand/10 text-brand',
  },
  approval: {
    line: '#F2B84B',
    border: 'border-warning/50',
    bg: 'bg-panel',
    text: 'text-text',
    accent: 'bg-warning',
    badge: 'border-warning/40 bg-warning/10 text-warning',
  },
  success: {
    line: '#3ECF8E',
    border: 'border-success/50',
    bg: 'bg-panel',
    text: 'text-text',
    accent: 'bg-success',
    badge: 'border-success/40 bg-success/10 text-success',
  },
  danger: {
    line: '#F87171',
    border: 'border-danger/50',
    bg: 'bg-panel',
    text: 'text-text',
    accent: 'bg-danger',
    badge: 'border-danger/40 bg-danger/10 text-danger',
  },
  muted: {
    line: '#8B949E',
    border: 'border-borderStrong',
    bg: 'bg-panel',
    text: 'text-text',
    accent: 'bg-muted',
    badge: 'border-borderStrong bg-canvas text-muted',
  },
  info: {
    line: '#7DD3FC',
    border: 'border-info/50',
    bg: 'bg-panel',
    text: 'text-text',
    accent: 'bg-info',
    badge: 'border-info/40 bg-info/10 text-info',
  },
} satisfies Record<DiagramTone, {
  line: string;
  border: string;
  bg: string;
  text: string;
  accent: string;
  badge: string;
}>;

export const nodeSize = {
  label: 180,
  pill: 230,
  small: 220,
  medium: 260,
  large: 320,
  hero: 400,
} satisfies Record<DiagramNodeSize, number>;
