import { Dialog as BaseDialog } from '@base-ui/react/dialog'
import { Popover as BasePopover } from '@base-ui/react/popover'
import { Tooltip as BaseTooltip } from '@base-ui/react/tooltip'
import type { ReactElement, ReactNode } from 'react'
import { IconButton } from './button'

interface OverlayProps {
  /** The element that opens it; Base UI wires its events and ARIA. */
  trigger: ReactElement
  /** Names the overlay for assistive tech and heads it. */
  title: string
  children?: ReactNode
  open?: boolean
  onOpenChange?: (open: boolean) => void
}

export interface TooltipProps {
  content: ReactNode
  /**
   * The element it describes. Give icon-only triggers an aria-label: the tooltip is visual only,
   * and its popup stays out of the accessibility tree.
   */
  children: ReactElement
  side?: 'top' | 'right' | 'bottom' | 'left'
}

/** §6.1 Tooltip's box: the stage's light tooltip (F2) draws the same one. */
export const TOOLTIP_SURFACE =
  'flex max-w-72 flex-col gap-1.25 rounded-tile border border-line-strong bg-raised/94 px-3 py-2.5 text-meta text-text shadow-tip'

/** §6.1 Tooltip. */
export function Tooltip({ content, children, side = 'top' }: TooltipProps) {
  return (
    <BaseTooltip.Root>
      <BaseTooltip.Trigger render={children} />
      <BaseTooltip.Portal>
        <BaseTooltip.Positioner side={side} sideOffset={6} className="z-50">
          <BaseTooltip.Popup aria-hidden="true" className={TOOLTIP_SURFACE}>
            {content}
          </BaseTooltip.Popup>
        </BaseTooltip.Positioner>
      </BaseTooltip.Portal>
    </BaseTooltip.Root>
  )
}

/** What every popup's surface is. */
export const SURFACE = 'rounded-card border border-line-strong bg-raised shadow-pop outline-none'
/** A popup's title. */
export const HEAD = 'text-section font-semibold text-text'

/**
 * §6.1 Popover: anchored to its trigger. `width` in px, never wider than the viewport allows; `aside` sits
 * at the title row's end (the attention popover's count, §6.2, State-Problems).
 */
export function Popover({
  trigger,
  title,
  children,
  open,
  onOpenChange,
  align = 'center',
  width,
  aside,
}: OverlayProps & { align?: 'start' | 'center' | 'end'; width?: number; aside?: ReactNode }) {
  return (
    <BasePopover.Root open={open} onOpenChange={onOpenChange}>
      <BasePopover.Trigger render={trigger} />
      <BasePopover.Portal>
        <BasePopover.Positioner sideOffset={8} align={align} collisionPadding={16} className="z-50">
          <BasePopover.Popup
            className={`flex max-h-(--available-height) max-w-[calc(100vw-2rem)] flex-col overflow-hidden ${SURFACE}`}
            style={width === undefined ? undefined : { width }}
          >
            <div className="flex shrink-0 items-baseline justify-between gap-2 px-3.5 py-3">
              <BasePopover.Title className={HEAD}>{title}</BasePopover.Title>
              {aside}
            </div>
            <div className="min-h-0 overflow-y-auto">{children}</div>
          </BasePopover.Popup>
        </BasePopover.Positioner>
      </BasePopover.Portal>
    </BasePopover.Root>
  )
}

/** Dialog and Sheet: a modal Base UI dialog over the dimmed page; `className` places the popup. */
function Modal({ trigger, open, onOpenChange, className, children }: Omit<OverlayProps, 'title'> & { className: string }) {
  return (
    <BaseDialog.Root open={open} onOpenChange={onOpenChange}>
      <BaseDialog.Trigger render={trigger} />
      <BaseDialog.Portal>
        <BaseDialog.Backdrop className="fixed inset-0 z-40 bg-bg/50" />
        <BaseDialog.Popup className={className}>{children}</BaseDialog.Popup>
      </BaseDialog.Portal>
    </BaseDialog.Root>
  )
}

/** §6.1 Dialog: centred and modal. */
export function Dialog({ title, children, ...modal }: OverlayProps) {
  return (
    <Modal {...modal} className={`fixed top-1/2 left-1/2 z-50 flex w-[min(28rem,calc(100vw-2rem))] -translate-1/2 flex-col gap-3 p-5 ${SURFACE}`}>
      <div className="flex items-start justify-between gap-4">
        <BaseDialog.Title className={HEAD}>{title}</BaseDialog.Title>
        <BaseDialog.Close render={<IconButton icon="x" label="Close" />} />
      </div>
      {children}
    </Modal>
  )
}

/**
 * §6.1 Sheet: the phone's bottom sheet, with a grabber, its title (Phone-State-Problems: `aside` beside
 * it, the count) and a Close at the row's end.
 */
export function Sheet({ title, aside, children, ...modal }: OverlayProps & { aside?: ReactNode }) {
  return (
    <Modal
      {...modal}
      className="fixed inset-x-0 bottom-0 z-50 flex max-h-[85dvh] flex-col gap-1 overflow-y-auto rounded-t-sheet border-t border-line bg-panel px-4 pt-2 pb-[max(1rem,env(safe-area-inset-bottom))] shadow-sheet outline-none"
    >
      <span aria-hidden="true" className="mx-auto mb-1.5 h-1.25 w-10 shrink-0 rounded-[3px] bg-line-strong" />
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-baseline gap-1">
          <BaseDialog.Title className="text-title font-semibold text-text">{title}</BaseDialog.Title>
          {aside}
        </div>
        <BaseDialog.Close render={<IconButton icon="x" label="Close" />} />
      </div>
      {children}
    </Modal>
  )
}
