// Where a zone is on the stage: its floor polygons, for §8.1's "Hover a card → its zone outlines on the
// stage", and the middle of its lights, where its tag goes (F3 decision 18). Plan metres throughout.
import type { Home, Id, Light, Vec2, Vec3, Zone } from '@/api/contract'
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
