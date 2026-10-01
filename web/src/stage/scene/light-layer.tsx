// The lights on the canvas (§7.3, §7.5). React makes their meshes when what's drawn changes (the
// lights, their states, the home); frames never pass through React. On each draw, useFrame writes
// the frame store's latest bytes into the meshes' own arrays, if a frame arrived since the last draw.
import { useFrame, useThree } from '@react-three/fiber'
import { useEffect, useLayoutEffect, useMemo, useRef } from 'react'
import { frames } from '@/api/live'
import type { CameraPose } from '../camera'
import type { FrameWriter } from '../frame-writer'
import type { RoomMask } from '../room-mask'
import { LightMeshes } from './light-meshes'

export interface LightLayerProps {
  writer: FrameWriter
  mask: RoomMask
  pose: CameraPose
  /** §7.6 frozen: the last frame stays. A new writer (a light's state changed) still draws once. */
  frozen: boolean
}

export function LightLayer({ writer, mask, pose, frozen }: LightLayerProps) {
  const meshes = useMemo(() => new LightMeshes(writer, mask), [writer, mask])
  const invalidate = useThree((state) => state.invalidate)
  const drawnWriter = useRef<FrameWriter | null>(null)
  const drawnVersion = useRef(-1)
  useEffect(() => () => meshes.dispose(), [meshes])
  useLayoutEffect(() => {
    meshes.setView(pose)
    invalidate()
  }, [meshes, pose, invalidate])
  useFrame(() => {
    if (drawnWriter.current === writer && (frozen || drawnVersion.current === frames.version)) return
    writer.write(frames)
    meshes.update()
    drawnWriter.current = writer
    drawnVersion.current = frames.version
  })
  return (
    <>
      {meshes.pools !== null && <primitive object={meshes.pools} />}
      <primitive object={meshes.lifted} />
    </>
  )
}
