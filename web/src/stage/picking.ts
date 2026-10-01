// What's under the pointer (§8.1): "Hover a light → tooltip. Click a room → /live/put?zone=<room>".
// Both work from the pose, in CSS px, so they need no raycaster: a light is the nearest of its
// projected samples within its halo's reach, a room the polygon that holds the floor point.
import type { Home, Id, Room, Vec2 } from '@/api/contract'
import type { Body } from './bodies'
import { floorPoint, projectPoint, type CameraPose } from './camera'
import { haloRadiusPx } from './light-maths'
import { contains } from './plan'

export interface ScreenPoint {
  lightId: Id
  at: Vec2
  /** How near the pointer must come, in CSS px: the light's halo at full intensity. */
  reach: number
}

/** Every sample of every body, where the pose draws it. */
export function screenPoints(pose: CameraPose, bodies: readonly Body[]): ScreenPoint[] {
  return bodies.flatMap((body) => {
    const reach = haloRadiusPx(body.form === 'compact', 1)
    return body.samples.map((sample) => ({ lightId: body.lightId, at: projectPoint(pose, sample), reach }))
  })
}

/** The light nearest (x, y) within its reach, or null. */
export function pickLight(points: readonly ScreenPoint[], x: number, y: number): Id | null {
  let best: Id | null = null
  let bestDistance = Infinity
  for (const point of points) {
    const distance = Math.hypot(point.at[0] - x, point.at[1] - y)
    if (distance <= point.reach && distance < bestDistance) {
      best = point.lightId
      bestDistance = distance
    }
  }
  return best
}

/** The room whose floor is under (x, y), or null. */
export function pickRoom(home: Pick<Home, 'rooms'>, pose: CameraPose, x: number, y: number): Room | null {
  const point = floorPoint(pose, x, y)
  return home.rooms.find((room) => contains(room.polygon, point)) ?? null
}
