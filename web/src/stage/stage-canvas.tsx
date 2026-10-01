// The stage's WebGL canvas (§7.5). React Three Fiber's createRoot draws the scene into the stage's own
// <canvas>, sized from the pose the stage already measures. Nothing is extend()ed: the scene's objects
// go in as <primitive>, so three.js tree-shakes (R3F's <Canvas> registers all of it), and with no
// event manager R3F adds no listeners, since the stage picks for itself (picking.ts). The camera is
// orthographic and placed by hand, colours are drawn as given (`linear` and `flat`: no colour
// conversion, no tone mapping), the pixel ratio is capped at SPEC.dprCap, and the canvas draws only
// when asked (frameloop "demand") — once three has compiled the scene's shaders. Three links a draw's
// programs synchronously, so until compileAsync() has them ready off the main thread, nothing draws:
// not on demand (frameloop "never") and not on the cadence (cadenceMs null).
import { createRoot, type ReconcilerRoot } from '@react-three/fiber'
import { Component, memo, useInsertionEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
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

/** Memoised: a hover or anything else the page re-renders for doesn't touch the canvas. */
export const StageCanvas = memo(function StageCanvas(props: StageSceneProps) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const root = useRef<ReconcilerRoot<HTMLCanvasElement> | null>(null)
  const compiling = useRef(false)
  const [compiled, setCompiled] = useState(false)
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
        frameloop: compiled ? 'demand' : 'never',
        dpr: [1, SPEC.dprCap],
        size: { width, height, top: 0, left: 0 },
        scene: { background: BACKGROUND },
      })
      .catch(fail)
    // A renderer that failed to start rejects, and the catch hands it on.
    if (root.current.ready.status !== 'fulfilled') return
    const store = root.current.render(
      <HandOn onError={fail}>
        <StageScene {...props} cadenceMs={compiled ? props.cadenceMs : null} />
      </HandOn>,
    )
    const { gl, scene, camera, invalidate } = store.getState()
    if (compiled) invalidate()
    else if (!compiling.current) {
      compiling.current = true
      gl.compileAsync(scene, camera).then(() => setCompiled(true), fail)
    }
  })

  return <canvas ref={canvas} aria-hidden="true" className="absolute inset-0" />
})
