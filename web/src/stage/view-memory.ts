// §7.2: "Remember the view per route in local storage." The view is a per-viewer convenience, so
// storage that is missing, full, blocked or holding junk only costs the remembered view: every read
// and write is guarded, and every field is checked on the way in.
import { useCallback, useState } from 'react'
import { browserStorage } from '@/lib/storage'
import { FIT_VIEW, type View } from './camera'
import { SPEC } from './design-numbers'

/** What the stage remembers per route: the camera's view, and whether the room labels and the effects in space show. */
export interface StoredView {
  view: View
  labels: boolean
  /** §7.4: "This is the "Effects in space" toggle (default on)". */
  effects: boolean
}

export const DEFAULT_STAGE_VIEW: StoredView = { view: FIT_VIEW, labels: true, effects: true }

/** "Zoom in" steps through these; Fit goes back to the first (decision 5). */
export const ZOOM_STEPS = [1, 1.25, 1.5, 2] as const

const KEY = 'dj-ledfx:stage-view:'

const isRotation = (value: unknown): value is number =>
  typeof value === 'number' && Number.isInteger(value / SPEC.rotate.stepDeg) && Math.abs(value) <= SPEC.rotate.maxDeg
const isZoom = (value: unknown): value is number => typeof value === 'number' && (ZOOM_STEPS as readonly number[]).includes(value)

/** The view stored for `route`; the default for whatever is missing or unreadable. */
export function readStageView(storage: Storage | null, route: string): StoredView {
  let stored: unknown = null
  try {
    stored = JSON.parse(storage?.getItem(KEY + route) ?? 'null')
  } catch {
    return DEFAULT_STAGE_VIEW
  }
  if (typeof stored !== 'object' || stored === null) return DEFAULT_STAGE_VIEW
  const { mode, rotateDeg, zoom, labels, effects } = stored as Record<string, unknown>
  return {
    view: {
      mode: mode === 'plan' || mode === '3d' ? mode : FIT_VIEW.mode,
      rotateDeg: isRotation(rotateDeg) ? rotateDeg : FIT_VIEW.rotateDeg,
      zoom: isZoom(zoom) ? zoom : FIT_VIEW.zoom,
    },
    labels: typeof labels === 'boolean' ? labels : DEFAULT_STAGE_VIEW.labels,
    effects: typeof effects === 'boolean' ? effects : DEFAULT_STAGE_VIEW.effects,
  }
}

/** Stores the view for `route`; a storage that refuses is ignored. */
export function writeStageView(storage: Storage | null, route: string, { view, labels, effects }: StoredView): void {
  try {
    storage?.setItem(KEY + route, JSON.stringify({ ...view, labels, effects }))
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
export function useStageView(route: string, storage: Storage | null = browserStorage()): [StoredView, (next: StoredView) => void] {
  const [state, setState] = useState(() => readStageView(storage, route))
  const update = useCallback(
    (next: StoredView) => {
      setState(next)
      writeStageView(storage, route, next)
    },
    [storage, route],
  )
  return [state, update]
}
