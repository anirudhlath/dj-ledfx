// The stage's WebGL canvas (§7.5): an orthographic camera placed by hand, colours drawn as given
// (`linear` and `flat`: no colour conversion, no tone mapping), the pixel ratio capped at
// SPEC.dprCap, and a draw only when something asks for one.
import { Canvas } from '@react-three/fiber'
import { Color } from 'three'
import { SPEC } from './design-numbers'
import { STAGE_PALETTE } from './palette'
import { StageScene, type StageSceneProps } from './scene/stage-scene'

const BACKGROUND = new Color().setRGB(...STAGE_PALETTE.bg)

export function StageCanvas(props: StageSceneProps) {
  return (
    <Canvas
      orthographic
      linear
      flat
      frameloop="demand"
      dpr={[1, SPEC.dprCap]}
      camera={{ manual: true }}
      scene={{ background: BACKGROUND }}
      aria-hidden="true"
      className="absolute! inset-0"
    >
      <StageScene {...props} />
    </Canvas>
  )
}
