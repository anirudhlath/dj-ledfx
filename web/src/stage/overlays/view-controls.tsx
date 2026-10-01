// §8.1 bottom right: rotate, zoom and fit (§7.2's view controls: rotate orbits in SPEC.rotate's steps
// within its range, and Fit snaps back). Zoom steps in until ZOOM_STEPS runs out; Fit goes back to the
// fitted view.
import { IconButton } from '@/design/button'
import { FIT_VIEW, type View } from '../camera'
import { RENDER } from '../design-numbers'
import { nextRotation, nextZoom } from '../view-memory'

export interface ViewControlsProps {
  view: View
  onView: (view: View) => void
}

export function ViewControls({ view, onView }: ViewControlsProps) {
  const { rightPx, bottomPx, gapPx } = RENDER.controls
  const zoomIn = nextZoom(view.zoom)
  return (
    <div className="absolute flex" style={{ right: rightPx, bottom: bottomPx, gap: gapPx }}>
      <IconButton icon="rotate" label="Rotate view" onClick={() => onView({ ...view, rotateDeg: nextRotation(view.rotateDeg) })} />
      <IconButton icon="plus" label="Zoom in" disabled={zoomIn === null} onClick={() => zoomIn !== null && onView({ ...view, zoom: zoomIn })} />
      <IconButton icon="crosshair" label="Fit home" onClick={() => onView({ ...FIT_VIEW, mode: view.mode })} />
    </div>
  )
}
