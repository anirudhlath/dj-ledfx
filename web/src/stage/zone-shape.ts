// Where a zone is on the stage: its floor polygons, for §8.1's "Hover a card → its zone outlines on the
// stage", the rooms it lights, which §7.6 compose leaves undimmed, and the middle of its lights, where its
// tag goes (F3 decision 18), in plan metres; and where a card beside it goes, in CSS px.
import type { Home, Id, Light, Vec2, Vec3, Zone } from '@/api/contract'
import type { ElementSize } from '@/lib/use-element-size'
import type { Body } from './bodies'
import { anchorOf } from './marks'

/** A room's or a sub-zone's own polygon, the home's outline, or for a group the rooms its lights stand in. */
export function zonePolygons(home: Home, zone: Zone | undefined, lights: readonly Light[]): Vec2[][] {
  if (zone === undefined) return []
  switch (zone.kind) {
    case 'home':
      return [home.outline]
    case 'room':
      return home.rooms.filter((room) => room.id === zone.id).map((room) => room.polygon)
    case 'sub-zone':
      return home.subZones.filter((sub) => sub.id === zone.id).map((sub) => sub.polygon)
    case 'group': {
      const members = new Set(zone.lights)
      const rooms = new Set(lights.filter((light) => members.has(light.id)).map((light) => light.room))
      return home.rooms.filter((room) => rooms.has(room.id)).map((room) => room.polygon)
    }
  }
}

/** The mean of the anchors of the lights' bodies; null when none of them is placed. */
export function zoneMiddle(bodies: readonly Body[], lights: readonly Id[]): Vec3 | null {
  const ids = new Set(lights)
  const anchors = bodies.filter((body) => ids.has(body.lightId)).map(anchorOf)
  if (anchors.length === 0) return null
  const sum = anchors.reduce<Vec3>((total, at) => [total[0] + at[0], total[1] + at[1], total[2] + at[2]], [0, 0, 0])
  return [sum[0] / anchors.length, sum[1] / anchors.length, sum[2] / anchors.length]
}

/**
 * The rooms a zone lights (§7.6 compose: "Rooms outside the chosen zone dimmed"): every room for the
 * whole home, a room itself, a sub-zone's room, and for a group the rooms its lights stand in.
 */
export function zoneRooms(home: Home, zone: Zone, lights: readonly Light[]): Set<Id> {
  switch (zone.kind) {
    case 'home':
      return new Set(home.rooms.map((room) => room.id))
    case 'room':
      return new Set([zone.id])
    case 'sub-zone':
      return new Set(home.subZones.filter((sub) => sub.id === zone.id).map((sub) => sub.room))
    case 'group': {
      const members = new Set(zone.lights)
      return new Set(lights.flatMap((light) => (members.has(light.id) && light.room != null ? [light.room] : [])))
    }
  }
}

/** A box round some points on the stage, CSS px. */
export interface StageBox {
  left: number
  top: number
  right: number
  bottom: number
}

/** The box round projected polygons; null for none. */
export function boxOf(polygons: readonly (readonly Vec2[])[]): StageBox | null {
  const points = polygons.flat()
  if (points.length === 0) return null
  const xs = points.map(([x]) => x)
  const ys = points.map(([, y]) => y)
  return { left: Math.min(...xs), top: Math.min(...ys), right: Math.max(...xs), bottom: Math.max(...ys) }
}

/**
 * Where a card goes beside a zone (F4 ruling 15; Live-PutLookOn's PREVIEW ON SCREEN): left of the zone
 * where it fits, else right of it, else over its middle; centred on it from top to bottom; and inside the
 * stage. Its top-left corner, CSS px.
 */
export function besideZone(zone: StageBox, stage: ElementSize, card: ElementSize): Vec2 {
  const left =
    zone.left - card.width >= 0
      ? zone.left - card.width
      : zone.right + card.width <= stage.width
        ? zone.right
        : (zone.left + zone.right - card.width) / 2
  const top = (zone.top + zone.bottom - card.height) / 2
  const inside = (value: number, room: number) => Math.min(Math.max(value, 0), Math.max(room, 0))
  return [inside(left, stage.width - card.width), inside(top, stage.height - card.height)]
}
