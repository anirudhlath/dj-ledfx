// "Effects in space" on the canvas (§7.4): the fx store's picture of the zones the stage picks, drawn
// on the stage's cadence beside the lights (draw-list.ts). Pictures never pass through React: the
// layer writes the store's newest into its meshes' arrays when the cadence asks, and a new pick (the
// composer's preview, focus's zone) is written at once.
import { useThree } from '@react-three/fiber'
import { useEffect, useLayoutEffect, useMemo } from 'react'
import type { Home } from '@/api/contract'
import { fx } from '@/api/live'
import type { CameraPose } from '../camera'
import { FxWriter, type FxPick } from '../fx-writer'
import type { DrawList } from './draw-list'
import { FxMaterials, FxMeshes } from './fx-meshes'

export interface FxLayerProps {
  home: Pick<Home, 'outline' | 'ceiling'>
  /** Which zones' fx it draws. */
  pick: FxPick
  pose: CameraPose
  drawList: DrawList
}

export function FxLayer({ home, pick, pose, drawList }: FxLayerProps) {
  const { outline, ceiling } = home
  const materials = useMemo(() => new FxMaterials({ outline, ceiling }), [outline, ceiling])
  const writer = useMemo(() => new FxWriter(), [])
  const meshes = useMemo(() => new FxMeshes(writer, materials), [writer, materials])
  const invalidate = useThree((state) => state.invalidate)
  useEffect(() => () => materials.dispose(), [materials])
  // Gone, the picture goes with it: the canvas draws once more without it.
  useEffect(
    () => () => {
      meshes.dispose()
      invalidate()
    },
    [meshes, invalidate],
  )
  useLayoutEffect(() => {
    materials.setView(pose)
    invalidate()
  }, [materials, pose, invalidate])
  useLayoutEffect(() => {
    writer.write(fx, pick)
    meshes.update()
    invalidate()
  }, [writer, meshes, pick, invalidate])
  useLayoutEffect(
    () =>
      drawList.add(() => {
        if (!writer.write(fx, pick)) return false
        meshes.update()
        return true
      }),
    [drawList, writer, meshes, pick],
  )
  return <primitive object={meshes.group} />
}
