// The lights on the canvas (§7.3, §7.5). Their materials are made once per room mask, and their
// meshes when the writer is (which bodies are drawn changed); a `lights` push that changes only what
// a light shows is written into them in place, and drawn at once. Frames never pass through React:
// on each draw, useFrame writes the frame store's latest bytes into the meshes' own arrays, if a
// frame arrived since the last draw.
import { useFrame, useThree } from '@react-three/fiber'
import { useEffect, useLayoutEffect, useMemo, useRef } from 'react'
import { frames } from '@/api/live'
import type { CameraPose } from '../camera'
import type { FrameWriter, WriterEntry } from '../frame-writer'
import type { RoomMask } from '../room-mask'
import { LightMaterials, LightMeshes } from './light-meshes'

export interface LightLayerProps {
  writer: FrameWriter
  /** What each drawn light shows now, laid out as the writer is. */
  entries: readonly WriterEntry[]
  mask: RoomMask
  pose: CameraPose
  /** §7.6 frozen: the last frame stays. A light whose state changed still draws once. */
  frozen: boolean
}

export function LightLayer({ writer, entries, mask, pose, frozen }: LightLayerProps) {
  const materials = useMemo(() => new LightMaterials(mask), [mask])
  const meshes = useMemo(() => new LightMeshes(writer, materials), [writer, materials])
  const invalidate = useThree((state) => state.invalidate)
  const drawnVersion = useRef(-1)
  useEffect(() => () => materials.dispose(), [materials])
  useEffect(() => () => meshes.dispose(), [meshes])
  useLayoutEffect(() => {
    materials.setView(pose)
    meshes.setView(pose)
    invalidate()
  }, [materials, meshes, pose, invalidate])
  useLayoutEffect(() => {
    writer.setEntries(entries)
    writer.write(frames)
    meshes.update()
    drawnVersion.current = frames.version
    invalidate()
  }, [writer, meshes, entries, invalidate])
  useFrame(() => {
    if (frozen || drawnVersion.current === frames.version) return
    writer.write(frames)
    meshes.update()
    drawnVersion.current = frames.version
  })
  return (
    <>
      {meshes.pools !== null && <primitive object={meshes.pools} />}
      <primitive object={meshes.lifted} />
    </>
  )
}
