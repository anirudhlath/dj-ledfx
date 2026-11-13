// A LookThumb's motion while it's on screen (§5.4 "Pause thumbnails that are off screen"). It moves only
// with a motif, `live` (F5 decision 8), no reduced motion (§5.4 "stop … thumbnail loops") and no ?still
// (decision 6): otherwise nothing is observed, and the motif stays at its authored moment.
import { useLayoutEffect, type RefObject } from 'react'
import { beatClock } from '@/api/live'
import { useReducedMotion } from '@/lib/use-media-query'
import { registerThumb } from './thumb-writer'

/** `beat`: whether the thumb's motif follows the beat, undefined with no motif. */
export function useThumbMotion(svg: RefObject<SVGSVGElement | null>, beat: boolean | undefined, live: boolean): void {
  const reducedMotion = useReducedMotion()
  useLayoutEffect(() => {
    const element = svg.current
    if (element === null || beat === undefined || !live || reducedMotion || beatClock.held) return
    let stop: (() => void) | null = null
    let disposed = false
    const observer = new IntersectionObserver((entries) => {
      // A report already queued when the effect cleaned up can still arrive after disconnect().
      if (disposed) return
      // The newest entry is where the svg is now.
      const onScreen = entries.at(-1)?.isIntersecting ?? false
      if (onScreen && stop === null) stop = registerThumb({ svg: element, beat })
      else if (!onScreen && stop !== null) {
        stop()
        stop = null
      }
    })
    observer.observe(element)
    return () => {
      disposed = true
      observer.disconnect()
      stop?.()
    }
  }, [svg, beat, live, reducedMotion])
}
