// A transition's percentage and bar on the move (F3 decision 16). The engine pushes a zone as its
// transition starts, passes the midpoint and ends (the engine M4 plan's ruling 15), so between pushes an
// animation frame moves them on from the served progress at the served duration, never through React,
// as the overlay's time moves (decision 17). Without a duration they hold. The served values are
// primitives, so a card that renders again for anything else doesn't restart the motion.
import { useLayoutEffect, type RefObject } from 'react'
import { percentOf, writeProgress } from '@/design/progress'
import { transitionProgress } from './zone-view'

export function useMovingProgress(
  progress: number,
  durationS: number | null,
  text: RefObject<HTMLElement | null>,
  bar?: RefObject<HTMLElement | null>,
): void {
  useLayoutEffect(() => {
    const first = Date.now()
    let frame = 0
    let shown = ''
    const tick = () => {
      const value = transitionProgress(progress, durationS, Date.now() - first)
      const words = `${percentOf(value)}%`
      if (text.current !== null && words !== shown) {
        text.current.textContent = words
        shown = words
      }
      if (bar?.current) writeProgress(bar.current, value)
      frame = durationS !== null && value < 1 ? requestAnimationFrame(tick) : 0
    }
    tick()
    return () => cancelAnimationFrame(frame)
  }, [progress, durationS, text, bar])
}
