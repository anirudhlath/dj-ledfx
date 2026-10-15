// Everything on the stage's canvas: the camera where the pose puts it (§7.2), the static home, the
// lights, and the effects in space (§7.4) while the stage draws them. The lights and the effects draw
// on the stage's one cadence (§7.5): each writes what's new, and the canvas renders once if any did.
import { useThree } from '@react-three/fiber'
import { useLayoutEffect, useMemo } from 'react'
import type { OrthographicCamera } from 'three'
import type { Home } from '@/api/contract'
import { useCadence } from '../cadence'
import { applyPose, type CameraPose } from '../camera'
import type { FxPick } from '../fx-writer'
import type { FrameWriter, WriterEntry } from '../frame-writer'
import type { RoomMask } from '../room-mask'
import { DrawList } from './draw-list'
import { FxLayer } from './fx-layer'
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
  const drawList = useMemo(() => new DrawList(), [])
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
      {fx !== null && <FxLayer home={home} pick={fx} pose={pose} drawList={drawList} />}
    </>
  )
}
