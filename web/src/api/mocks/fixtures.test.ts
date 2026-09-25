import { describe, expect, it } from 'vitest'
import homeJson from './home.json'
import looksJson from './looks.json'
import {
  HOME_TOTALS, HOME_ZONE, OWNER_ROOM_NAMES, coversOf, homeFixture, lightFixtures, lookFixtures, lookName, roomName,
  withOwnerNames, zoneFixtures,
} from './fixtures'

const SINCE = '2026-09-23T17:04:00.000Z'
const lights = lightFixtures(SINCE)

describe('the fixtures', () => {
  it('builds every light in home.json, and their LEDs add up to its totals', () => {
    expect(lights).toHaveLength(HOME_TOTALS.lights)
    expect(lights.reduce((sum, light) => sum + light.leds, 0)).toBe(HOME_TOTALS.leds)
  })

  it("gives each light the shape the file's flat fields describe", () => {
    for (const raw of homeJson.lights) {
      const shape = lights.find((light) => light.id === raw.id)?.shape
      expect(shape?.kind).toBe(raw.shape)
      if (shape?.kind === 'point' && 'position' in raw) expect(shape.position).toEqual(raw.position)
      if (shape?.kind === 'bent-line' && 'path' in raw) expect(shape.path).toEqual(raw.path)
      if (shape?.kind === 'line') expect(shape.path).toHaveLength(2)
      if (shape?.kind === 'grid') expect(shape.rotation).toEqual([0, 0, 0])
    }
  })

  it('reads capabilities in lower case, with no MAC and only documentation addresses', () => {
    for (const light of lights) {
      expect(light.capabilities.every((name) => name === name.toLowerCase())).toBe(true)
      expect(light.mac ?? null).toBeNull()
      expect(light.address).toMatch(/^192\.0\.2\.\d+$/)
      expect(light).toMatchObject({ status: 'idle', statusSince: SINCE, power: false, sendFps: 0 })
    }
    expect(new Set(lights.map((light) => light.address)).size).toBe(lights.length)
  })

  it("serves the handoff's looks, built in, each needing its inputs", () => {
    expect(lookFixtures.map((look) => look.id)).toEqual(looksJson.looks.map((look) => look.id))
    for (const raw of looksJson.looks) {
      const look = lookFixtures.find((candidate) => candidate.id === raw.id)
      expect(look).toMatchObject({ name: raw.name, builtIn: true, needs: raw.inputs, description: raw.description })
      expect(lookName(raw.id)).toBe(raw.name)
    }
    expect(() => lookName('nope')).toThrow('nope')
  })

  it('makes a zone of the whole home, of each room with lights, and of each sub-zone', () => {
    const zones = zoneFixtures(homeFixture, lights)
    expect(zones[0]).toMatchObject({ id: HOME_ZONE, kind: 'home', lights: lights.map((light) => light.id) })
    const rooms = zones.filter((zone) => zone.kind === 'room')
    expect(rooms.map((zone) => zone.id)).toEqual(homeFixture.rooms.filter((room) => room.hasLights).map((room) => room.id))
    for (const zone of rooms) {
      expect(zone.name).toBe(roomName(zone.id))
      expect(zone.lights).toEqual(lights.filter((light) => light.room === zone.id).map((light) => light.id))
    }
    const subZones = zones.filter((zone) => zone.kind === 'sub-zone')
    expect(subZones.map((zone) => zone.id)).toEqual(homeFixture.subZones.map((sub) => sub.id))
  })

  it('lists the rooms a zone covers in the order of its lights', () => {
    expect(coversOf(homeFixture, lights, ['kcorner', 'bedl', 'kfloor', 'neon'])).toEqual([
      roomName('kitchen'),
      roomName('bedroom'),
      roomName('corridor'),
    ])
  })

  it("gives the PC's parts an id each, as engine M2 will", () => {
    const pc = lights.find((light) => light.id === 'pc')
    expect(pc?.parts?.length).toBeGreaterThan(1)
    expect(new Set(pc?.parts?.map((part) => (part as { id?: string }).id)).size).toBe(pc?.parts?.length)
  })

  it("names the room corridor Entrance, the owner's decision, and keeps every other name", () => {
    expect(OWNER_ROOM_NAMES).toEqual({ corridor: 'Entrance' })
    const raw = new Map(homeJson.rooms.map((room) => [room.id, room.name]))
    expect(raw.has('corridor')).toBe(true)
    for (const room of homeFixture.rooms) expect(room.name).toBe(OWNER_ROOM_NAMES[room.id] ?? raw.get(room.id))
    expect(roomName('corridor')).toBe('Entrance')
  })

  it("leaves a room alone once home.json has the owner's name", () => {
    const named = { ...homeFixture.rooms[0], id: 'corridor', name: 'Entrance' }
    expect(withOwnerNames([named])).toEqual([named])
    expect(withOwnerNames([{ ...named, name: 'Hall' }])).toEqual([named])
  })
})
