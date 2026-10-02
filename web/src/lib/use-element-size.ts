import { useCallback, useState } from 'react'

export interface ElementSize {
  width: number
  height: number
}

const UNMEASURED: ElementSize = { width: 0, height: 0 }

/**
 * A ref for an element and its content-box size in CSS px, kept current by a ResizeObserver: 0 × 0
 * until the first measure. A size that didn't change keeps the same object, so nothing re-renders.
 */
export function useElementSize<T extends Element>(): [ref: (element: T | null) => (() => void) | undefined, size: ElementSize] {
  const [size, setSize] = useState(UNMEASURED)
  const ref = useCallback((element: T | null) => {
    if (element === null) return undefined
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect
      setSize((previous) => (previous.width === width && previous.height === height ? previous : { width, height }))
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [])
  return [ref, size]
}
