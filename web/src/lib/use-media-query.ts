import { useCallback, useMemo, useSyncExternalStore } from 'react'

/** Below Tailwind's `md` (48rem = 768 px) the app uses the phone layouts (spec §4.4). */
export const PHONE_QUERY = '(width < 48rem)'

/** The system asks for less motion (§5.4). */
export const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)'

export function useMediaQuery(query: string): boolean {
  const list = useMemo(() => window.matchMedia(query), [query])
  const subscribe = useCallback(
    (onChange: () => void) => {
      list.addEventListener('change', onChange)
      return () => list.removeEventListener('change', onChange)
    },
    [list],
  )
  return useSyncExternalStore(subscribe, () => list.matches)
}

export function useIsPhone(): boolean {
  return useMediaQuery(PHONE_QUERY)
}

/** The system asks for less motion (§5.4): the stage redraws at most once every SPEC.reducedMotionMs. */
export function useReducedMotion(): boolean {
  return useMediaQuery(REDUCED_MOTION_QUERY)
}
