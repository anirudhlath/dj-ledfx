// A confirm before something that can't be taken back in one step (§11.3: "Stop all does this for every
// zone after a confirm"), on Base UI's AlertDialog (docs: …/alert-dialog.md): modal, named by its title,
// described by its sentence, Cancel first.
import { AlertDialog } from '@base-ui/react/alert-dialog'
import type { ReactElement } from 'react'
import { Button } from './button'
import { HEAD, SURFACE } from './overlays'

export interface ConfirmDialogProps {
  trigger: ReactElement
  title: string
  description: string
  /** The confirm button's words. */
  confirm: string
  onConfirm: () => void
}

export function ConfirmDialog({ trigger, title, description, confirm, onConfirm }: ConfirmDialogProps) {
  return (
    <AlertDialog.Root>
      <AlertDialog.Trigger render={trigger} />
      <AlertDialog.Portal>
        <AlertDialog.Backdrop className="fixed inset-0 z-40 bg-bg/50" />
        <AlertDialog.Popup className={`fixed top-1/2 left-1/2 z-50 flex w-[min(24rem,calc(100vw-2rem))] -translate-1/2 flex-col gap-3 p-5 ${SURFACE}`}>
          <AlertDialog.Title className={HEAD}>{title}</AlertDialog.Title>
          <AlertDialog.Description className="text-body text-text-2">{description}</AlertDialog.Description>
          <div className="flex justify-end gap-2 pt-1">
            <AlertDialog.Close render={<Button variant="ghost">Cancel</Button>} />
            <AlertDialog.Close
              render={
                <Button variant="danger" onClick={onConfirm}>
                  {confirm}
                </Button>
              }
            />
          </div>
        </AlertDialog.Popup>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  )
}
