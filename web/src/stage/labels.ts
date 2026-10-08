// §7.6 live: "labels (room caps + running look in serif italic)". Every room gets its name; a room
// whose lights a look runs on gets the look beneath, the newest one there. A running sub-zone gets a
// label of its own at its middle, as Main.png shows one, and its lights don't count for its room. A zone
// turning from one look into another names both, as State-Transition does ("Fireflies → Embers").
// In the composer the look previewed on its zone counts as the newest on the zone's lights, so
// Live-PutLookOn labels the room with the look it previews.
import type { Home, Id, Light, RunningZone, Vec3, Zone } from '@/api/contract'
import { centroid } from './plan'
import { newestFirst } from './show'

export interface StageLabel {
  key: string
  /** As the server names the room: CSS draws it in caps. */
  name: string
  look: string | null
  /** On the floor, in plan metres. */
  at: Vec3
}

/** The composer's look on its zone, while the stage draws it from the preview stream. */
export interface PreviewedLook {
  zoneId: Id
  lookName: string
  lights: readonly Id[]
}

type Labelled = PreviewedLook & Partial<Pick<RunningZone, 'state' | 'transition'>>

function lookOf(zone: Labelled): string {
  return zone.state === 'transition' && zone.transition != null ? `${zone.transition.from} → ${zone.lookName}` : zone.lookName
}

export function stageLabels(
  home: Home,
  running: readonly RunningZone[],
  lights: readonly Light[],
  preview: PreviewedLook | null = null,
): StageLabel[] {
  const subZones = new Map(home.subZones.map((subZone) => [subZone.id, subZone]))
  const roomOf = new Map<Id, Id | null | undefined>(lights.map((light) => [light.id, light.room]))
  // A zone the preview covers whole has nothing left to label.
  const covered = new Set(preview?.lights)
  const others = newestFirst(running).filter(
    (zone) => preview === null || (zone.zoneId !== preview.zoneId && !zone.lights.every((id) => covered.has(id))),
  )
  const newest: Labelled[] = preview === null ? others : [preview, ...others]
  const wide = newest.filter((zone) => !subZones.has(zone.zoneId))
  const rooms = home.rooms.map((room): StageLabel => {
    const zone = wide.find((candidate) => candidate.lights.some((id) => roomOf.get(id) === room.id))
    return { key: room.id, name: room.name, look: zone === undefined ? null : lookOf(zone), at: [room.labelAt[0], room.labelAt[1], 0] }
  })
  const parts = newest.flatMap((zone): StageLabel[] => {
    const subZone = subZones.get(zone.zoneId)
    if (subZone === undefined) return []
    const [x, y] = centroid(subZone.polygon)
    return [{ key: subZone.id, name: subZone.name, look: lookOf(zone), at: [x, y, 0] }]
  })
  return [...rooms, ...parts]
}

/**
 * The looks a zone's lights run now, its own first, then the newest: what the composer's preview card
 * says they still run (Live-PutLookOn: "The lights are still running <look>.").
 */
export function looksOn(zone: Pick<Zone, 'id' | 'lights'>, running: readonly RunningZone[]): string[] {
  const lights = new Set(zone.lights)
  const own = running.filter((candidate) => candidate.zoneId === zone.id)
  const others = newestFirst(running).filter((candidate) => candidate.zoneId !== zone.id && candidate.lights.some((id) => lights.has(id)))
  return [...new Set([...own, ...others].map((candidate) => candidate.lookName))]
}
