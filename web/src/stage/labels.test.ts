import { describe, expect, it } from 'vitest'
import { lookName, OWNER_ROOM_NAMES, roomName } from '@/api/mocks/fixtures'
import { buildScenario } from '@/api/mocks/scenarios'
import { HERO_NOW } from '@/test/live'
import { looksOn, stageLabels } from './labels'

describe('the room labels (§7.6)', () => {
  it("names every room, with the look on its lights beneath, as Main.png does", () => {
    const hero = buildScenario('hero', HERO_NOW)
    const labels = stageLabels(hero.home, hero.running, hero.lights)
    const looks = Object.fromEntries(labels.map((label) => [label.key, label.look]))
    expect(labels.slice(0, hero.home.rooms.length).map((label) => label.name)).toEqual(hero.home.rooms.map((room) => roomName(room.id)))
    expect(looks).toMatchObject({
      living: lookName('fireflies'),
      kitchen: lookName('homesunset'),
      corridor: lookName('homesunset'),
      // The office desk runs its own look, so the rest of the bedroom shows the whole home's.
      bedroom: lookName('homesunset'),
      office: lookName('comets'),
      study: null,
    })
    // The owner's name for the corridor, not home.json's.
    expect(labels.find((label) => label.key === 'corridor')!.name).toBe(OWNER_ROOM_NAMES.corridor)
  })

  it('labels a sub-zone only while it runs', () => {
    const quiet = buildScenario('nothing-running', HERO_NOW)
    const labels = stageLabels(quiet.home, quiet.running, quiet.lights)
    expect(labels).toHaveLength(quiet.home.rooms.length)
    expect(labels.every((label) => label.look === null)).toBe(true)
  })

  // State-Transition: "LIVING ROOM" over "Fireflies → Embers" while one look turns into the other.
  it('names both looks while one turns into the other, as State-Transition does', () => {
    const turning = buildScenario('transition', HERO_NOW)
    const labels = stageLabels(turning.home, turning.running, turning.lights)
    expect(labels.find((label) => label.key === 'living')!.look).toBe(`${lookName('fireflies')} → ${lookName('embers')}`)
    expect(labels.find((label) => label.key === 'kitchen')!.look).toBe(lookName('homesunset'))
  })

  // Live-PutLookOn: the room's name over the look previewed there.
  it("names the composer's look on its zone, as the newest there", () => {
    const hero = buildScenario('hero', HERO_NOW)
    const zone = (id: string) => hero.zones.find((candidate) => candidate.id === id)!
    const previewed = (id: string) => ({ zoneId: id, lookName: lookName('embers'), lights: zone(id).lights })
    const looks = (id: string) =>
      Object.fromEntries(stageLabels(hero.home, hero.running, hero.lights, previewed(id)).map((label) => [label.key, label.look]))
    expect(looks('living')).toMatchObject({ living: lookName('embers'), kitchen: lookName('homesunset'), office: lookName('comets') })
    expect(looks('office')).toMatchObject({ office: lookName('embers'), bedroom: lookName('homesunset') })
    // The whole home covers the sub-zone's lights: its own label goes, and every lit room shows the preview.
    const home = looks('home')
    expect(home).toMatchObject({ living: lookName('embers'), bedroom: lookName('embers'), corridor: lookName('embers') })
    expect(home).not.toHaveProperty('office')
  })

  it('shows the newest look where two run on one room', () => {
    const hero = buildScenario('hero', HERO_NOW)
    const living = hero.running.find((zone) => zone.zoneId === 'living')!
    const older = { ...living, zoneId: 'kitchen-group', lookName: 'Older', since: '2026-09-23T10:00:00-05:00' }
    const labels = stageLabels(hero.home, [older, ...hero.running], hero.lights)
    expect(labels.find((label) => label.key === 'living')!.look).toBe(lookName('fireflies'))
  })
})

describe("the looks a zone's lights still run", () => {
  it('are its own look first, then the newest of the others on its lights', () => {
    const hero = buildScenario('hero', HERO_NOW)
    const zone = (id: string) => hero.zones.find((each) => each.id === id)!
    expect(looksOn(zone('living'), hero.running)).toEqual([lookName('fireflies')])
    expect(looksOn(zone('bedroom'), hero.running)).toEqual([lookName('comets'), lookName('homesunset')])
    const quiet = buildScenario('nothing-running', HERO_NOW)
    expect(looksOn(quiet.zones.find((each) => each.id === 'kitchen')!, quiet.running)).toEqual([])
  })
})
