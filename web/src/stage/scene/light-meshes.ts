// The lights' three objects (§7.5): "One InstancedMesh for cores, one for halos, one for pools", and
// the strips as two LineSegments2 (SPEC.stripPx's two widths). Their attributes are the frame
// writer's own arrays, so a frame is written once and only flagged here. The halos, cores and strips
// sit LIFT_M toward the camera: a lamp's halo is a flat disc facing the camera, and lifted it clears
// the floor and the wall it hangs on while a wall in front still hides it.
import {
  DynamicDrawUsage,
  Group,
  InstancedBufferAttribute,
  InstancedMesh,
  PlaneGeometry,
  type DataTexture,
  type InterleavedBufferAttribute,
  type ShaderMaterial,
} from 'three'
import { LineMaterial } from 'three/addons/lines/LineMaterial.js'
import { LineSegments2 } from 'three/addons/lines/LineSegments2.js'
import { LineSegmentsGeometry } from 'three/addons/lines/LineSegmentsGeometry.js'
import type { CameraPose } from '../camera'
import { SPEC } from '../design-numbers'
import type { FrameWriter, StripBuffers } from '../frame-writer'
import type { RoomMask } from '../room-mask'
import { coreMaterial, haloMaterial, maskTexture, poolMaterial } from './light-shaders'

export const LIFT_M = 0.5

function attribute(array: Float32Array, size: number): InstancedBufferAttribute {
  return new InstancedBufferAttribute(array, size).setUsage(DynamicDrawUsage)
}

/** A quad per instance; the shaders place and size each from its attributes. */
function instanced(count: number, material: ShaderMaterial, attributes: Record<string, InstancedBufferAttribute>): InstancedMesh {
  const geometry = new PlaneGeometry(2, 2)
  for (const [name, value] of Object.entries(attributes)) geometry.setAttribute(name, value)
  const mesh = new InstancedMesh(geometry, material, count)
  // The instance matrices stay identity, so three's bounds would be wrong: never cull.
  mesh.frustumCulled = false
  return mesh
}

function strips(buffers: StripBuffers, width: number): { object: LineSegments2; colours: InterleavedBufferAttribute } {
  const geometry = new LineSegmentsGeometry().setPositions(buffers.positions).setColors(buffers.colours)
  const object = new LineSegments2(geometry, new LineMaterial({ vertexColors: true, linewidth: width, worldUnits: false }))
  object.frustumCulled = false
  return { object, colours: geometry.getAttribute('instanceColorStart') as InterleavedBufferAttribute }
}

export class LightMeshes {
  /** Halos, cores and strips, lifted toward the camera. */
  readonly lifted = new Group()
  /** The pools, on the floor. */
  readonly pools: InstancedMesh | null = null
  private readonly dynamic: InstancedBufferAttribute[] = []
  private readonly stripColours: InterleavedBufferAttribute[] = []
  private readonly discs: ShaderMaterial[] = []
  private readonly lines: LineMaterial[] = []
  private readonly disposables: { dispose(): void }[] = []
  private readonly texture: DataTexture

  constructor(writer: FrameWriter, mask: RoomMask) {
    this.texture = maskTexture(mask)
    this.disposables.push(this.texture)
    if (writer.glows > 0) {
      const centres = attribute(writer.glowCentres, 3)
      const haloColours = attribute(writer.haloColours, 3)
      const haloSizes = attribute(writer.haloSizes, 1)
      const poolColours = attribute(writer.poolColours, 3)
      const poolRadii = attribute(writer.poolRadii, 1)
      this.dynamic.push(haloColours, haloSizes, poolColours, poolRadii)
      const halo = haloMaterial()
      const pool = poolMaterial(mask, this.texture)
      this.discs.push(halo)
      const room = new InstancedBufferAttribute(writer.glowRooms, 1)
      this.pools = instanced(writer.glows, pool, { centre: centres, colour: poolColours, radius: poolRadii, room })
      this.lifted.add(instanced(writer.glows, halo, { centre: centres, colour: haloColours, size: haloSizes }))
      this.disposables.push(halo, pool)
    }
    if (writer.cores > 0) {
      const colours = attribute(writer.coreColours, 3)
      const sizes = attribute(writer.coreSizes, 1)
      this.dynamic.push(colours, sizes)
      const core = coreMaterial()
      this.discs.push(core)
      this.lifted.add(instanced(writer.cores, core, { centre: attribute(writer.coreCentres, 3), colour: colours, size: sizes }))
      this.disposables.push(core)
    }
    for (const [buffers, width] of [
      [writer.narrow, SPEC.stripPx.min],
      [writer.wide, SPEC.stripPx.max],
    ] as const) {
      if (buffers.segments === 0) continue
      const { object, colours } = strips(buffers, width)
      this.lifted.add(object)
      this.stripColours.push(colours)
      this.lines.push(object.material)
      this.disposables.push(object.geometry, object.material)
    }
    for (const object of this.lifted.children) if (object instanceof InstancedMesh) this.disposables.push(object.geometry)
    if (this.pools !== null) this.disposables.push(this.pools.geometry)
  }

  /** The pose's size for the screen-space discs and lines, and the lift toward its camera. */
  setView(pose: CameraPose): void {
    for (const material of this.discs) material.uniforms.viewport.value.set(pose.width, pose.height)
    for (const material of this.lines) material.resolution.set(pose.width, pose.height)
    this.lifted.position.set(pose.back[0] * LIFT_M, pose.back[1] * LIFT_M, pose.back[2] * LIFT_M)
  }

  /** After FrameWriter.write(): sends what it wrote to the GPU. */
  update(): void {
    for (const item of this.dynamic) item.needsUpdate = true
    for (const colours of this.stripColours) colours.data.needsUpdate = true
  }

  dispose(): void {
    for (const item of this.disposables) item.dispose()
  }
}
