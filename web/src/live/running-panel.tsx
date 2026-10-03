// §8.1's Running panel: the header ("Running · 3 zones · all 19 lights" + Stop all), an overlay over
// everything on top, then the zones newest first (F3 decision 1), collapsed in two steps when they don't
// fit (decision 2), and the footer's Put a look on. Nothing running is §9.4's. The zone /live/zones/:zoneId
// names is outlined, collapses last and scrolls into view (decision 23). It reads the live store a slice at
// a time; the frames reach only the swatches. Look and layout: Main.html's and State-Nothing-Running.html's.
import { useEffect, useMemo } from 'react'
import { failureText, stopAll } from '@/api/actions'
import type { Id, Overlay } from '@/api/contract'
import { useLive } from '@/api/live-store'
import { usePreviewOnly } from '@/chrome/hooks'
import { useAnnounce } from '@/design/announce'
import { Button, ButtonLink, IconButton } from '@/design/button'
import { ConfirmDialog } from '@/design/confirm-dialog'
import { cx } from '@/design/cx'
import { useNow } from '@/lib/use-now'
import { newestFirst } from '@/stage/show'
import { OverlayCard } from '@/zones/overlay-card'
import { useZoneWorld } from '@/zones/use-zone-world'
import { ZoneCard } from '@/zones/zone-card'
import { ZoneRow } from '@/zones/zone-row'
import { chipsFor, zoneView } from '@/zones/zone-view'
import { collapseKey, shapesAt, useCollapse } from './collapse'
import { NothingRunning } from './nothing-running'
import { TapeBar } from './preview-only'
import { runningSummary } from './words'

const NO_OVERLAYS: readonly Overlay[] = []

export interface RunningPanelProps {
  /** The zone /live/zones/:zoneId names (F3 decision 23). */
  selected?: Id
  className?: string
  /** Between 768 and 1199 px the panel can hide (F3 decision 22). */
  onHide?: () => void
  /** Hide takes the focus: the panel came back from the stage's Running button. */
  focusHide?: boolean
  /** The zone of the card or row under the pointer or the focus; null when it leaves (§8.1). */
  onZoneHover?: (zoneId: Id | null) => void
}

export function RunningPanel({ selected, className, onHide, focusHide = false, onZoneHover }: RunningPanelProps) {
  const world = useZoneWorld()
  const running = useLive((state) => state.running?.zones ?? null)
  const overlays = useLive((state) => state.running?.overlays ?? NO_OVERLAYS)
  const previewOnly = usePreviewOnly()
  const now = useNow()
  const announce = useAnnounce()
  const zones = useMemo(() => (running === null ? [] : newestFirst(running)), [running])
  // Taken apart: the React Compiler would take the whole object for a ref once one of its callbacks is a ref.
  const { box, list: listRef, listElement: list, step } = useCollapse(collapseKey(zones, selected), zones.length)
  const shapes = shapesAt(zones, step, selected)
  useEffect(() => {
    if (selected === undefined || list === null) return
    const card = [...list.querySelectorAll<HTMLElement>('[data-zone]')].find((item) => item.dataset.zone === selected)
    card?.scrollIntoView?.({ block: 'nearest' })
  }, [selected, list, step])

  const stop = () => {
    stopAll().catch((error: unknown) => announce(failureText('stop all', error)))
  }
  const hover = (target: EventTarget) =>
    onZoneHover?.(target instanceof Element ? (target.closest<HTMLElement>('[data-zone]')?.dataset.zone ?? null) : null)
  const something = zones.length > 0
  const nothing = running !== null && !something && overlays.length === 0
  const on = nothing ? [...world.states.values()].filter((state) => state.power === true).length : 0
  return (
    <aside
      aria-label="Running"
      className={cx('flex min-h-0 flex-col border-l border-line-soft bg-panel', className)}
      onPointerOver={(event) => hover(event.target)}
      onPointerLeave={() => onZoneHover?.(null)}
      onFocus={(event) => hover(event.target)}
      onBlur={() => onZoneHover?.(null)}
    >
      {/* Every render's header: 10 px between the title and the summary; State-Preview-Only's starts 14 px down
          to make room for the tape bar under its row. */}
      <div
        className={cx(
          'flex flex-col gap-2 px-5',
          previewOnly === true ? 'pt-3.5' : 'pt-4',
          (something || previewOnly === true) && 'pb-3',
        )}
      >
        <div className="flex items-center justify-between gap-2">
          <div className="flex min-w-0 items-baseline gap-2.5">
            <h2 className="text-section font-semibold">Running</h2>
            {something && (
              <span className="truncate text-data text-text-3">{runningSummary(zones, overlays.length, world.lightCount, previewOnly)}</span>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-1">
            {something && (
              <ConfirmDialog
                trigger={
                  <Button variant="ghost" size="sm" icon="power">
                    Stop all
                  </Button>
                }
                title="Stop all?"
                description="Every zone's look stops, and each light goes back to how it was."
                confirm="Stop all"
                onConfirm={stop}
              />
            )}
            {onHide !== undefined && <IconButton icon="x" label="Hide Running" onClick={onHide} autoFocus={focusHide} />}
          </div>
        </div>
        {previewOnly === true && <TapeBar />}
      </div>
      <div ref={box} className="min-h-0 grow overflow-y-auto px-4">
        <div ref={listRef} className="flex flex-col gap-3">
          {overlays.map((overlay) => {
            const look = world.looks.get(overlay.lookId)
            return <OverlayCard key={`${overlay.lookId}:${overlay.endsAt}`} overlay={overlay} inputs={look === undefined ? [] : chipsFor(look)} />
          })}
          {zones.map((zone) => {
            const shape = shapes.get(zone.zoneId) ?? 'card'
            const view = zoneView(zone, world, now, shape !== 'card')
            return shape === 'row' ? (
              <ZoneRow key={zone.zoneId} view={view} to={`/live/zones/${encodeURIComponent(zone.zoneId)}`} />
            ) : (
              <ZoneCard key={zone.zoneId} running={zone} view={view} compact={shape === 'compact'} outlined={zone.zoneId === selected} />
            )
          })}
          {nothing && <NothingRunning on={on} total={world.lightCount} />}
        </div>
      </div>
      <div className="flex flex-col gap-2.5 border-t border-line-soft px-5 pt-4 pb-5">
        <ButtonLink variant="primary" size="lg" icon="plus" to="/live/put" className="w-full">
          Put a look on
        </ButtonLink>
        {/* F3 decision 34: the sentence goes while the cards are squeezed. */}
        {something && step === 0 && <p className="text-center text-meta text-text-3">or click a room in the home</p>}
      </div>
    </aside>
  )
}
