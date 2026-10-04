'use client';

import { useRef, useState } from 'react';

import { deleteWorkspaceAction } from '@/app/workspace-actions';
import { buttonStyles, fieldStyles } from '@/components/console-ui';
import { FormSubmitButton } from '@/components/form-submit-button';

export function DeleteWorkspaceDialog({
  workspaceId,
  workspaceName,
}: {
  workspaceId: string;
  workspaceName: string;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [confirmation, setConfirmation] = useState('');
  const confirmed = confirmation === workspaceName;

  return (
    <>
      <button
        type="button"
        className={buttonStyles.danger}
        onClick={() => {
          setConfirmation('');
          dialogRef.current?.showModal();
        }}
      >
        Delete workspace
      </button>

      <dialog
        ref={dialogRef}
        className="w-[min(92vw,34rem)] rounded-lg border border-border bg-panel p-0 text-text shadow-2xl backdrop:bg-background/80"
      >
        <div className="border-b border-border px-5 py-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold text-text">Delete workspace</h2>
              <p className="mt-1 text-sm text-muted">
                This permanently removes this workspace and its related records.
              </p>
            </div>
            <form method="dialog">
              <button
                type="submit"
                className="rounded-md border border-border bg-canvas px-2 py-1 text-sm text-muted transition hover:border-borderStrong hover:text-text"
                aria-label="Close delete workspace dialog"
              >
                Close
              </button>
            </form>
          </div>
        </div>

        <form action={deleteWorkspaceAction} className="space-y-4 px-5 py-5">
          <input type="hidden" name="workspace_id" value={workspaceId} />
          <input type="hidden" name="workspace_name" value={workspaceName} />

          <div className="rounded-md border border-danger/30 bg-danger/10 p-3 text-sm text-danger">
            Actions, runs, receipts, approval links, workspace keys, and API keys for this
            workspace will be deleted.
          </div>

          <label htmlFor="workspace_name_confirmation" className="block text-sm font-medium text-text">
            Paste workspace name to confirm
          </label>
          <p className="break-words rounded-md border border-border bg-canvas px-3 py-2 font-mono text-xs text-muted">
            {workspaceName}
          </p>
          <input
            id="workspace_name_confirmation"
            name="workspace_name_confirmation"
            type="text"
            required
            autoComplete="off"
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value)}
            className={fieldStyles}
            placeholder={workspaceName}
          />

          <div className="flex flex-wrap justify-end gap-2 border-t border-border pt-4">
            <button
              type="button"
              className={buttonStyles.secondary}
              onClick={() => dialogRef.current?.close()}
            >
              Cancel
            </button>
            <FormSubmitButton
              label="Delete permanently"
              loadingLabel="Deleting..."
              disabled={!confirmed}
              className={buttonStyles.danger}
            />
          </div>
        </form>
      </dialog>
    </>
  );
}
