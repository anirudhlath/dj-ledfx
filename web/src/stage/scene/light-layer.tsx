// The lights on the canvas (§7.3, §7.5). Their materials are made once per room mask, and their
// meshes when the writer is (which bodies are drawn changed); a `lights` push that changes only what
// a light shows is written into them in place, and drawn at once. Frames never pass through React:
// the light layer draws on the stage's cadence (cadence.ts), writing the frame store's latest bytes
// into the meshes' own arrays, then drawing the canvas in that animation frame.
import { useThree } from '@react-three/fiber'
import { useEffect, useLayoutEffect, useMemo } from 'react'
import { frames } from '@/api/live'
import { useCadence } from '../cadence'
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
  /** The stage behaviour's (behaviour.ts): null while frames don't redraw the stage. */
  cadenceMs: number | null
}

export function LightLayer({ writer, entries, mask, pose, cadenceMs }: LightLayerProps) {
  const materials = useMemo(() => new LightMaterials(mask), [mask])
  const meshes = useMemo(() => new LightMeshes(writer, materials), [writer, materials])
  const invalidate = useThree((state) => state.invalidate)
  const advance = useThree((state) => state.advance)
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
    invalidate()
  }, [writer, meshes, entries, invalidate])
  useCadence(cadenceMs, (now) => {
    writer.write(frames)
    meshes.update()
    advance(now)
  })
  return (
    <>
      {meshes.pools !== null && <primitive object={meshes.pools} />}
      <primitive object={meshes.lifted} />
    </>
  )
}
