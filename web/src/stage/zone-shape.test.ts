import { describe, expect, it } from 'vitest'
import type { Zone } from '@/api/contract'
import { buildScenario } from '@/api/mocks/scenarios'
import { HERO_NOW } from '@/test/live'
import { stageBodies } from './bodies'
import { anchorOf } from './marks'
import { zoneMiddle, zonePolygons } from './zone-shape'

const { home, lights, zones } = buildScenario('hero', HERO_NOW)
const zone = (id: string) => zones.find((each) => each.id === id)!

describe("a zone's place on the stage", () => {
  // §8.1: "Hover a card → its zone outlines on the stage".
  it("outlines a room, a sub-zone, the whole home, and a group's rooms", () => {
    expect(zonePolygons(home, zone('living'), lights)).toEqual([home.rooms.find((room) => room.id === 'living')!.polygon])
    expect(zonePolygons(home, zone('office'), lights)).toEqual([home.subZones.find((sub) => sub.id === 'office')!.polygon])
    expect(zonePolygons(home, zone('home'), lights)).toEqual([home.outline])
    const pair = [lights.find((light) => light.room === 'kitchen')!, lights.find((light) => light.room === 'bedroom')!]
    const group: Zone = { id: 'pair', name: 'Pair', kind: 'group', lights: pair.map((light) => light.id) }
    expect(zonePolygons(home, group, lights)).toEqual(
      home.rooms.filter((room) => room.id === 'kitchen' || room.id === 'bedroom').map((room) => room.polygon),
    )
    expect(zonePolygons(home, undefined, lights)).toEqual([])
  })

  // F3 decision 18.
  it("puts a zone's tag at the middle of its lights, and nowhere when none is placed", () => {
    const bodies = stageBodies(lights)
    const office = zone('office')
    const anchors = bodies.filter((body) => office.lights.includes(body.lightId)).map(anchorOf)
    const middle = zoneMiddle(bodies, office.lights)!
    for (const axis of [0, 1, 2]) expect(middle[axis]).toBeCloseTo(anchors.reduce((sum, at) => sum + at[axis], 0) / anchors.length)
    expect(zoneMiddle(bodies, ['nothing-here'])).toBeNull()
  })
})
