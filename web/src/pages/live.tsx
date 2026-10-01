// Live (§8.1, §8.10): the stage, and beside it (F3) the Running panel. The stage's code loads on
// demand, keeping three.js out of the first load (§14); its place keeps the stage's background
// meanwhile.
import { lazy, Suspense } from 'react'
import { useIsPhone, useMediaQuery } from '@/lib/use-media-query'
import { SPEC } from '@/stage/design-numbers'
import { StagePending } from '@/stage/stage-pending'
import { Placeholder } from './placeholder'

const Stage = lazy(() => import('@/stage/stage'))

/** §4.4: below SPEC.widePx the Running panel stops sitting beside the stage (F3 makes it collapsible). */
const NARROW_QUERY = `(width < ${SPEC.widePx / 16}rem)`

export function LivePage() {
  const phone = useIsPhone()
  const narrow = useMediaQuery(NARROW_QUERY)
  if (phone) {
    return (
      <div className="flex flex-col">
        <div className="relative shrink-0" style={{ aspectRatio: `${SPEC.phoneStage.width} / ${SPEC.phoneStage.height}` }}>
          <Suspense fallback={<StagePending />}>
            <Stage variant="phone" />
          </Suspense>
        </div>
        <Placeholder name="Running" milestone="F3" />
      </div>
    )
  }
  return (
    <div className="flex h-full min-h-0">
      <div className="relative min-w-0 flex-1">
        <Suspense fallback={<StagePending />}>
          <Stage variant="desktop" />
        </Suspense>
      </div>
      {!narrow && (
        <aside aria-label="Running" className="w-(--live-panel-w) shrink-0 border-l border-line-soft bg-panel">
          <Placeholder name="Running panel" milestone="F3" />
        </aside>
      )}
    </div>
  )
}
