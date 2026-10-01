// What the home's static scene is made of (§7.1), in plan metres: prisms (walls cut at the home's
// wallCutHeight, window and glass-door sills, columns, furniture), glass panes, and the ghost
// volume's lines. Pure data; scene/build.ts turns it into three's geometry.
import type { Home, Vec2, Vec3, Wall } from '@/api/contract'
import { SPEC } from './design-numbers'
import { doubleArea } from './plan'

export type PrismKind = 'wall' | 'column' | 'furniture'

/** A polygon on the plan, extruded from z0 to z1. */
export interface Prism {
  kind: PrismKind
  polygon: Vec2[]
  z0: number
  z1: number
}

/** A window's or a glass door's glass: upright, along its wall, from its sill to the cut. */
export interface Pane {
  a: Vec2
  b: Vec2
  z0: number
  z1: number
  /** §7.1: the west bedroom windows, which looks that model the sun light (F10). */
  westFacing: boolean
}

export type Segment = [Vec3, Vec3]

/** The wall's footprint: its thickness either side of the line from a to b. */
export function wallPolygon(wall: Pick<Wall, 'a' | 'b' | 'thickness'>): Vec2[] {
  const [ax, ay] = wall.a
  const [bx, by] = wall.b
  const length = Math.hypot(bx - ax, by - ay) || 1
  const nx = (-(by - ay) / length) * (wall.thickness / 2)
  const ny = ((bx - ax) / length) * (wall.thickness / 2)
  return [
    [ax + nx, ay + ny],
    [bx + nx, by + ny],
    [bx - nx, by - ny],
    [ax - nx, ay - ny],
  ]
}

/** A furniture block's footprint: its polygon, or its box [x0, y0, x1, y1]. */
export function furniturePolygon(item: Home['furniture'][number]): Vec2[] | null {
  if (item.polygon != null && item.polygon.length >= 3) return item.polygon
  if (item.box == null) return null
  const [x0, y0, x1, y1] = item.box
  return [
    [x0, y0],
    [x1, y0],
    [x1, y1],
    [x0, y1],
  ]
}

/** Every solid of the home: wall pieces up to the cut (or a window's sill), columns, furniture. */
export function homePrisms(home: Home): Prism[] {
  const cut = home.wallCutHeight
  const walls = home.walls.map(
    (wall): Prism => ({ kind: 'wall', polygon: wallPolygon(wall), z0: 0, z1: wall.kind === 'wall' ? cut : sillOf(wall) }),
  )
  const columns = home.columns.map(
    ({ min, max }): Prism => ({
      kind: 'column',
      polygon: [min, [max[0], min[1]], max, [min[0], max[1]]],
      z0: 0,
      z1: cut + SPEC.columnAboveCutM,
    }),
  )
  const furniture = home.furniture.flatMap((item): Prism[] => {
    const polygon = furniturePolygon(item)
    return polygon === null ? [] : [{ kind: 'furniture', polygon, z0: item.z0, z1: item.z0 + item.height }]
  })
  return [...walls, ...columns, ...furniture]
}

const sillOf = (wall: Wall) => (wall.kind === 'glass-door' ? SPEC.glassDoorSillM : SPEC.window.sillM)

/** The glass of every window and glass door. */
export function homePanes(home: Home): Pane[] {
  return home.walls
    .filter((wall) => wall.kind !== 'wall')
    .map((wall) => ({ a: wall.a, b: wall.b, z0: sillOf(wall), z1: home.wallCutHeight, westFacing: wall.westFacing }))
}

/** §7.1 Ghost volume: the outline at the ceiling, and upright lines from the cut to it at each corner. */
export function ghostLines(home: Home): Segment[] {
  const { outline, ceiling, wallCutHeight } = home
  const ring = outline.map((p, i): Segment => {
    const q = outline[(i + 1) % outline.length]
    return [
      [p[0], p[1], ceiling],
      [q[0], q[1], ceiling],
    ]
  })
  const uprights = outline.map(
    ([x, y]): Segment => [
      [x, y, wallCutHeight],
      [x, y, ceiling],
    ],
  )
  return [...ring, ...uprights]
}

/** A polygon's edges as segments at height z, closed. */
export function outlineAt(polygon: readonly Vec2[], z: number): Segment[] {
  return polygon.map((p, i) => {
    const q = polygon[(i + 1) % polygon.length]
    return [
      [p[0], p[1], z],
      [q[0], q[1], z],
    ]
  })
}

/** Each edge's outward normal on the plan, whichever way the polygon winds. */
export function outwardNormals(polygon: readonly Vec2[]): Vec2[] {
  const sign = doubleArea(polygon) >= 0 ? 1 : -1
  return polygon.map((p, i) => {
    const q = polygon[(i + 1) % polygon.length]
    const length = Math.hypot(q[0] - p[0], q[1] - p[1]) || 1
    return [(sign * (q[1] - p[1])) / length, (sign * -(q[0] - p[0])) / length]
  })
}

/**
 * Whether a side with this outward normal faces the camera: whether it points the way the camera
 * stands back from the home (the pose's `back`, in three's world, whose (x, z) is the plan's (x, y)).
 */
export function facesCamera(normal: Vec2, back: Vec3): boolean {
  return normal[0] * back[0] + normal[1] * back[2] > 0
}
