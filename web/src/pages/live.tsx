// Live (§8.1, §8.10): the stage, and beside it (F3) the Running panel. The stage's code loads on
// demand, keeping three.js out of the first load (§14); its place keeps the stage's background
// meanwhile, and its REST reads start at once rather than when its code arrives.
import { usePrefetchQuery } from '@tanstack/react-query'
import { lazy, Suspense } from 'react'
import { queries } from '@/api/queries'
import { useIsPhone, useMediaQuery } from '@/lib/use-media-query'
import { StagePending } from '@/stage/stage-pending'
import { LIVE_LAYOUT } from './live-numbers'
import { Placeholder } from './placeholder'

const Stage = lazy(() => import('@/stage/stage'))

/** §4.4: below LIVE_LAYOUT.widePx the Running panel stops sitting beside the stage (F3 makes it collapsible). */
const NARROW_QUERY = `(width < ${LIVE_LAYOUT.widePx / 16}rem)`

export function LivePage() {
  usePrefetchQuery(queries.home())
  usePrefetchQuery(queries.lights())
  usePrefetchQuery(queries.zones())
  const phone = useIsPhone()
  const narrow = useMediaQuery(NARROW_QUERY)
  const stage = (
    <Suspense fallback={<StagePending />}>
      <Stage variant={phone ? 'phone' : 'desktop'} />
    </Suspense>
  )
  if (phone) {
    return (
      <div className="flex flex-col">
        <div className="relative shrink-0" style={{ aspectRatio: `${LIVE_LAYOUT.phoneStage.width} / ${LIVE_LAYOUT.phoneStage.height}` }}>
          {stage}
        </div>
        <Placeholder name="Running" milestone="F3" />
      </div>
    )
  }
  return (
    <div className="flex h-full min-h-0">
      <div className="relative min-w-0 flex-1">{stage}</div>
      {!narrow && (
        <aside aria-label="Running" className="w-(--live-panel-w) shrink-0 border-l border-line-soft bg-panel">
          <Placeholder name="Running panel" milestone="F3" />
        </aside>
      )}
    </div>
  )
}
