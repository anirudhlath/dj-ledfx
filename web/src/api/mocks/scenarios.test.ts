import { describe, expect, it } from 'vitest'
import { HERO_CHROME } from '@/chrome/state'
import { formatTime } from '@/lib/format'
import type { AttentionItem } from '../contract'
import { HOME_ZONE, lookName, roomName } from './fixtures'
import { SCENARIOS, buildScenario, isScenario, orderAttention } from './scenarios'

const NOW = new Date(2026, 8, 23, 19, 14)
const hhmm = (iso: string) => formatTime(new Date(iso))
const light = (name: (typeof SCENARIOS)[number], id: string) =>
  buildScenario(name, NOW).lights.find((candidate) => candidate.id === id)

describe('every scenario', () => {
  it.each(SCENARIOS)('%s runs known looks on known lights, each light in one zone at most', (name) => {
    const state = buildScenario(name, NOW)
    const ids = new Set(state.lights.map((candidate) => candidate.id))
    const owned = state.running.flatMap((zone) => zone.lights)
    expect(new Set(owned).size).toBe(owned.length)
    for (const id of owned) expect(ids.has(id)).toBe(true)
    for (const zone of state.running) {
      expect(zone.lookName).toBe(lookName(zone.lookId))
      expect(state.zones.map((candidate) => candidate.id)).toContain(zone.zoneId)
    }
    expect(state.attention).toEqual(orderAttention(state.attention))
    // "Start again" offers known looks on known zones, newest stop first (engine M2's order).
    for (const entry of state.recent) {
      expect(entry.lookName).toBe(lookName(entry.lookId))
      expect(entry.zoneName).toBe(state.zones.find((candidate) => candidate.id === entry.zoneId)?.name)
      expect(Date.parse(entry.startedAt)).toBeLessThanOrEqual(Date.parse(entry.stoppedAt))
    }
    const stops = state.recent.map((entry) => Date.parse(entry.stoppedAt))
    expect(stops).toEqual([...stops].sort((a, b) => b - a))
  })

  it('is built afresh each time', () => {
    const first = buildScenario('hero', NOW)
    first.running.pop()
    first.lights[0].name = 'changed'
    const second = buildScenario('hero', NOW)
    expect(second.running).toHaveLength(3)
    expect(second.lights[0].name).not.toBe('changed')
  })

  it('knows its names', () => {
    expect(isScenario('hero')).toBe(true)
    expect(isScenario('preview-only')).toBe(true)
    expect(isScenario('nope')).toBe(false)
  })
})

describe('orderAttention', () => {
  it('puts high severity first, then the newest', () => {
    const item = (id: string, severity: AttentionItem['severity'], since: string): AttentionItem => ({
      id,
      severity,
      since,
      kind: 'zone-slow',
      subject: { type: 'zone', id },
      title: id,
      detail: '',
      actions: [],
    })
    const items = [
      item('a', 'normal', '2026-09-23T17:02:00Z'),
      item('b', 'high', '2026-09-23T17:00:00Z'),
      item('c', 'normal', '2026-09-23T19:12:00Z'),
      item('d', 'high', '2026-09-23T19:00:00Z'),
    ]
    expect(orderAttention(items).map((each) => each.id)).toEqual(['d', 'b', 'c', 'a'])
  })
})

describe('the hero', () => {
  const hero = buildScenario('hero', NOW)

  it('runs the three zones of the 19:14 render', () => {
    expect(hero.running.map((zone) => [zone.zoneId, zone.lookId, zone.brightness])).toEqual([
      [HOME_ZONE, 'homesunset', 0.85],
      ['living', 'fireflies', 0.7],
      ['office', 'comets', 1],
    ])
    expect(hero.running.map((zone) => hhmm(zone.since))).toEqual(['18:04', '19:05', '19:10'])
    expect(hero.running[0].covers).toEqual([roomName('kitchen'), roomName('bedroom'), roomName('corridor')])
  })

  it('has Rope offline since 17:02 and Candle 2 switched off, and one item needing attention', () => {
    const rope = hero.lights.find((candidate) => candidate.id === 'rope')
    expect(rope?.status).toBe('offline')
    expect(hhmm(rope?.statusSince ?? '')).toBe('17:02')
    expect(light('hero', 'candle2')).toMatchObject({ status: 'switched-off', power: false })
    expect(hero.lights.filter((candidate) => candidate.status === 'streaming')).toHaveLength(17)
    expect(hero.attention).toHaveLength(HERO_CHROME.attention.total)
    expect(hero.attention[0]).toMatchObject({
      id: 'light-offline:rope',
      kind: 'light-offline',
      severity: 'normal',
      subject: { type: 'light', id: 'rope' },
    })
    expect(hero.attention[0].detail).toContain('since 17:02')
  })

  it("agrees with the chrome's fixture on the tempo and the sunset", () => {
    expect(hero.beat).toMatchObject({
      source: HERO_CHROME.tempo.source,
      bpm: HERO_CHROME.tempo.bpm,
      bar: HERO_CHROME.tempo.bar,
      beatInBar: HERO_CHROME.tempo.beat,
      stale: false,
    })
    expect(hhmm(hero.inputs.sun.sunset)).toBe(HERO_CHROME.sunset)
    expect(hero.previewOnly).toBe(false)
    expect(hero.link.dropAfterMs).toBeNull()
  })
})

describe('the other scenarios', () => {
  it('doorbell plays the ripple over everything, with 2.4 s left', () => {
    const { overlays } = buildScenario('doorbell', NOW)
    expect(overlays).toHaveLength(1)
    expect(overlays[0]).toMatchObject({ lookId: 'doorbell', name: lookName('doorbell'), progress: 0.4 })
    expect(Date.parse(overlays[0].endsAt) - NOW.getTime()).toBe(2400)
  })

  it('transition dissolves the living room from one look into another', () => {
    const living = buildScenario('transition', NOW).running.find((zone) => zone.zoneId === 'living')
    expect(living).toMatchObject({
      lookId: 'embers',
      state: 'transition',
      transition: { from: lookName('fireflies'), kind: 'dissolve', progress: 0.62 },
    })
  })

  it('problems lists five items, the crash first', () => {
    const state = buildScenario('problems', NOW)
    expect(state.attention.map((item) => item.kind)).toEqual([
      'zone-crashed',
      'input-stale',
      'zone-slow',
      'input-disconnected',
      'light-offline',
    ])
    expect(state.running.find((zone) => zone.zoneId === 'kitchen')).toMatchObject({ state: 'crashed', lookId: 'lava' })
    expect(state.running.find((zone) => zone.zoneId === 'living')).toMatchObject({
      state: 'slow',
      fps: { actual: 38, target: 60 },
    })
    const waiting = state.looks.filter((look) => look.needs?.includes('home-assistant')).map((look) => look.name)
    const disconnected = state.attention.find((item) => item.kind === 'input-disconnected')
    for (const name of waiting) expect(disconnected?.detail).toContain(name)
    expect(state.beat).toMatchObject({ source: 'internal', bpm: 118 })
  })

  it("firmware runs each light's own effect, and a streamed copy where there is none", () => {
    const state = buildScenario('firmware', NOW)
    expect(state.running).toHaveLength(1)
    expect(state.running[0]).toMatchObject({ zoneId: HOME_ZONE, lookId: 'firmware', brightness: 0.9 })
    expect(state.running[0].lights).toHaveLength(state.lights.length)
    for (const each of state.lights) {
      if (each.builtInEffects.length === 0) expect(each.status).toBe('streamed-copy')
      else expect(each).toMatchObject({ status: 'own-effect', ownEffect: each.builtInEffects[0] })
    }
    expect(state.lights.filter((each) => each.ownEffect === 'LIFX waveform')).toHaveLength(11)
    expect(state.lights.filter((each) => each.status === 'streamed-copy')).toHaveLength(1)
    expect(state.attention).toEqual([])
  })

  it('inputs-down has the music stale, Home Assistant disconnected and the tempo on Internal', () => {
    const state = buildScenario('inputs-down', NOW)
    expect(state.inputs.music.state).toBe('stale')
    expect(NOW.getTime() - Date.parse(state.inputs.music.updatedAt)).toBe(42_000)
    expect(state.inputs.homeAssistant).toMatchObject({ state: 'disconnected', retryS: 10 })
    expect(hhmm(state.inputs.homeAssistant.since)).toBe('19:02')
    expect(state.inputs.tempo).toMatchObject({ source: 'internal', bpm: 118 })
    expect(state.attention.map((item) => item.kind)).toEqual(['input-stale', 'input-disconnected', 'light-offline'])
  })

  it('nothing-running leaves 9 lights on and 10 off, and nothing needs attention', () => {
    const state = buildScenario('nothing-running', NOW)
    expect(state.running).toEqual([])
    expect(state.lights.filter((each) => each.power === true)).toHaveLength(9)
    expect(state.lights.filter((each) => each.power !== true)).toHaveLength(10)
    expect(light('nothing-running', 'rope')?.status).toBe('offline')
    expect(state.attention).toEqual([])
  })

  it("nothing-running offers last night's three looks to start again, newest stop first", () => {
    const { recent } = buildScenario('nothing-running', NOW)
    expect(recent.map((entry) => [entry.zoneId, entry.lookId])).toEqual([
      [HOME_ZONE, 'goodnight'],
      ['living', 'fireflies'],
      [HOME_ZONE, 'homesunset'],
    ])
    expect(recent.map((entry) => [hhmm(entry.startedAt), hhmm(entry.stoppedAt)])).toEqual([
      ['23:31', '07:00'],
      ['21:10', '23:31'],
      ['18:02', '23:31'],
    ])
    expect(buildScenario('hero', NOW).recent).toEqual([])
  })

  it('no-lights has no shapes and no anchors', () => {
    const state = buildScenario('no-lights', NOW)
    expect(state.lights.every((each) => each.shape === null)).toBe(true)
    expect(state.home.anchors).toEqual([])
  })

  it('reconnecting drops the link a second after it connects', () => {
    expect(buildScenario('reconnecting', NOW).link.dropAfterMs).toBe(1000)
  })

  it('dj-playing has four decks, Player 2 the master, and the beat from Pro DJ Link', () => {
    const state = buildScenario('dj-playing', NOW)
    expect(state.decks.map((deck) => [deck.player, deck.state, deck.master])).toEqual([
      ['Player 1', 'cued', false],
      ['Player 2', 'playing', true],
      ['Player 3', 'empty', false],
      ['Player 4', 'empty', false],
    ])
    expect(state.beat).toMatchObject({ source: 'prodjlink', bar: 17, beatInBar: 3, pitchPercent: 1.2 })
    expect(state.beat.bpm).toBeCloseTo(125.488)
    expect(state.inputs.music).toMatchObject({ state: 'idle', track: null })
  })

  it('preview-only is the hero with preview only on', () => {
    const state = buildScenario('preview-only', NOW)
    expect(state.previewOnly).toBe(true)
    expect(state.running).toEqual(buildScenario('hero', NOW).running)
  })
})
