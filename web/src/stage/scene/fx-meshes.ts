// "Effects in space"'s three objects (§7.4): one InstancedMesh each for the particles, the rings and
// the planes. Their attributes are the fx writer's own arrays, so a picture is written once and only
// flagged here; each mesh draws as many instances as the writer wrote, and is made again only when the
// writer's arrays grow. Their materials, and the outline's mask, are FxMaterials: made once per home.
import { DynamicDrawUsage, Group, InstancedBufferAttribute, InstancedMesh, PlaneGeometry, type DataTexture, type ShaderMaterial } from 'three'
import type { Home } from '@/api/contract'
import type { CameraPose } from '../camera'
import type { FxBatch, FxWriter } from '../fx-writer'
import { bounds } from '../plan'
import { roomMask } from '../room-mask'
import { particleMaterial, planeMaterial, ringMaterial } from './fx-shaders'
import { maskTexture } from './light-shaders'

/** The fx's materials and the home outline's mask: once per home. */
export class FxMaterials {
  readonly particle = particleMaterial()
  readonly ring = ringMaterial()
  readonly plane: ShaderMaterial
  private readonly texture: DataTexture

  constructor(home: Pick<Home, 'outline' | 'ceiling'>) {
    // The outline as one room: a plane draws only inside the home (§7.4: "clipped to the apartment outline").
    const mask = roomMask([{ polygon: home.outline }])
    this.texture = maskTexture(mask)
    const { min, max } = bounds(home.outline)
    const [halfX, halfY, halfZ] = [(max[0] - min[0]) / 2, (max[1] - min[1]) / 2, home.ceiling / 2]
    this.plane = planeMaterial({
      mask,
      texture: this.texture,
      ceilingM: home.ceiling,
      // In three's world (plan.ts's toWorld): x, then up, then the plan's y.
      centre: [min[0] + halfX, halfZ, min[1] + halfY],
      reachM: Math.hypot(halfX, halfY, halfZ),
    })
  }

  /** The pose's scale and the way the camera looks. */
  setView(pose: CameraPose): void {
    this.particle.uniforms.pxPerM.value = pose.zoom
    this.plane.uniforms.back.value.set(...pose.back)
  }

  dispose(): void {
    for (const item of [this.particle, this.ring, this.plane, this.texture]) item.dispose()
  }
}

/** The attributes each kind's batch feeds, in the writer's order of its arrays. */
const NAMES = {
  particles: ['centre', 'colour', 'size'],
  rings: ['centre', 'colour', 'shape'],
  planes: ['point', 'planeNormal', 'ray', 'colour', 'width'],
} as const

type Kind = keyof typeof NAMES

interface Drawn {
  mesh: InstancedMesh | null
  generation: number
  attributes: InstancedBufferAttribute[]
}

export class FxMeshes {
  readonly group = new Group()
  private readonly writer: FxWriter
  private readonly materials: Record<Kind, ShaderMaterial>
  private readonly drawn: Record<Kind, Drawn> = {
    particles: { mesh: null, generation: -1, attributes: [] },
    rings: { mesh: null, generation: -1, attributes: [] },
    planes: { mesh: null, generation: -1, attributes: [] },
  }

  constructor(writer: FxWriter, materials: FxMaterials) {
    this.writer = writer
    this.materials = { particles: materials.particle, rings: materials.ring, planes: materials.plane }
  }

  /** After FxWriter.write(): draws as many of each as it wrote, sending them to the GPU. */
  update(): void {
    for (const kind of Object.keys(NAMES) as Kind[]) this.updateKind(kind, this.writer[kind])
  }

  private updateKind(kind: Kind, batch: FxBatch): void {
    const drawn = this.drawn[kind]
    if (drawn.generation !== batch.generation) this.remake(kind, batch)
    if (drawn.mesh === null) return
    drawn.mesh.count = batch.count
    drawn.mesh.visible = batch.count > 0
    for (const attribute of drawn.attributes) attribute.needsUpdate = true
  }

  /** New arrays, larger ones: a new mesh over them. */
  private remake(kind: Kind, batch: FxBatch): void {
    const drawn = this.drawn[kind]
    this.drop(drawn)
    drawn.generation = batch.generation
    if (batch.capacity === 0) return
    const geometry = new PlaneGeometry(2, 2)
    drawn.attributes = batch.arrays.map((array, i) => {
      const attribute = new InstancedBufferAttribute(array, array.length / batch.capacity).setUsage(DynamicDrawUsage)
      geometry.setAttribute(NAMES[kind][i], attribute)
      return attribute
    })
    const mesh = new InstancedMesh(geometry, this.materials[kind], batch.capacity)
    // The instance matrices stay identity, so three's bounds would be wrong: never cull.
    mesh.frustumCulled = false
    drawn.mesh = mesh
    this.group.add(mesh)
  }

  private drop(drawn: Drawn): void {
    if (drawn.mesh === null) return
    this.group.remove(drawn.mesh)
    drawn.mesh.geometry.dispose()
    drawn.mesh.dispose()
    drawn.mesh = null
    drawn.attributes = []
  }

  dispose(): void {
    for (const drawn of Object.values(this.drawn)) this.drop(drawn)
  }
}
