// The chrome's parts on the live store. Each reads its own slice (hooks.ts), so a beat redraws the
// tempo module and nothing else, and each draws nothing until its data has arrived.
import { AttentionButton } from './attention-button'
import { ConnectionIndicator } from './connection-indicator'
import { useAttentionCounts, useConnection, usePreviewOnly, useTempo } from './hooks'
import { PreviewOnlySwitch } from './preview-only-switch'
import { TempoModule } from './tempo-module'

type Variant = 'bar' | 'header'

/** The top bar's tempo module, and the divider after it. */
export function ChromeTempo() {
  const tempo = useTempo()
  if (tempo === null) return null
  return (
    <>
      <TempoModule variant="bar" {...tempo} />
      <span aria-hidden="true" className="h-6 w-px bg-line tablet:hidden" />
    </>
  )
}

/** The phone's tempo strip under the header, on Live. */
export function ChromeTempoStrip() {
  const tempo = useTempo()
  if (tempo === null) return null
  return (
    <div className="mx-4 mt-1.5">
      <TempoModule variant="strip" {...tempo} />
    </div>
  )
}

export function ChromePreviewOnly({ variant }: { variant: Variant }) {
  return <PreviewOnlySwitch variant={variant} on={usePreviewOnly()} />
}

export function ChromeAttention({ variant }: { variant: Variant }) {
  const counts = useAttentionCounts()
  if (counts === null) return null
  return <AttentionButton variant={variant} count={counts.total} />
}

export function ChromeConnection({ variant }: { variant: Variant }) {
  return <ConnectionIndicator variant={variant} connection={useConnection()} />
}
