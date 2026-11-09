// "Effects in space" on the canvas (§7.4): the fx store's picture of the zones the stage picks, drawn
// on the stage's cadence beside the lights (draw-list.ts). Pictures never pass through React: the
// layer writes the store's newest into its meshes' arrays when the cadence asks, and a new pick (the
// composer's preview, focus's zone) is written at once. The canvas's `data-fx-drawn` says what it
// shows (DrawnMark): e2e waits for it before a screenshot (e2e/helpers.ts, fxPictured()). One DOM
// write a picture or a pick, none an idle frame (§7.5).
import { useFrame, useThree } from '@react-three/fiber'
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
  const mark = useMemo(() => new DrawnMark(canvas), [canvas])
  // Gone, the picture goes with it: the canvas draws once more without it.
  useEffect(
    () => () => {
      meshes.dispose()
      mark.clear()
      invalidate()
    },
    [meshes, mark, invalidate],
  )
  useLayoutEffect(() => {
    materials.setView(pose)
    invalidate()
  }, [materials, pose, invalidate])
  useLayoutEffect(() => {
    writer.write(fx, pick)
    meshes.update()
    mark.clear()
    mark.willRender()
    invalidate()
  }, [writer, meshes, pick, mark, invalidate])
  useLayoutEffect(
    () =>
      drawList.add(() => {
        if (!writer.write(fx, pick)) {
          mark.unchanged(writer.previewing)
          return false
        }
        meshes.update()
        mark.willRender()
        return true
      }),
    [drawList, writer, meshes, pick, mark],
  )
  // Before three draws, in the task that renders the canvas.
  useFrame(() => mark.rendered(writer.previewing))
  return <primitive object={meshes.group} />
}

/**
 * e2e's sign of what the canvas shows (fxPictured()): `data-fx-drawn` is how many pictures the fx store had stored
 * (FxStore.stored) when the canvas drew, and " preview" after it while that has a preview's. It's written in the task
 * that renders, before three draws, or at once for a picture that changes nothing drawn, as the canvas shows it
 * already; a new pick takes it away until the canvas has drawn it, and so does the layer going.
 */
class DrawnMark {
  private readonly canvas: HTMLCanvasElement
  private shown: string | null = null
  private rendering = false

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas
  }

  /** The canvas no longer shows what the mark says. */
  clear(): void {
    if (this.shown === null) return
    this.shown = null
    this.canvas.removeAttribute('data-fx-drawn')
  }

  /** A render is on its way with what was written: marked as it renders. */
  willRender(): void {
    this.rendering = true
  }

  /** The canvas renders now. */
  rendered(previewing: boolean): void {
    if (!this.rendering) return
    this.rendering = false
    this.show(previewing)
  }

  /** A picture that changed nothing drawn: the canvas shows it already, unless a render is still on its way. */
  unchanged(previewing: boolean): void {
    if (!this.rendering) this.show(previewing)
  }

  private show(previewing: boolean): void {
    const shown = previewing ? `${fx.stored} preview` : String(fx.stored)
    if (shown === this.shown) return
    this.shown = shown
    this.canvas.setAttribute('data-fx-drawn', shown)
  }
}
