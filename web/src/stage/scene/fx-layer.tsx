// "Effects in space" on the canvas (§7.4): the fx store's picture of the zones the stage picks, drawn
// on the stage's cadence beside the lights (draw-list.ts). Pictures never pass through React: the
// layer writes the store's newest into its meshes' arrays when the cadence asks, and a new pick (the
// composer's preview, focus's zone) is written at once. Each write sets the canvas's `data-fx-drawn`
// to the store's version, on the cadence in the task that renders it, and for a new pick before the
// render it asks for: e2e waits for it before a screenshot (e2e/helpers.ts, fxPictured()). One DOM
// write a picture or a pick, none an idle frame (§7.5).
import { useThree } from '@react-three/fiber'
import { useEffect, useLayoutEffect, useMemo } from 'react'
import { fx } from '@/api/live'
import type { CameraPose } from '../camera'
import { FxWriter, type FxPick } from '../fx-writer'
import type { DrawList } from './draw-list'
import { FxMeshes, type FxMaterials } from './fx-meshes'

export interface FxLayerProps {
  /** The stage's, compiled already: they outlive the layer, so the switch going on links no program (stage-scene.tsx). */
  materials: FxMaterials
  /** Which zones' fx it draws. */
  pick: FxPick
  pose: CameraPose
  drawList: DrawList
}

export function FxLayer({ materials, pick, pose, drawList }: FxLayerProps) {
  const writer = useMemo(() => new FxWriter(), [])
  const meshes = useMemo(() => new FxMeshes(writer, materials), [writer, materials])
  const invalidate = useThree((state) => state.invalidate)
  const canvas = useThree((state) => state.gl.domElement)
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
    markDrawn(canvas)
    invalidate()
  }, [writer, meshes, pick, canvas, invalidate])
  useLayoutEffect(
    () =>
      drawList.add(() => {
        if (!writer.write(fx, pick)) return false
        meshes.update()
        markDrawn(canvas)
        return true
      }),
    [drawList, writer, meshes, pick, canvas],
  )
  return <primitive object={meshes.group} />
}

/** The canvas says which of the fx store's pictures it has drawn (its version), for e2e. */
function markDrawn(canvas: HTMLCanvasElement): void {
  canvas.setAttribute('data-fx-drawn', String(fx.version))
}
