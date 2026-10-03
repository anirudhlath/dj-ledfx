// Phone-Live's list under the stage (§8.10): "Running" and its summary, or preview only's banner in its
// place; Reconnecting's card; the empty homes; an overlay, then the zones newest first (F3 decision 1),
// each linking to its Zone detail; Nothing running; and the sticky Put a look on over the tab bar. While
// the link is down the cards are dimmed and inert, and Put a look on goes (Phone-State-Reconnecting draws
// none). Look: Phone-Live.html and Phone-State-*.html, whose head and banner run up into the stage's foot.
import { useMemo } from 'react'
import type { Overlay } from '@/api/contract'
import { useLive } from '@/api/live-store'
import { useConnectionStatus, usePreviewOnly } from '@/chrome/hooks'
import { ButtonLink } from '@/design/button'
import { LIVE_SPEC } from '@/design/live-numbers'
import { useNow } from '@/lib/use-now'
import { newestFirst } from '@/stage/show'
import { OverlayCard } from '@/zones/overlay-card'
import { PhoneZoneCard } from '@/zones/phone-zone-card'
import { useZoneWorld } from '@/zones/use-zone-world'
import { chipsFor, zoneView } from '@/zones/zone-view'
import { EmptyHome } from './empty-home'
import { NothingRunning } from './nothing-running'
import { PreviewOnlyBanner } from './preview-only'
import { ReconnectingCard } from './reconnecting'
import { runningSummary } from './words'

const NO_OVERLAYS: readonly Overlay[] = []

export function PhoneRunning() {
  const world = useZoneWorld()
  const running = useLive((state) => state.running?.zones ?? null)
  const overlays = useLive((state) => state.running?.overlays ?? NO_OVERLAYS)
  const previewOnly = usePreviewOnly()
  const frozen = useConnectionStatus() === 'reconnecting'
  const now = useNow()
  const zones = useMemo(() => (running === null ? [] : newestFirst(running)), [running])
  const something = zones.length > 0 || overlays.length > 0
  const nothing = running !== null && !something
  const on = nothing ? [...world.states.values()].filter((state) => state.power === true).length : 0
  // §9.4 Reconnecting: "cards at 45% opacity and inert", as on desktop.
  const still = frozen ? { inert: true, style: { opacity: LIVE_SPEC.frozenCardsOpacity } } : {}
  return (
    <>
      <div className="relative z-10 flex flex-col gap-2.5 px-4 pt-3 pb-4">
        {previewOnly === true ? (
          <PreviewOnlyBanner className="-mt-12.5" />
        ) : (
          something &&
          !frozen && (
            <div className="-mt-9 flex items-baseline justify-between gap-2">
              <h2 className="text-[14px] font-semibold">Running</h2>
              <span className="truncate text-meta text-text-3">{runningSummary(zones, overlays.length, world.lightCount, previewOnly)}</span>
            </div>
          )
        )}
        <ReconnectingCard variant="phone" />
        <EmptyHome variant="phone" />
        {(something || nothing) && (
          <div className="flex flex-col gap-2.5" {...still}>
            {overlays.map((overlay) => {
              const look = world.looks.get(overlay.lookId)
              return <OverlayCard key={`${overlay.lookId}:${overlay.endsAt}`} overlay={overlay} inputs={look === undefined ? [] : chipsFor(look)} />
            })}
            {zones.map((zone) => (
              <PhoneZoneCard key={zone.zoneId} running={zone} view={zoneView(zone, world, now, true)} />
            ))}
            {nothing && <NothingRunning on={on} total={world.lightCount} variant="phone" />}
          </div>
        )}
      </div>
      {!frozen && (
        <div className="sticky bottom-0 z-20 mt-auto bg-linear-to-t from-bg from-60% to-bg/0 px-4 pt-7 pb-3">
          <ButtonLink variant="primary" size="cta" icon="plus" to="/live/put" className="w-full">
            Put a look on
          </ButtonLink>
        </div>
      )}
    </>
  )
}
