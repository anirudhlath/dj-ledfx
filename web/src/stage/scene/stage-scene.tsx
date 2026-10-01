// Everything on the stage's canvas: the camera where the pose puts it (§7.2), the static home, the
// lights, and the cadence that redraws them (§7.5).
import { useThree } from '@react-three/fiber'
import { useLayoutEffect } from 'react'
import type { OrthographicCamera } from 'three'
import type { Home } from '@/api/contract'
import { useCadence } from '../cadence'
import { applyPose, type CameraPose } from '../camera'
import type { FrameWriter, WriterEntry } from '../frame-writer'
import type { RoomMask } from '../room-mask'
import { LightLayer } from './light-layer'
import { StaticHome } from './static-home'

export interface StageSceneProps {
  home: Home
  writer: FrameWriter
  /** What each drawn light shows now, laid out as the writer is (frame-writer.ts's sameLayout()). */
  entries: readonly WriterEntry[]
  mask: RoomMask
  pose: CameraPose
  /** The camera's bearing (camera.ts's bearingDeg). */
  bearing: number
  frozen: boolean
  /** cadence.ts's cadenceMs(): null while frames don't redraw the stage. */
  cadenceMs: number | null
}

export function StageScene({ home, writer, entries, mask, pose, bearing, frozen, cadenceMs }: StageSceneProps) {
  const camera = useThree((state) => state.camera)
  const invalidate = useThree((state) => state.invalidate)
  useLayoutEffect(() => {
    // The canvas is made orthographic (stage-canvas.tsx).
    applyPose(camera as OrthographicCamera, pose)
    invalidate()
  }, [camera, pose, invalidate])
  useCadence(cadenceMs)
  return (
    <>
      <StaticHome home={home} bearing={bearing} width={pose.width} height={pose.height} />
      <LightLayer writer={writer} entries={entries} mask={mask} pose={pose} frozen={frozen} />
    </>
  )
}
