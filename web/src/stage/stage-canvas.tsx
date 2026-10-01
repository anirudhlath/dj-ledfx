// The stage's WebGL canvas (§7.5). React Three Fiber's createRoot draws the scene into the stage's own
// <canvas>, sized from the pose the stage already measures. Nothing is extend()ed: the scene's objects
// go in as <primitive>, so three.js tree-shakes (R3F's <Canvas> registers all of it), and with no
// event manager R3F adds no listeners, since the stage picks for itself (picking.ts). The camera is
// orthographic and placed by hand, colours are drawn as given (`linear` and `flat`: no colour
// conversion, no tone mapping), the pixel ratio is capped at SPEC.dprCap, and the canvas draws only
// when asked (frameloop "demand").
import { createRoot, type ReconcilerRoot } from '@react-three/fiber'
import { Component, useInsertionEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { SPEC } from './design-numbers'
import { STAGE_PALETTE } from './palette'
import { rgb } from './scene/materials'
import { StageScene, type StageSceneProps } from './scene/stage-scene'

const BACKGROUND = rgb(STAGE_PALETTE.bg)

/** Hands an error in the canvas's own React root to the page's, whose error boundary shows it. */
class HandOn extends Component<{ onError: (error: unknown) => void; children: ReactNode }, { failed: boolean }> {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  componentDidCatch(error: unknown) {
    this.props.onError(error)
  }

  render() {
    return this.state.failed ? null : this.props.children
  }
}

export function StageCanvas(props: StageSceneProps) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const root = useRef<ReconcilerRoot<HTMLCanvasElement> | null>(null)
  const [failure, setFailure] = useState<{ error: unknown } | null>(null)
  if (failure !== null) throw failure.error
  const fail = (error: unknown) => setFailure({ error })

  // One root for the canvas's life: StrictMode replays layout effects, not an insertion effect's
  // cleanup, so its renderer and WebGL context are made once (as R3F's <Canvas> keeps them).
  useInsertionEffect(
    () => () => {
      root.current?.unmount()
      root.current = null
    },
    [],
  )

  useLayoutEffect(() => {
    root.current ??= createRoot(canvas.current!)
    const { width, height } = props.pose
    root.current
      .configure({
        orthographic: true,
        camera: { manual: true },
        linear: true,
        flat: true,
        frameloop: 'demand',
        dpr: [1, SPEC.dprCap],
        size: { width, height, top: 0, left: 0 },
        scene: { background: BACKGROUND },
      })
      .catch(fail)
    // A renderer that failed to start rejects, and the catch hands it on.
    if (root.current.ready.status !== 'fulfilled') return
    root.current.render(
      <HandOn onError={fail}>
        <StageScene {...props} />
      </HandOn>,
    )
  })

  return <canvas ref={canvas} aria-hidden="true" className="absolute inset-0" />
}
