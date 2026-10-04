'use client';

import { useFormStatus } from 'react-dom';

export function FormSubmitButton({
  label,
  loadingLabel,
  className,
  disabled = false,
}: {
  label: string;
  loadingLabel?: string;
  className: string;
  disabled?: boolean;
}) {
  const { pending } = useFormStatus();
  const isDisabled = pending || disabled;

  return (
    <button
      type="submit"
      disabled={isDisabled}
      className={`${className} disabled:cursor-not-allowed disabled:border-border disabled:bg-panelHover disabled:text-subtle`}
    >
      {pending ? loadingLabel ?? 'Saving...' : label}
    </button>
  );
}
