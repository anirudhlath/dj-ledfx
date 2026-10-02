import { describe, expect, it } from 'vitest'
import type { Light } from '@/api/contract'
import { FrameStore } from '@/api/frames'
import { HOME_ZONE, roomName } from '@/api/mocks/fixtures'
import { buildScenario } from '@/api/mocks/scenarios'
import { formatTime } from '@/lib/format'
import { HERO_NOW } from '@/test/live'
import { lightState, newestFirst } from './show'
import { colourLine, currentColour, deviceLine, tooltipText } from './tooltip'

const hero = buildScenario('hero', HERO_NOW)
const named = (id: string) => hero.lights.find((light) => light.id === id)!
const ZONE_NAMES = new Map(hero.zones.map((zone) => [zone.id, zone.name]))

describe('the light tooltip (§7.6)', () => {
  it('names the light, the newest look running on it with its zone, and the model with its latency', () => {
    const light = hero.lights.find((candidate) => hero.running.some((zone) => zone.zoneId !== HOME_ZONE && zone.lights.includes(candidate.id)))!
    const zone = newestFirst(hero.running).find((candidate) => candidate.lights.includes(light.id))!
    expect(tooltipText(light, hero.running, ZONE_NAMES)).toEqual({ name: light.name, running: `${zone.lookName} · ${ZONE_NAMES.get(zone.zoneId)}` })
    expect(deviceLine({ ...light, latency: { estimated: false, measuredMs: 51.6 } }, null)).toBe(`${light.model} · 52 ms`)
  })

  it("says the owner's name for a room's zone", () => {
    const light = hero.lights.find((candidate) => candidate.room === 'corridor')!
    const corridor = { ...hero.running[0], zoneId: 'corridor', lights: [light.id], since: HERO_NOW.toISOString() }
    expect(tooltipText(light, [corridor], ZONE_NAMES).running).toBe(`${corridor.lookName} · ${roomName('corridor')}`)
  })

  it('marks an estimate, prefers an override, and leaves out a latency nobody measured, and a look when none runs', () => {
    const light: Light = { ...named('rope'), latency: { estimated: true, measuredMs: 47 } }
    expect(tooltipText(light, [], ZONE_NAMES)).toEqual({ name: light.name, running: null })
    expect(deviceLine(light, null)).toBe(`${light.model} · ~47 ms`)
    expect(deviceLine({ ...light, latency: { estimated: true, measuredMs: 47, overrideMs: 30 } }, null)).toBe(`${light.model} · 30 ms`)
    expect(deviceLine({ ...light, latency: { estimated: false, measuredMs: null } }, null)).toBe(light.model)
  })

  // Mi1, and its ruling: the latency the engine times the light's frames by. The stats channel's
  // latency_ms is the light's effective latency, its manual offset included (contract.py's
  // light_stats); REST's measured_ms leaves the offset out (light_out), so it stands in only until
  // the first stats message. An override still comes first, and REST's estimated flag gives the "~".
  it("shows the latency the engine times the light's frames by: the stats channel's, and REST's until stats come", () => {
    const light: Light = { ...named('rope'), latency: { estimated: false, measuredMs: 47 } }
    expect(deviceLine(light, null)).toBe(`${light.model} · 47 ms`)
    // Measured at 47 ms, with a manual offset of 15.
    expect(deviceLine(light, 62)).toBe(`${light.model} · 62 ms`)
    expect(deviceLine({ ...light, latency: { estimated: true, measuredMs: 47 } }, 62)).toBe(`${light.model} · ~62 ms`)
    expect(deviceLine({ ...light, latency: { estimated: false, measuredMs: 47, overrideMs: 30 } }, 62)).toBe(`${light.model} · 30 ms`)
  })

  it("reads a streamed light's colour as its LEDs' average, and an idle one's as the colour it rests on", () => {
    const frames = new FrameStore()
    frames.live.set('x', { rgb: Uint8Array.from([255, 0, 0, 0, 0, 255]), seq: 1, count: 2, at: 0, recent: 0 })
    const streaming = lightState({ ...named('tube'), status: 'streaming' }, undefined)
    expect(currentColour(frames.get('x'), streaming)).toEqual([127.5, 0, 127.5])
    const idle = lightState({ ...named('tube'), status: 'idle', power: true, colour: '#102030' }, undefined)
    expect(currentColour(undefined, idle)).toEqual([16, 32, 48])
    expect(currentColour(undefined, { ...idle, power: false })).toBeNull()
  })

  it('says hex and intensity, Offline since, Switched off elsewhere, Off, or nothing it does not know', () => {
    const state = lightState({ ...named('tube'), status: 'streaming' }, undefined)
    expect(colourLine(state, [128, 64, 0])).toBe('#804000 · 50%')
    expect(colourLine({ ...state, status: 'offline' }, null)).toBe(`Offline since ${formatTime(new Date(state.since))}`)
    expect(colourLine({ ...state, status: 'switched-off' }, null)).toBe('Switched off elsewhere')
    expect(colourLine({ ...state, status: 'idle', power: false }, null)).toBe('Off')
    expect(colourLine({ ...state, status: 'idle', power: null }, null)).toBeNull()
  })
})
