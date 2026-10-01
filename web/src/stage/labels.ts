// §7.6 live: "labels (room caps + running look in serif italic)". Every room gets its name; a room
// whose lights a look runs on gets the look beneath, the newest one there. A running sub-zone gets a
// label of its own at its middle, as Main.png shows one, and its lights don't count for its room.
import type { Home, Id, Light, RunningZone, Vec3 } from '@/api/contract'
import { centroid } from './plan'

export interface StageLabel {
  key: string
  /** As the server names the room: CSS draws it in caps. */
  name: string
  look: string | null
  /** On the floor, in plan metres. */
  at: Vec3
}

export function stageLabels(home: Home, running: readonly RunningZone[], lights: readonly Light[]): StageLabel[] {
  const subZones = new Map(home.subZones.map((subZone) => [subZone.id, subZone]))
  const roomOf = new Map<Id, Id | null | undefined>(lights.map((light) => [light.id, light.room]))
  const newestFirst = [...running].sort((a, b) => Date.parse(b.since) - Date.parse(a.since))
  const wide = newestFirst.filter((zone) => !subZones.has(zone.zoneId))
  const rooms = home.rooms.map((room): StageLabel => {
    const zone = wide.find((candidate) => candidate.lights.some((id) => roomOf.get(id) === room.id))
    return { key: room.id, name: room.name, look: zone?.lookName ?? null, at: [room.labelAt[0], room.labelAt[1], 0] }
  })
  const parts = newestFirst.flatMap((zone): StageLabel[] => {
    const subZone = subZones.get(zone.zoneId)
    if (subZone === undefined) return []
    const [x, y] = centroid(subZone.polygon)
    return [{ key: subZone.id, name: subZone.name, look: zone.lookName, at: [x, y, 0] }]
  })
  return [...rooms, ...parts]
}
