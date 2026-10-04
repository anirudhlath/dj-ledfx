// §6.2 AttentionPopover (desktop, anchored under the button) and AttentionSheet (phone): the server's
// items (§9.5) in its order, each with its icon, title, explanation and actions (F3 decisions 14, 15
// and 32). The items are read only while the list is open, so a new snapshot redraws nothing else.
import { useState, type ReactElement } from 'react'
import { failureText, restartZone } from '@/api/actions'
import type { AttentionItem, RunningZone } from '@/api/contract'
import { useLive } from '@/api/live-store'
import { useAnnounce } from '@/design/announce'
import { Button, ButtonLink } from '@/design/button'
import { cx } from '@/design/cx'
import { Icon } from '@/design/icon'
import { LIVE_SPEC } from '@/design/live-numbers'
import { Popover, Sheet } from '@/design/overlays'
import { attentionActions, attentionLook, type AttentionAction } from './attention'

export interface AttentionListProps {
  /** The AttentionButton that opens it. */
  trigger: ReactElement
  count: number
  open: boolean
  onOpenChange: (open: boolean) => void
}

type Size = 'desktop' | 'phone'

const TITLE = 'Needs attention'
const NO_ITEMS: readonly AttentionItem[] = []
const NO_ZONES: readonly RunningZone[] = []

/** State-Problems: LIVE_SPEC.attentionPopoverPx wide, under the button, its count at the title row's end. */
export function AttentionPopover({ trigger, count, open, onOpenChange }: AttentionListProps) {
  return (
    <Popover
      trigger={trigger}
      title={TITLE}
      open={open}
      onOpenChange={onOpenChange}
      width={LIVE_SPEC.attentionPopoverPx}
      aside={<span className="num text-meta text-signal">{count}</span>}
    >
      <AttentionItems size="desktop" onNavigate={() => onOpenChange(false)} />
    </Popover>
  )
}

/** Phone-State-Problems: a sheet, the count beside its title, one action a row. */
export function AttentionSheet({ trigger, count, open, onOpenChange }: AttentionListProps) {
  return (
    <Sheet
      trigger={trigger}
      title={TITLE}
      open={open}
      onOpenChange={onOpenChange}
      aside={<span className="num text-title font-semibold text-signal">{count}</span>}
    >
      <AttentionItems size="phone" onNavigate={() => onOpenChange(false)} />
    </Sheet>
  )
}

function AttentionItems({ size, onNavigate }: { size: Size; onNavigate: () => void }) {
  const items = useLive((state) => state.attention ?? NO_ITEMS)
  const running = useLive((state) => state.running?.zones ?? NO_ZONES)
  if (items.length === 0) {
    // F3 decision 36: the desktop button reads All good and still opens the list.
    return <p className="border-t border-line-soft px-3.5 py-3 text-meta text-text-3">Nothing needs attention.</p>
  }
  return (
    <ul>
      {items.map((item) => (
        <AttentionRow key={item.id} item={item} actions={attentionActions(item, running)} size={size} onNavigate={onNavigate} />
      ))}
    </ul>
  )
}

interface RowProps {
  item: AttentionItem
  actions: AttentionAction[]
  size: Size
  onNavigate: () => void
}

function AttentionRow({ item, actions, size, onNavigate }: RowProps) {
  const { icon, tone } = attentionLook(item)
  const desktop = size === 'desktop'
  const toneClass = tone === 'signal' ? 'text-signal' : 'text-text-3'
  return (
    <li className={desktop ? 'flex gap-3 border-t border-line-soft px-3.5 py-3' : 'flex min-h-15 items-center gap-3 border-t border-line-soft py-2'}>
      <Icon name={icon} size={desktop ? 16 : 18} className={toneClass} />
      <div className={cx('flex min-w-0 grow flex-col', desktop ? 'gap-1.5' : 'gap-0.5')}>
        <span className={cx('font-semibold text-text', desktop ? 'text-size-control' : 'text-[14px]')}>{item.title}</span>
        <span className={cx('text-meta text-text-2', desktop && 'leading-[1.45]')}>{item.detail}</span>
        {desktop && actions.length > 0 && (
          <div className="flex gap-1.5">
            {actions.slice(0, 2).map((action, i) => (
              <ActionButton key={action.label} action={action} variant={i === 0 ? 'secondary' : 'ghost'} size="sm" onNavigate={onNavigate} />
            ))}
          </div>
        )}
      </div>
      {!desktop && actions.length > 0 && <ActionButton action={actions[0]} variant="secondary" size="md" onNavigate={onNavigate} />}
    </li>
  )
}

interface ActionProps {
  action: AttentionAction
  variant: 'secondary' | 'ghost'
  size: 'sm' | 'md'
  onNavigate: () => void
}

function ActionButton({ action, variant, size, onNavigate }: ActionProps) {
  const announce = useAnnounce()
  const [busy, setBusy] = useState(false)
  if (action.kind === 'link') {
    return (
      <ButtonLink to={action.to} variant={variant} size={size} onClick={onNavigate}>
        {action.label}
      </ButtonLink>
    )
  }
  const restart = async () => {
    setBusy(true)
    try {
      await restartZone(action.zoneId)
    } catch (error) {
      announce(failureText(`restart ${action.lookName}`, error))
    } finally {
      setBusy(false)
    }
  }
  return (
    <Button variant={variant} size={size} icon="refresh" disabled={busy} onClick={() => void restart()}>
      {action.label}
    </Button>
  )
}
