// Live (§8.1, §8.10): the stage, and beside it the Running panel. The stage's code loads on demand,
// keeping three.js out of the first load (§14); its place keeps the stage's background meanwhile, and
// its REST reads start at once rather than when its code arrives. /live/zones/:zoneId is Live with that
// zone's card outlined (F3 decision 23). Between 768 and 1199 px the panel lies over the stage's right
// side and can hide (§4.4, F3 decision 22).
import { usePrefetchQuery } from '@tanstack/react-query'
import { lazy, Suspense, useState } from 'react'
import { useParams } from 'react-router'
import type { Id } from '@/api/contract'
import { queries } from '@/api/queries'
import { usePreviewOnly } from '@/chrome/hooks'
import { Button } from '@/design/button'
import { LIVE_SPEC } from '@/design/live-numbers'
import { useIsPhone, useMediaQuery } from '@/lib/use-media-query'
import { EmptyHome } from '@/live/empty-home'
import { PhoneRunning } from '@/live/phone-live'
import { PreviewOnlyLabel } from '@/live/preview-only'
import { ReconnectingCard } from '@/live/reconnecting'
import { RunningPanel } from '@/live/running-panel'
import { ZoneDetail } from '@/live/zone-detail'
import { StagePending } from '@/stage/stage-pending'

const Stage = lazy(() => import('@/stage/stage'))

/** §4.4: below LIVE_SPEC.widePx the Running panel stops sitting beside the stage. */
const NARROW_QUERY = `(width < ${LIVE_SPEC.widePx / 16}rem)`

/** The narrow panel: shown, hidden, or shown again from the stage's Running button (Hide takes the focus). */
type NarrowPanel = 'open' | 'hidden' | 'reopened'

export function LivePage() {
  usePrefetchQuery(queries.home())
  usePrefetchQuery(queries.lights())
  usePrefetchQuery(queries.zones())
  usePrefetchQuery(queries.looks())
  const { zoneId } = useParams()
  const phone = useIsPhone()
  const narrow = useMediaQuery(NARROW_QUERY)
  const previewOnly = usePreviewOnly() === true
  const [panel, setPanel] = useState<NarrowPanel>('open')
  const [hovered, setHovered] = useState<Id | null>(null)
  const [named, setNamed] = useState(zoneId)
  if (zoneId !== named) {
    // React's way to adjust state to a prop: a zone named while the panel is hidden brings it back.
    setNamed(zoneId)
    if (zoneId !== undefined && panel === 'hidden') setPanel('open')
  }
  const stage = (
    <Suspense fallback={<StagePending />}>
      <Stage variant={phone ? 'phone' : 'desktop'} outlined={phone ? null : (hovered ?? zoneId ?? null)} focus={phone ? (zoneId ?? null) : null} />
    </Suspense>
  )
  if (phone) {
    return (
      <div className="flex min-h-full flex-col">
        <div className="relative shrink-0" style={{ aspectRatio: `${LIVE_SPEC.phoneStage.width} / ${LIVE_SPEC.phoneStage.height}` }}>
          {stage}
        </div>
        {zoneId === undefined ? <PhoneRunning /> : <ZoneDetail zoneId={zoneId} />}
      </div>
    )
  }
  return (
    <div className="relative flex h-full min-h-0">
      <div className="relative min-w-0 flex-1">
        {stage}
        {previewOnly && <PreviewOnlyLabel />}
        <ReconnectingCard variant="desktop" />
        <EmptyHome variant="desktop" />
      </div>
      {!narrow && <RunningPanel selected={zoneId} className="w-(--live-panel-w) shrink-0" onZoneHover={setHovered} />}
      {narrow && panel !== 'hidden' && (
        <RunningPanel
          selected={zoneId}
          className="absolute inset-y-0 right-0 z-20 w-(--live-panel-w) shadow-pop"
          onHide={() => setPanel('hidden')}
          onZoneHover={setHovered}
          focusHide={panel === 'reopened'}
        />
      )}
      {narrow && panel === 'hidden' && (
        <Button icon="left" autoFocus className="absolute top-1/2 right-4 z-20 -translate-y-1/2 shadow-pop" onClick={() => setPanel('reopened')}>
          Running
        </Button>
      )}
    </div>
  )
}
