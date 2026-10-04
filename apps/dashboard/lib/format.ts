export function formatTimestamp(value: string | null): string {
  if (!value) {
    return 'N/A';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

export function formatJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

export function formatPayloadPreview(value: unknown, max = 120): string {
  const compact = JSON.stringify(value);
  if (!compact) {
    return '{}';
  }
  if (compact.length <= max) {
    return compact;
  }
  return `${compact.slice(0, max - 3)}...`;
}
