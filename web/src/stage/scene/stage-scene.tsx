// Everything on the stage's canvas: the camera where the pose puts it (§7.2), the static home, the
// lights, and the effects in space (§7.4) while the stage draws them. The lights and the effects draw
// on the stage's one cadence (§7.5): each writes what's new, and the canvas renders once if any did.
// The effects' materials are the scene's, one set per home, compiled ahead as the scene comes up and
// kept while the fx layer comes and goes (the switch, frozen, reduced motion), so no program of theirs
// is linked mid-draw; the layer comes only once they're compiled.
import { useThree } from '@react-three/fiber'
import { useEffect, useLayoutEffect, useMemo, useState } from 'react'
import type { OrthographicCamera } from 'three'
import type { Home } from '@/api/contract'
import { useCadence } from '../cadence'
import { applyPose, type CameraPose } from '../camera'
import type { FxPick } from '../fx-writer'
import type { FrameWriter, WriterEntry } from '../frame-writer'
import type { RoomMask } from '../room-mask'
import { DrawList } from './draw-list'
import { FxLayer } from './fx-layer'
import { compileFx, FxMaterials } from './fx-meshes'
import { LightLayer } from './light-layer'
import { StaticHome } from './static-home'

export interface StageSceneProps {
  home: Home
  writer: FrameWriter
  /** What each drawn light shows now, laid out as the writer is (frame-writer.ts's sameLayout()). */
  entries: readonly WriterEntry[]
  mask: RoomMask
  pose: CameraPose
  /** The stage behaviour's (behaviour.ts): null while frames don't redraw the stage. */
  cadenceMs: number | null
  /** Which zones' effects in space it draws (§7.4), or null while it draws none. */
  fx: FxPick | null
}

export function StageScene({ home, writer, entries, mask, pose, cadenceMs, fx }: StageSceneProps) {
  const camera = useThree((state) => state.camera)
  const invalidate = useThree((state) => state.invalidate)
  const advance = useThree((state) => state.advance)
  const gl = useThree((state) => state.gl)
  const scene = useThree((state) => state.scene)
  const drawList = useMemo(() => new DrawList(), [])
  const { outline, ceiling } = home
  const fxMaterials = useMemo(() => new FxMaterials({ outline, ceiling }), [outline, ceiling])
  const [fxCompiled, setFxCompiled] = useState<FxMaterials | null>(null)
  useEffect(() => () => fxMaterials.dispose(), [fxMaterials])
  useEffect(() => {
    let current = true
    const done = () => current && setFxCompiled(fxMaterials)
    // Compiling ahead only keeps a link off the main thread: if it fails, the programs link on first draw, so the layer
    // comes all the same, and the failure is reported as an uncaught error, which e2e's shader check listens for.
    void compileFx(gl, fxMaterials, camera, scene).then(done, (error: unknown) => {
      if (current) reportError(error)
      done()
    })
    return () => void (current = false)
  }, [gl, fxMaterials, camera, scene])
  useLayoutEffect(() => {
    // The canvas is made orthographic (stage-canvas.tsx).
    applyPose(camera as OrthographicCamera, pose)
    invalidate()
  }, [camera, pose, invalidate])
  useCadence(cadenceMs, (now) => {
    if (drawList.draw()) advance(now)
  })
  return (
    <>
      <StaticHome home={home} pose={pose} />
      <LightLayer writer={writer} entries={entries} mask={mask} pose={pose} drawList={drawList} />
      {fx !== null && fxCompiled === fxMaterials && <FxLayer materials={fxMaterials} pick={fx} pose={pose} drawList={drawList} />}
    </>
  )
}
