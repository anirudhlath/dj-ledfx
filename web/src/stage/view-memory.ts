// §7.2: "Remember the view per route in local storage." The view is a per-viewer convenience, so
// storage that is missing, full, blocked or holding junk only costs the remembered view: every read
// and write is guarded, and every field is checked on the way in.
import { useCallback, useState } from 'react'
import { FIT_VIEW, type View } from './camera'
import { SPEC } from './design-numbers'

/** The stage's own controls: the camera's view, and whether the room labels show. */
export interface StageView {
  view: View
  labels: boolean
}

export const DEFAULT_STAGE_VIEW: StageView = { view: FIT_VIEW, labels: true }

/** "Zoom in" steps through these; Fit goes back to the first (decision 5). */
export const ZOOM_STEPS = [1, 1.25, 1.5, 2] as const

const KEY = 'dj-ledfx:stage-view:'

/** localStorage, or null where reaching it throws (a sandboxed frame, blocked site data). */
export function browserStorage(): Storage | null {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

const isRotation = (value: unknown): value is number =>
  typeof value === 'number' && Number.isInteger(value / SPEC.rotate.stepDeg) && Math.abs(value) <= SPEC.rotate.maxDeg
const isZoom = (value: unknown): value is number => typeof value === 'number' && (ZOOM_STEPS as readonly number[]).includes(value)

/** The view stored for `route`; the default for whatever is missing or unreadable. */
export function readStageView(storage: Storage | null, route: string): StageView {
  let stored: unknown = null
  try {
    stored = JSON.parse(storage?.getItem(KEY + route) ?? 'null')
  } catch {
    return DEFAULT_STAGE_VIEW
  }
  if (typeof stored !== 'object' || stored === null) return DEFAULT_STAGE_VIEW
  const { mode, rotateDeg, zoom, labels } = stored as Record<string, unknown>
  return {
    view: {
      mode: mode === 'plan' || mode === '3d' ? mode : FIT_VIEW.mode,
      rotateDeg: isRotation(rotateDeg) ? rotateDeg : FIT_VIEW.rotateDeg,
      zoom: isZoom(zoom) ? zoom : FIT_VIEW.zoom,
    },
    labels: typeof labels === 'boolean' ? labels : DEFAULT_STAGE_VIEW.labels,
  }
}

/** Stores the view for `route`; a storage that refuses is ignored. */
export function writeStageView(storage: Storage | null, route: string, { view, labels }: StageView): void {
  try {
    storage?.setItem(KEY + route, JSON.stringify({ ...view, labels }))
  } catch {
    // Full, or blocked: the view just isn't remembered.
  }
}

/** "Rotate view": one step on, from the last step round to the first (§7.2's ±SPEC.rotate.maxDeg). */
export function nextRotation(rotateDeg: number): number {
  const next = rotateDeg + SPEC.rotate.stepDeg
  return next > SPEC.rotate.maxDeg ? -SPEC.rotate.maxDeg : next
}

/** "Zoom in": the next step, or null at the last. */
export function nextZoom(zoom: number): number | null {
  return ZOOM_STEPS.find((step) => step > zoom + 1e-9) ?? null
}

/** The stage's view for `route`, remembered across visits. */
export function useStageView(route: string, storage: Storage | null = browserStorage()): [StageView, (next: StageView) => void] {
  const [state, setState] = useState(() => readStageView(storage, route))
  const update = useCallback(
    (next: StageView) => {
      setState(next)
      writeStageView(storage, route, next)
    },
    [storage, route],
  )
  return [state, update]
}
