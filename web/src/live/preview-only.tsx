// §5.6's tape, which makes preview only impossible to miss: a frame round the window, a bar under the
// Running panel's header, and on the stage a label with the way back (State-Preview-Only). The phone has a
// banner under its stage instead (Phone-State-Preview-Only). Each reads the server's preview only itself, so
// nothing around it redraws when it changes. They're plain blocks: the page keeps one status region.
import { usePreviewOnly } from '@/chrome/hooks'
import { usePreviewControl } from '@/chrome/preview-control'
import { Button } from '@/design/button'
import { cx } from '@/design/cx'
import { LIVE_SPEC } from '@/design/live-numbers'
import { useIsPhone } from '@/lib/use-media-query'

/** The frame on all four edges of the window, thinner on the phone. */
export function TapeFrame() {
  const on = usePreviewOnly()
  const phone = useIsPhone()
  if (on !== true) return null
  const px = phone ? LIVE_SPEC.tape.phoneFramePx : LIVE_SPEC.tape.framePx
  return (
    <div aria-hidden="true" data-tape="frame" className="pointer-events-none fixed inset-0 z-60">
      <div className="tape absolute inset-x-0 top-0" style={{ height: px }} />
      <div className="tape absolute inset-x-0 bottom-0" style={{ height: px }} />
      <div className="tape absolute inset-y-0 left-0" style={{ width: px }} />
      <div className="tape absolute inset-y-0 right-0" style={{ width: px }} />
    </div>
  )
}

/** The bar under the Running panel's header row. */
export function TapeBar() {
  return <span aria-hidden="true" data-tape="bar" className="tape block rounded-[2px]" style={{ height: LIVE_SPEC.tape.panelBarPx }} />
}

/** The stage's label, centred at its top, with the way back to the lights. */
export function PreviewOnlyLabel() {
  const control = usePreviewControl()
  return (
    <div className="absolute top-4.5 left-1/2 z-10 flex h-11 -translate-x-1/2 items-center gap-3 rounded-control border-2 border-text bg-bg pr-1.5 pl-1">
      <span aria-hidden="true" className="tape block h-8 w-10 shrink-0 rounded-[5px]" />
      <div className="flex flex-col whitespace-nowrap">
        <span className="text-data font-bold tracking-[0.08em] uppercase">Preview only</span>
        <span className="text-meta text-text-2">Everything renders here. Nothing is sent to the lights.</span>
      </div>
      <Button variant="primary" size="sm" disabled={control.pending} onClick={() => control.change(false)}>
        Send to lights again
      </Button>
    </div>
  )
}

/** The phone's banner under the stage. */
export function PreviewOnlyBanner({ className }: { className?: string }) {
  const control = usePreviewControl()
  return (
    <div className={cx('flex items-center gap-2.5 rounded-tile border-2 border-text bg-bg p-2', className)}>
      <span aria-hidden="true" className="tape block size-7.5 shrink-0 rounded-[5px]" />
      <div className="flex grow flex-col">
        <span className="text-meta font-bold tracking-[0.08em] uppercase">Preview only</span>
        <span className="text-[11.5px] text-text-2">Nothing is sent to the lights</span>
      </div>
      <Button variant="primary" size="sm" aria-label="Turn off preview only" disabled={control.pending} onClick={() => control.change(false)}>
        Turn off
      </Button>
    </div>
  )
}
