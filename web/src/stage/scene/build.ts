// three's geometry for the home (§7.1), from home-geometry.ts's data. Everything is in three's world
// (plan (x, y, z) → (x, z, y)) with vertex colours, so the whole static home is a handful of draw
// calls. Sides are coloured by whether they face the camera, and recoloured when the view turns.
import { BufferAttribute, BufferGeometry, ShapeUtils, Vector2 } from 'three'
import { LineSegmentsGeometry } from 'three/addons/lines/LineSegmentsGeometry.js'
import type { Vec2, Vec3 } from '@/api/contract'
import { facesCamera, outwardNormals, type Pane, type Prism, type Segment } from '../home-geometry'
import type { Colour } from '../light-maths'
import { STAGE_PALETTE, type StagePalette } from '../palette'
import { toWorld } from '../plan'

/** The triangles that fill a polygon, as indices into it. */
export function triangulate(polygon: readonly Vec2[]): number[][] {
  return ShapeUtils.triangulateShape(
    polygon.map(([x, y]) => new Vector2(x, y)),
    [],
  )
}

/** A geometry of positions alone, three numbers a vertex in three's world. */
function positionGeometry(positions: readonly number[]): BufferGeometry {
  const geometry = new BufferGeometry()
  geometry.setAttribute('position', new BufferAttribute(new Float32Array(positions), 3))
  return geometry
}

/** An upright quad on the plan line from a to b, from z0 to z1: two triangles' six vertices, in three's world. */
function uprightQuad(a: Vec2, b: Vec2, z0: number, z1: number): Vec3[] {
  const corners: [Vec2, number][] = [
    [a, z0],
    [b, z0],
    [b, z1],
    [a, z0],
    [b, z1],
    [a, z1],
  ]
  return corners.map(([point, z]) => toWorld([point[0], point[1], z]))
}

/** Flat polygons at height z, one colour: the floors, the courtyard, the balcony. */
export function flatGeometry(polygons: readonly (readonly Vec2[])[], z: number): BufferGeometry {
  const positions: number[] = []
  for (const polygon of polygons) {
    for (const triangle of triangulate(polygon)) {
      for (const index of triangle) positions.push(...toWorld([polygon[index][0], polygon[index][1], z]))
    }
  }
  return positionGeometry(positions)
}

const TOP: Record<Prism['kind'], keyof StagePalette> = { wall: 'wallTop', column: 'columnTop', furniture: 'furnitureTop' }
const SIDES: Record<Prism['kind'], [keyof StagePalette, keyof StagePalette]> = {
  wall: ['wallSide', 'wallSide2'],
  column: ['wallSide', 'wallSide2'],
  furniture: ['furnitureSide', 'furnitureSide2'],
}

/** One side of a prism: where its six vertices start in the buffer, and which way it faces. */
interface Side {
  first: number
  normal: Vec2
  kind: Prism['kind']
}

/**
 * Every prism's top and sides, in one geometry with vertex colours. `face(back)` colours the sides
 * for a camera standing back that way (camera.ts's pose); until then they're all the facing colour.
 */
export class SolidGeometry {
  readonly geometry = new BufferGeometry()
  private readonly sides: Side[] = []
  private readonly colours: Float32Array

  constructor(prisms: readonly Prism[]) {
    const palette = STAGE_PALETTE
    const positions: number[] = []
    const colours: number[] = []
    const vertex = (world: Vec3, colour: Colour) => {
      positions.push(...world)
      colours.push(...colour)
    }
    for (const prism of prisms) {
      const { polygon, z0, z1, kind } = prism
      for (const triangle of triangulate(polygon)) {
        for (const index of triangle) vertex(toWorld([polygon[index][0], polygon[index][1], z1]), palette[TOP[kind]])
      }
      outwardNormals(polygon).forEach((normal, i) => {
        this.sides.push({ first: positions.length / 3, normal, kind })
        for (const world of uprightQuad(polygon[i], polygon[(i + 1) % polygon.length], z0, z1)) vertex(world, palette.wallSide)
      })
    }
    this.colours = new Float32Array(colours)
    this.geometry.setAttribute('position', new BufferAttribute(new Float32Array(positions), 3))
    this.geometry.setAttribute('color', new BufferAttribute(this.colours, 3))
  }

  /** Colours the sides: the camera's side of each prism in its facing colour, the rest in the other. */
  face(back: Vec3): void {
    for (const side of this.sides) {
      const [facing, other] = SIDES[side.kind]
      const colour = STAGE_PALETTE[facesCamera(side.normal, back) ? facing : other]
      for (let v = 0; v < 6; v++) this.colours.set(colour, (side.first + v) * 3)
    }
    this.geometry.getAttribute('color').needsUpdate = true
  }
}

/** The windows' and glass doors' panes, upright along their walls. */
export function paneGeometry(panes: readonly Pane[]): BufferGeometry {
  return positionGeometry(panes.flatMap(({ a, b, z0, z1 }) => uprightQuad(a, b, z0, z1).flat()))
}

/** Plan segments as LineSegments2's geometry. */
export function segmentsGeometry(segments: readonly Segment[]): LineSegmentsGeometry {
  return new LineSegmentsGeometry().setPositions(new Float32Array(segments.flatMap(([a, b]) => [...toWorld(a), ...toWorld(b)])))
}
