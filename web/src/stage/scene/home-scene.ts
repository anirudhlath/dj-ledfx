// The static home (§7.1) as three's objects, made once per home: floors with their edges, the
// courtyard and the balcony, walls and windows cut at the home's wallCutHeight, columns, furniture,
// and the ghost volume. setView(pose, pixelRatio), as LightMeshes.setView(pose) does for the lights,
// colours the sides the camera sees and sizes the lines and patterns for the stage.
import { Group, Mesh, type Material, type ShaderMaterial } from 'three'
import { LineSegments2 } from 'three/addons/lines/LineSegments2.js'
import type { LineMaterial } from 'three/addons/lines/LineMaterial.js'
import type { Home } from '@/api/contract'
import type { CameraPose } from '../camera'
import { RENDER, SPEC } from '../design-numbers'
import { furniturePolygon, ghostLines, homePanes, homePrisms, outlineAt, type Segment } from '../home-geometry'
import { STAGE_PALETTE } from '../palette'
import { flatGeometry, paneGeometry, segmentsGeometry, SolidGeometry } from './build'
import { courtyardMaterial, flatMaterial, glassMaterial, hatchMaterial, lineMaterial, solidMaterial } from './materials'

/** Heights that keep coplanar things apart: the courtyard under the floors, edges just over them. */
const COURTYARD_Z = -0.005
const BALCONY_Z = -0.002
const EDGE_Z = 0.003

export class HomeScene {
  readonly group = new Group()
  private readonly solids: SolidGeometry
  private readonly lines: LineMaterial[] = []
  private readonly patterns: ShaderMaterial[] = []
  private readonly disposables: { dispose(): void }[] = []
  private back: CameraPose['back'] | null = null

  constructor(home: Home) {
    const palette = STAGE_PALETTE
    const mesh = (geometry: Mesh['geometry'], material: Material, order = 0) => {
      const object = new Mesh(geometry, material)
      object.renderOrder = order
      this.group.add(object)
      this.disposables.push(geometry, material)
      return object
    }
    const lines = (segments: Segment[], material: LineMaterial) => {
      if (segments.length === 0) return
      const geometry = segmentsGeometry(segments)
      this.group.add(new LineSegments2(geometry, material))
      this.lines.push(material)
      this.disposables.push(geometry, material)
    }

    const { courtyard, balcony } = home.outdoor ?? {}
    // The floors' edges, the balcony's among them: one line in one material.
    const edges = home.rooms.flatMap((room) => outlineAt(room.polygon, EDGE_Z))
    if (courtyard != null && courtyard.length >= 3) {
      const material = courtyardMaterial()
      this.patterns.push(material)
      mesh(flatGeometry([courtyard], COURTYARD_Z), material)
    }
    if (balcony != null && balcony.length >= 3) {
      const material = hatchMaterial()
      this.patterns.push(material)
      mesh(flatGeometry([balcony], BALCONY_Z), material)
      edges.push(...outlineAt(balcony, EDGE_Z))
    }
    mesh(
      flatGeometry(
        home.rooms.map((room) => room.polygon),
        0,
      ),
      flatMaterial(palette.floor),
    )
    lines(edges, lineMaterial(palette.floorEdge, SPEC.floorEdgePx))

    this.solids = new SolidGeometry(homePrisms(home))
    mesh(this.solids.geometry, solidMaterial())
    lines(
      home.furniture.flatMap((item) => {
        const polygon = furniturePolygon(item)
        return polygon === null ? [] : outlineAt(polygon, item.z0 + item.height)
      }),
      lineMaterial(palette.furnitureEdge, RENDER.furniture.edge.widthPx, RENDER.furniture.edge.alpha),
    )

    const panes = homePanes(home)
    if (panes.length > 0) mesh(paneGeometry(panes), glassMaterial(), 1)
    lines(
      panes.map(({ a, b, z1 }): Segment => [
        [a[0], a[1], z1],
        [b[0], b[1], z1],
      ]),
      lineMaterial(palette.text, SPEC.window.edgePx, SPEC.window.edgeAlpha),
    )
    lines(ghostLines(home), lineMaterial(palette.text, RENDER.ghost.widthPx, SPEC.ghostAlpha))
  }

  /** The camera's pose (which sides it sees, the stage's CSS size) and the canvas's pixel ratio. */
  setView(pose: CameraPose, pixelRatio: number): void {
    const { back } = pose
    if (this.back === null || back.some((value, axis) => value !== this.back![axis])) this.solids.face(back)
    this.back = back
    for (const material of this.lines) material.resolution.set(pose.width, pose.height)
    for (const material of this.patterns) material.uniforms.pixelRatio.value = pixelRatio
  }

  dispose(): void {
    for (const item of this.disposables) item.dispose()
  }
}
