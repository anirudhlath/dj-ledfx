// Live (§8.1, §8.10): the stage, and beside it the Running panel. The stage's code loads on demand,
// keeping three.js out of the first load (§14); its place keeps the stage's background meanwhile, and
// its REST reads start at once rather than when its code arrives. /live/zones/:zoneId is Live with that
// zone's card outlined (F3 decision 23); /live/put is Live with the composer in the panel's place and the
// stage in `compose` mode (§8.2), which `L` opens and Esc closes. Between 768 and 1199 px the panel lies
// over the stage's right side and can hide (§4.4, F3 decision 22); the composer lies there too.
import { usePrefetchQuery } from '@tanstack/react-query'
import { lazy, Suspense, useEffect, useRef, useState, type CSSProperties } from 'react'
import { useMatch, useParams } from 'react-router'
import type { Id } from '@/api/contract'
import { queries } from '@/api/queries'
import { usePreviewOnly } from '@/chrome/hooks'
import { ComposerPanel, ComposerWhere } from '@/compose/composer-panel'
import { useStageCompose } from '@/compose/use-composer'
import { useComposerKeys } from '@/compose/use-composer-keys'
import { Button } from '@/design/button'
import { LIVE_SPEC } from '@/design/live-numbers'
import { useIsPhone, useMediaQuery } from '@/lib/use-media-query'
import { EmptyHome } from '@/live/empty-home'
import { PhoneRunning } from '@/live/phone-live'
import { PREVIEW_LABEL_FOOT_PX, PreviewOnlyLabel } from '@/live/preview-only'
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
  const composing = useMatch('/live/put') !== null
  const compose = useStageCompose(composing)
  useComposerKeys(composing)
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
  const [wasComposing, setWasComposing] = useState(composing)
  if (composing !== wasComposing) {
    // The composer takes the Running panel's place, so no card stays under the pointer.
    setWasComposing(composing)
    setHovered(null)
  }
  // The focus was in the composer, which goes with it: the Running panel that returns gives it to the link that opens the composer, where it
  // would otherwise fall to the page.
  const put = useRef<HTMLAnchorElement>(null)
  const wasOpen = useRef(composing)
  useEffect(() => {
    if (wasOpen.current && !composing) put.current?.focus()
    wasOpen.current = composing
  }, [composing])
  const stage = (
    <Suspense fallback={<StagePending />}>
      <Stage
        variant={phone ? 'phone' : 'desktop'}
        outlined={phone ? null : (hovered ?? zoneId ?? null)}
        focus={phone ? (zoneId ?? null) : null}
        compose={compose}
      />
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
      <div
        className="relative min-w-0 flex-1"
        style={previewOnly ? ({ '--stage-top-shift': `${PREVIEW_LABEL_FOOT_PX}px` } as CSSProperties) : undefined}
      >
        {stage}
        {composing && <ComposerWhere narrow={narrow} />}
        {previewOnly && <PreviewOnlyLabel />}
        <ReconnectingCard variant="desktop" />
        <EmptyHome variant="desktop" />
      </div>
      {composing && (
        <ComposerPanel className={narrow ? 'absolute inset-y-0 right-0 z-20 w-(--live-panel-w) shadow-pop' : 'w-(--live-panel-w) shrink-0'} />
      )}
      {!composing && !narrow && (
        <RunningPanel selected={zoneId} className="w-(--live-panel-w) shrink-0" onZoneHover={setHovered} putRef={put} />
      )}
      {!composing && narrow && panel !== 'hidden' && (
        <RunningPanel
          selected={zoneId}
          className="absolute inset-y-0 right-0 z-20 w-(--live-panel-w) shadow-pop"
          onHide={() => setPanel('hidden')}
          onZoneHover={setHovered}
          focusHide={panel === 'reopened'}
          putRef={put}
        />
      )}
      {!composing && narrow && panel === 'hidden' && (
        <Button icon="left" autoFocus className="absolute top-1/2 right-4 z-20 -translate-y-1/2 shadow-pop" onClick={() => setPanel('reopened')}>
          Running
        </Button>
      )}
    </div>
  )
}
