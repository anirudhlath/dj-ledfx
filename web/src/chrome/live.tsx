// The chrome's parts on the live store. Each reads its own slice (hooks.ts), so a message redraws only the
// part whose slice it changes (a beat, none: the pip writer draws the pips), and each draws nothing until
// its data has arrived. TAP sends a tap and the source button opens the tempo source popover.
import { useCallback, useState, type ReactElement } from 'react'
import { failureText, tapTempo } from '@/api/actions'
import { useAnnounce } from '@/design/announce'
import { AttentionButton } from './attention-button'
import { AttentionPopover, AttentionSheet } from './attention-list'
import { ConnectionIndicator } from './connection-indicator'
import { useAttentionTotal, useConnection, useConnectionUnlessLive, useHoldNews, usePreviewOnly, useTempo } from './hooks'
import { usePreviewControl } from './preview-control'
import { PreviewOnlySwitch } from './preview-only-switch'
import { TempoModule } from './tempo-module'
import { TempoSourcePopover } from './tempo-source'

type Variant = 'bar' | 'header'

/** TAP (F3 decision 5): a tap, and what failed if it did (Review Focus 1). */
function useTapTempo(): () => void {
  const announce = useAnnounce()
  return useCallback(() => {
    tapTempo().catch((error: unknown) => announce(failureText('tap the tempo', error)))
  }, [announce])
}

/** The source button opens the tempo source popover (desktop). One function, so the module's props stay equal. */
const sourcePopover = (source: ReactElement) => <TempoSourcePopover trigger={source} />

/** The hold's news (F3 decision 6), said once for the whole app. */
export function ChromeHoldNews() {
  useHoldNews()
  return null
}

/** The top bar's tempo module, and the divider after it. */
export function ChromeTempo() {
  const tempo = useTempo()
  const onTap = useTapTempo()
  if (tempo === null) return null
  return (
    <>
      <TempoModule variant="bar" {...tempo} onTap={onTap} renderSource={sourcePopover} />
      <span aria-hidden="true" className="h-6 w-px bg-line tablet:hidden" />
    </>
  )
}

/** The phone's tempo strip under the header, on Live. */
export function ChromeTempoStrip() {
  const tempo = useTempo()
  const onTap = useTapTempo()
  if (tempo === null) return null
  return (
    <div className="mx-4 mt-1.5">
      <TempoModule variant="strip" {...tempo} onTap={onTap} />
    </div>
  )
}

export function ChromePreviewOnly({ variant }: { variant: Variant }) {
  const on = usePreviewOnly()
  const control = usePreviewControl()
  if (on === null) return null
  return <PreviewOnlySwitch variant={variant} on={on} onChange={control.change} disabled={control.pending} />
}

/** §6.2: the button, and what it opens: the popover on desktop, the sheet on the phone. */
export function ChromeAttention({ variant }: { variant: Variant }) {
  const total = useAttentionTotal()
  const [open, setOpen] = useState(false)
  if (total === null) return null
  const button = <AttentionButton variant={variant} count={total} />
  return variant === 'bar' ? (
    <AttentionPopover trigger={button} count={total} open={open} onOpenChange={setOpen} />
  ) : (
    <AttentionSheet trigger={button} count={total} open={open} onOpenChange={setOpen} />
  )
}

export function ChromeConnection({ variant }: { variant: Variant }) {
  return variant === 'bar' ? <BarConnection /> : <HeaderConnection />
}

/** The top bar's "Live 60 fps": it follows the frame rate. */
function BarConnection() {
  return <ConnectionIndicator variant="bar" connection={useConnection()} />
}

/** The phone header shows the link only while it isn't live, so a new frame rate redraws nothing. */
function HeaderConnection() {
  const connection = useConnectionUnlessLive()
  if (connection === null) return null
  return <ConnectionIndicator variant="header" connection={connection} />
}
