import { describe, expect, it } from 'vitest'
import type { Zone } from '@/api/contract'
import { buildScenario } from '@/api/mocks/scenarios'
import { HERO_NOW } from '@/test/live'
import { stageBodies } from './bodies'
import { anchorOf } from './marks'
import { besideZone, boxOf, zoneMiddle, zonePolygons, zoneRooms } from './zone-shape'

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

  // §7.6 compose: "Rooms outside the chosen zone dimmed".
  it('lights its own rooms: all of them for the whole home, its room for a sub-zone, its lights\' for a group', () => {
    expect(zoneRooms(home, zone('home'), lights)).toEqual(new Set(home.rooms.map((room) => room.id)))
    expect(zoneRooms(home, zone('living'), lights)).toEqual(new Set(['living']))
    expect(zoneRooms(home, zone('office'), lights)).toEqual(new Set([home.subZones.find((sub) => sub.id === 'office')!.room]))
    const pair = [lights.find((light) => light.room === 'kitchen')!, lights.find((light) => light.room === 'bedroom')!]
    const group: Zone = { id: 'pair', name: 'Pair', kind: 'group', lights: pair.map((light) => light.id) }
    expect(zoneRooms(home, group, lights)).toEqual(new Set(['kitchen', 'bedroom']))
  })

  // F4 ruling 15: Live-PutLookOn's card sits left of the room it previews on.
  it('puts a card left of its zone, else right, else over it, and keeps it on the stage', () => {
    const stage = { width: 1000, height: 800 }
    const card = { width: 200, height: 80 }
    const box = (left: number, right: number) => ({ left, right, top: 300, bottom: 500 })
    expect(besideZone(box(500, 700), stage, card)).toEqual([300, 360])
    expect(besideZone(box(100, 300), stage, card)).toEqual([300, 360])
    expect(besideZone(box(100, 900), stage, card)).toEqual([400, 360])
    expect(besideZone({ left: 500, right: 700, top: -100, bottom: 0 }, stage, card)).toEqual([300, 0])
    expect(boxOf([[[1, 5], [4, 2]], [[3, 9]]])).toEqual({ left: 1, top: 2, right: 4, bottom: 9 })
    expect(boxOf([])).toBeNull()
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
