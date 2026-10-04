'use client';

import { useState } from 'react';

import { buttonStyles } from '@/components/console-ui';

export function CopyButton({
  value,
  label = 'Copy',
}: {
  value: string;
  label?: string;
}) {
  const [status, setStatus] = useState<'idle' | 'copied' | 'error'>('idle');

  async function onCopy() {
    try {
      await navigator.clipboard.writeText(value);
      setStatus('copied');
      setTimeout(() => setStatus('idle'), 1200);
    } catch {
      setStatus('error');
      setTimeout(() => setStatus('idle'), 1800);
    }
  }

  return (
    <button
      type="button"
      onClick={onCopy}
      className={`${buttonStyles.subtle} px-2.5 py-1.5 text-xs`}
    >
      {status === 'copied' ? 'Copied' : status === 'error' ? 'Copy failed' : label}
    </button>
  );
}
