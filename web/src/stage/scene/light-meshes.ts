// The lights' three objects (§7.5): "One InstancedMesh for cores, one for halos, one for pools", and
// the strips as two LineSegments2 (SPEC.stripPx's two widths). Their attributes are the frame
// writer's own arrays, so a frame is written once and only flagged here. The halos, cores and strips
// sit LIFT_M toward the camera: a lamp's halo is a flat disc facing the camera, and lifted it clears
// the floor and the wall it hangs on while a wall in front still hides it. Their materials, and the
// room mask's texture, are LightMaterials: made once per mask and shared by every LightMeshes, so a
// light that stops being drawn makes new meshes, but no shader is compiled again (I1).
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

function strips(buffers: StripBuffers, material: LineMaterial): { object: LineSegments2; colours: InterleavedBufferAttribute } {
  const geometry = new LineSegmentsGeometry().setPositions(buffers.positions).setColors(buffers.colours)
  const object = new LineSegments2(geometry, material)
  object.frustumCulled = false
  return { object, colours: geometry.getAttribute('instanceColorStart') as InterleavedBufferAttribute }
}

const stripMaterial = (width: number) => new LineMaterial({ vertexColors: true, linewidth: width, worldUnits: false })

/** The lights' materials and the room mask's texture: once per mask, whatever the lights do. */
export class LightMaterials {
  readonly halo = haloMaterial()
  readonly core = coreMaterial()
  readonly pool: ShaderMaterial
  /** The strips' two widths, SPEC.stripPx's. */
  readonly narrow = stripMaterial(SPEC.stripPx.min)
  readonly wide = stripMaterial(SPEC.stripPx.max)
  private readonly texture: DataTexture

  constructor(mask: RoomMask) {
    this.texture = maskTexture(mask)
    this.pool = poolMaterial(mask, this.texture)
  }

  /** The pose's size, for the screen-space discs and lines. */
  setView(pose: CameraPose): void {
    for (const material of [this.halo, this.core]) material.uniforms.viewport.value.set(pose.width, pose.height)
    for (const material of [this.narrow, this.wide]) material.resolution.set(pose.width, pose.height)
  }

  dispose(): void {
    for (const item of [this.halo, this.core, this.pool, this.narrow, this.wide, this.texture]) item.dispose()
  }
}

export class LightMeshes {
  /** Halos, cores and strips, lifted toward the camera. */
  readonly lifted = new Group()
  /** The pools, on the floor. */
  readonly pools: InstancedMesh | null = null
  private readonly dynamic: InstancedBufferAttribute[] = []
  private readonly stripColours: InterleavedBufferAttribute[] = []
  /** Its own: the materials are shared, and LightMaterials lets go of them. */
  private readonly disposables: { dispose(): void }[] = []

  constructor(writer: FrameWriter, materials: LightMaterials) {
    if (writer.glows > 0) {
      const centres = attribute(writer.glowCentres, 3)
      const haloColours = attribute(writer.haloColours, 3)
      const haloSizes = attribute(writer.haloSizes, 1)
      const poolColours = attribute(writer.poolColours, 3)
      const poolRadii = attribute(writer.poolRadii, 1)
      this.dynamic.push(haloColours, haloSizes, poolColours, poolRadii)
      const room = new InstancedBufferAttribute(writer.glowRooms, 1)
      this.pools = instanced(writer.glows, materials.pool, { centre: centres, colour: poolColours, radius: poolRadii, room })
      this.lifted.add(instanced(writer.glows, materials.halo, { centre: centres, colour: haloColours, size: haloSizes }))
    }
    if (writer.cores > 0) {
      const colours = attribute(writer.coreColours, 3)
      const sizes = attribute(writer.coreSizes, 1)
      this.dynamic.push(colours, sizes)
      this.lifted.add(instanced(writer.cores, materials.core, { centre: attribute(writer.coreCentres, 3), colour: colours, size: sizes }))
    }
    for (const [buffers, material] of [
      [writer.narrow, materials.narrow],
      [writer.wide, materials.wide],
    ] as const) {
      if (buffers.segments === 0) continue
      const { object, colours } = strips(buffers, material)
      this.lifted.add(object)
      this.stripColours.push(colours)
      this.disposables.push(object.geometry)
    }
    // Mi6: an instanced mesh holds buffers of its own (its instance matrices) beside its geometry's.
    for (const object of [this.pools, ...this.lifted.children]) {
      if (object instanceof InstancedMesh) this.disposables.push(object.geometry, object)
    }
  }

  /** The lift toward the pose's camera. */
  setView(pose: CameraPose): void {
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
