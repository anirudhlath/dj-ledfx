// Plan geometry (spec §7.1): metres, x east, y south, z up, origin at the plan's north-west corner.
// three's world is (x, z, y): y up, +z south. Pure maths, shared by the scene and the overlays.
import type { Vec2, Vec3 } from '@/api/contract'

/** A plan point in three's world: (x, z, y). */
export const toWorld = ([x, y, z]: Vec3): Vec3 => [x, z, y]

/** Twice the polygon's signed area: positive when it runs clockwise on the plan (y points south). */
export function doubleArea(polygon: readonly Vec2[]): number {
  let sum = 0
  for (let i = 0; i < polygon.length; i++) {
    const [x0, y0] = polygon[i]
    const [x1, y1] = polygon[(i + 1) % polygon.length]
    sum += x0 * y1 - x1 * y0
  }
  return sum
}

/** The polygon's centre of area; the mean of its corners when it has none. */
export function centroid(polygon: readonly Vec2[]): Vec2 {
  const area = doubleArea(polygon)
  if (Math.abs(area) < 1e-12) {
    const n = Math.max(polygon.length, 1)
    return [polygon.reduce((s, p) => s + p[0], 0) / n, polygon.reduce((s, p) => s + p[1], 0) / n]
  }
  let cx = 0
  let cy = 0
  for (let i = 0; i < polygon.length; i++) {
    const [x0, y0] = polygon[i]
    const [x1, y1] = polygon[(i + 1) % polygon.length]
    const cross = x0 * y1 - x1 * y0
    cx += (x0 + x1) * cross
    cy += (y0 + y1) * cross
  }
  return [cx / (3 * area), cy / (3 * area)]
}

/** Whether the point is inside the polygon (even-odd rule; a point on an edge may go either way). */
export function contains(polygon: readonly Vec2[], [x, y]: Vec2): boolean {
  let inside = false
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const [xi, yi] = polygon[i]
    const [xj, yj] = polygon[j]
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside
  }
  return inside
}

/** The smallest box around the points. */
export function bounds(points: readonly Vec2[]): { min: Vec2; max: Vec2 } {
  const xs = points.map((p) => p[0])
  const ys = points.map((p) => p[1])
  return { min: [Math.min(...xs), Math.min(...ys)], max: [Math.max(...xs), Math.max(...ys)] }
}
