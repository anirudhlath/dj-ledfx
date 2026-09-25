// The §12.5 scenarios, each a whole server state: the hero at 19:14 and the states around it, from
// the reference renders' sample content. Times count from `now`, so a clock fixed at 19:14 shows the
// renders' times (decision 8). Names come from the fixtures; ids pick things out of them.
import { formatBpm, formatTime } from '@/lib/format'
import type {
  AttentionItem, Deck, Home, Id, Inputs, Light, Look, Overlay, RecentLook, RunningZone, Signal, TempoSource, Zone,
} from '../contract'
import {
  HOME_ZONE, coversOf, homeFixture, lightFixtures, lookFixtures, lookName, roomName, zoneFixtures,
} from './fixtures'

export const SCENARIOS = [
  'hero',
  'doorbell',
  'transition',
  'problems',
  'firmware',
  'inputs-down',
  'nothing-running',
  'no-lights',
  'reconnecting',
  'dj-playing',
  'preview-only',
] as const
export type ScenarioName = (typeof SCENARIOS)[number]

export function isScenario(name: string): name is ScenarioName {
  return (SCENARIOS as readonly string[]).includes(name)
}

/** Where a scenario's beat starts. It moves unless stale or at 0 BPM. */
export interface ScenarioBeat {
  source: TempoSource
  /** Pitch-adjusted. */
  bpm: number
  bar: number
  /** 1–4. */
  beatInBar: number
  pitchPercent: number
  stale: boolean
}

export interface ScenarioLink {
  /** The mock drops every session this long after the first one connects, and refuses new ones. */
  dropAfterMs: number | null
}

export interface ScenarioState {
  name: ScenarioName
  home: Home
  lights: Light[]
  looks: Look[]
  zones: Zone[]
  running: RunningZone[]
  overlays: Overlay[]
  attention: AttentionItem[]
  beat: ScenarioBeat
  decks: Deck[]
  inputs: Inputs
  signals: Signal[]
  previewOnly: boolean
  link: ScenarioLink
  /** "Start again" (§9.4): the looks that stopped, newest stop first, as engine M2 keeps them (decision 8). */
  recent: RecentLook[]
}

const SEVERITY: Record<AttentionItem['severity'], number> = { high: 0, normal: 1 }

/** §9.5: "Ordered by severity then time", the newest first, as M1's feed sorts (decision 7). */
export function orderAttention(items: AttentionItem[]): AttentionItem[] {
  return [...items].sort(
    (a, b) => SEVERITY[a.severity] - SEVERITY[b.severity] || Date.parse(b.since) - Date.parse(a.since),
  )
}

const SECOND = 1000
const MINUTE = 60 * SECOND
/** The doorbell's entity, as the Inputs render names it. */
const DOORBELL = 'binary_sensor.front_door_ding'

/** The ISO time `ms` from now, as the API sends times. */
const after = (now: Date, ms: number) => new Date(now.getTime() + ms).toISOString()
const hhmm = (iso: string) => formatTime(new Date(iso))
const joinNames = (names: string[]) =>
  names.length < 2 ? names.join('') : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`

function lightOf(state: ScenarioState, id: Id): Light {
  const light = state.lights.find((candidate) => candidate.id === id)
  if (light === undefined) throw new Error(`No light ${id} in the fixtures`)
  return light
}

function setLight(state: ScenarioState, id: Id, patch: Partial<Light>): void {
  Object.assign(lightOf(state, id), patch)
}

function zoneOf(state: ScenarioState, id: Id): Zone {
  const zone = state.zones.find((candidate) => candidate.id === id)
  if (zone === undefined) throw new Error(`No zone ${id} in the fixtures`)
  return zone
}

function runningOf(state: ScenarioState, zoneId: Id): RunningZone {
  const zone = state.running.find((candidate) => candidate.zoneId === zoneId)
  if (zone === undefined) throw new Error(`Zone ${zoneId} is not running`)
  return zone
}

/** A look that stopped on a zone, as "Start again" lists it. */
function stoppedLook(state: ScenarioState, zoneId: Id, lookId: Id, startedAt: string, stoppedAt: string): RecentLook {
  return { zoneId, zoneName: zoneOf(state, zoneId).name, lookId, lookName: lookName(lookId), startedAt, stoppedAt }
}

/** Starts a look on a zone. Its lights stream from `since`. */
function run(
  state: ScenarioState,
  zoneId: Id,
  lookId: Id,
  since: string,
  brightness: number,
  lights: Id[] = zoneOf(state, zoneId).lights,
  extra: Partial<RunningZone> = {},
): RunningZone {
  const zone: RunningZone = {
    zoneId,
    lookId,
    lookName: lookName(lookId),
    since,
    brightness,
    lights,
    covers: coversOf(state.home, state.lights, lights),
    state: 'running',
    fps: { actual: 60, target: 60 },
    ...extra,
  }
  for (const id of lights) setLight(state, id, { status: 'streaming', statusSince: since, power: true, sendFps: 60 })
  state.running.push(zone)
  return zone
}

// ── Attention, in M1's words where M1 raises the kind (decision 8) ─────────────────────────

function lightOffline(state: ScenarioState, id: Id): AttentionItem {
  const light = lightOf(state, id)
  return {
    id: `light-offline:${id}`,
    severity: 'normal',
    kind: 'light-offline',
    subject: { type: 'light', id },
    title: `${light.name} offline`,
    detail: `${light.name} offline since ${hhmm(light.statusSince)}. It rejoins by itself when it's back.`,
    since: light.statusSince,
    actions: ['details'],
  }
}

function zoneCrashed(state: ScenarioState, zone: RunningZone): AttentionItem {
  const name = zoneOf(state, zone.zoneId).name
  const lights = name.toLowerCase().endsWith('lights') ? `${name} are` : `The ${name} lights are`
  const error = zone.error
  if (!error) throw new Error(`Zone ${zone.zoneId} has no error`)
  return {
    id: `zone-crashed:${zone.zoneId}`,
    severity: 'high',
    kind: 'zone-crashed',
    subject: { type: 'zone', id: zone.zoneId },
    title: `${zone.lookName} crashed`,
    detail: `${lights} holding the last frame. ${error.layer}: ${error.message}`,
    since: error.at,
    actions: ['restart', 'details'],
  }
}

function zoneSlow(state: ScenarioState, zone: RunningZone, since: string): AttentionItem {
  return {
    id: `zone-slow:${zone.zoneId}`,
    severity: 'normal',
    kind: 'zone-slow',
    subject: { type: 'zone', id: zone.zoneId },
    title: `${zoneOf(state, zone.zoneId).name} is running slow`,
    detail: `${zone.lookName} can't keep up with ${zone.fps?.target ?? 60} fps, so it runs at a lower frame rate.`,
    since,
    actions: ['details'],
  }
}

// M1 can't raise these two yet: they use the State-Problems render's words.
function homeAssistantDisconnected(state: ScenarioState): AttentionItem {
  const ha = state.inputs.homeAssistant
  const waiting = state.looks.filter((look) => look.needs?.includes('home-assistant')).map((look) => look.name)
  return {
    id: 'input-disconnected:home-assistant',
    severity: 'normal',
    kind: 'input-disconnected',
    subject: { type: 'input', id: 'home-assistant' },
    title: 'Home Assistant is disconnected',
    detail: `Since ${hhmm(ha.since)}, retrying every ${ha.retryS ?? 10} s. ${joinNames(waiting)} can't trigger.`,
    since: ha.since,
    actions: ['retry', 'open'],
  }
}

function musicWentQuiet(state: ScenarioState, now: Date): AttentionItem {
  const music = state.inputs.music
  const quietS = Math.round((now.getTime() - Date.parse(music.updatedAt)) / SECOND)
  return {
    id: 'input-stale:music',
    severity: 'normal',
    kind: 'input-stale',
    subject: { type: 'input', id: 'music' },
    title: 'Music Assistant went quiet',
    detail: `No update for ${quietS} s. The tempo fell back to Internal ${formatBpm(state.beat.bpm)}.`,
    since: music.updatedAt,
    actions: ['open'],
  }
}

// ── The hero, and the scenarios built on it ────────────────────────────────────────────────

const SPECTRUM = Array.from({ length: 32 }, (_, band) => Math.round(83 * Math.exp(-band / 10)) / 100)

function heroInputs(now: Date): Inputs {
  return {
    tempo: { source: 'music', lock: 'auto', bpm: 121.8, stale: false },
    prodjlink: {
      state: 'idle',
      interface: 'eth0',
      lastSet: { from: after(now, -4114 * MINUTE), to: after(now, -3959 * MINUTE) },
    },
    music: {
      state: 'connected',
      track: { title: 'Rain', artist: 'Kerri Chandler' },
      group: [roomName('living'), roomName('kitchen')],
      loudness: 0.58,
      lufs: -14,
      spectrum: [...SPECTRUM],
      onsets: { kick: 0.91, snare: 0.12, hihat: 0.44 },
      updatedAt: after(now, -40),
    },
    homeAssistant: {
      state: 'connected',
      url: 'homeassistant.local:8123',
      since: after(now, -1440 * MINUTE),
      retryS: null,
      entities: [
        { id: DOORBELL, state: 'off', since: after(now, -152 * MINUTE) },
        { id: 'input_boolean.bedtime', state: 'off', since: after(now, -1180 * MINUTE) },
        { id: 'media_player.living_room', state: 'playing', since: after(now, -12 * MINUTE) },
        { id: 'sun.sun', state: 'above_horizon', since: after(now, -724 * MINUTE) },
      ],
    },
    sun: { elevation: 2.1, azimuth: 268, sunrise: after(now, -724 * MINUTE), sunset: after(now, 12 * MINUTE) },
  }
}

/** The Inputs render's signals table. `usedBy` holds look ids. */
function heroSignals(): Signal[] {
  return [
    { name: 'beat.phase', value: 0.62, usedBy: ['comets'] },
    { name: 'bar.phase', value: 0.41, usedBy: ['comets'] },
    { name: 'bpm', value: 121.8, usedBy: ['comets'] },
    { name: 'loudness', value: 0.58, usedBy: [] },
    { name: 'spectrum.bass', value: 0.83, usedBy: [] },
    { name: 'onset.kick', value: 0.91, usedBy: [] },
    { name: 'doorbell', value: 'idle', usedBy: ['doorbell'] },
    { name: 'bedtime', value: 'off', usedBy: ['goodnight'] },
    { name: 'sun.elevation', value: 2.1, unit: '°', usedBy: ['homesunset'] },
    { name: 'sun.azimuth', value: 268, unit: '°', usedBy: ['homesunset'] },
    { name: 'time.evening', value: 0.31, usedBy: [] },
  ]
}

function base(name: ScenarioName, now: Date): ScenarioState {
  const home = structuredClone(homeFixture)
  const lights = lightFixtures(after(now, -70 * MINUTE))
  return {
    name,
    home,
    lights,
    looks: structuredClone(lookFixtures),
    zones: zoneFixtures(home, lights),
    running: [],
    overlays: [],
    attention: [],
    beat: { source: 'music', bpm: 121.8, bar: 42, beatInBar: 2, pitchPercent: 0, stale: false },
    decks: [],
    inputs: heroInputs(now),
    signals: heroSignals(),
    previewOnly: false,
    link: { dropAfterMs: null },
    recent: [],
  }
}

/** Rope offline since 17:02 and Candle 2 switched off elsewhere at 18:43 (§9.1). */
function heroLights(state: ScenarioState, now: Date): void {
  setLight(state, 'rope', { status: 'offline', statusSince: after(now, -132 * MINUTE), power: null, sendFps: 0 })
  setLight(state, 'candle2', {
    status: 'switched-off',
    statusSince: after(now, -31 * MINUTE),
    power: false,
    sendFps: 0,
  })
}

/** Main.png: the whole home since 18:04, the living room since 19:05 and the office desk since 19:10. */
function hero(state: ScenarioState, now: Date): void {
  const living = zoneOf(state, 'living').lights
  const office = zoneOf(state, 'office').lights
  const taken = new Set([...living, ...office])
  const rest = state.lights.map((light) => light.id).filter((id) => !taken.has(id))
  run(state, HOME_ZONE, 'homesunset', after(now, -70 * MINUTE), 0.85, rest)
  run(state, 'living', 'fireflies', after(now, -9 * MINUTE), 0.7)
  run(state, 'office', 'comets', after(now, -4 * MINUTE), 1)
  heroLights(state, now)
  state.attention = orderAttention([lightOffline(state, 'rope')])
}

/** State-Inputs-Down: the music went quiet 42 s ago, so the tempo fell back to Internal. */
function inputsDown(state: ScenarioState, now: Date): void {
  state.beat = { ...state.beat, source: 'internal', bpm: 118 }
  state.inputs.tempo = { source: 'internal', lock: 'auto', bpm: 118, stale: false }
  state.inputs.music = { ...state.inputs.music, state: 'stale', updatedAt: after(now, -42 * SECOND) }
  state.inputs.homeAssistant = {
    ...state.inputs.homeAssistant,
    state: 'disconnected',
    since: after(now, -12 * MINUTE),
    retryS: 10,
  }
}

const BUILD: Record<ScenarioName, (state: ScenarioState, now: Date) => void> = {
  hero,
  doorbell(state, now) {
    hero(state, now)
    state.overlays = [
      { lookId: 'doorbell', name: lookName('doorbell'), trigger: DOORBELL, endsAt: after(now, 2.4 * SECOND), progress: 0.4 },
    ]
  },
  transition(state, now) {
    hero(state, now)
    Object.assign(runningOf(state, 'living'), {
      lookId: 'embers',
      lookName: lookName('embers'),
      state: 'transition',
      transition: { from: lookName('fireflies'), kind: 'dissolve', progress: 0.62 },
    } satisfies Partial<RunningZone>)
  },
  problems(state, now) {
    inputsDown(state, now)
    const office = zoneOf(state, 'office').lights
    const kitchen = run(state, 'kitchen', 'lava', after(now, -20 * MINUTE), 1, undefined, {
      state: 'crashed',
      fps: null,
      error: { layer: 'Plasma', message: 'raised an error', at: after(now, -2 * MINUTE) },
    })
    const living = run(state, 'living', 'embers', after(now, -24 * MINUTE), 0.7, undefined, {
      state: 'slow',
      fps: { actual: 38, target: 60 },
    })
    const bedroom = zoneOf(state, 'bedroom').lights.filter((id) => !office.includes(id))
    run(state, 'bedroom', 'sunset', after(now, -60 * MINUTE), 0.85, bedroom)
    run(state, 'office', 'comets', after(now, -4 * MINUTE), 1)
    heroLights(state, now)
    state.attention = orderAttention([
      zoneCrashed(state, kitchen),
      zoneSlow(state, living, after(now, -2 * MINUTE)),
      homeAssistantDisconnected(state),
      musicWentQuiet(state, now),
      lightOffline(state, 'rope'),
    ])
  },
  firmware(state, now) {
    run(state, HOME_ZONE, 'firmware', after(now, -10 * MINUTE), 0.9)
    for (const light of state.lights) {
      if (light.builtInEffects.length === 0) setLight(state, light.id, { status: 'streamed-copy' })
      else setLight(state, light.id, { status: 'own-effect', ownEffect: light.builtInEffects[0] })
    }
  },
  'inputs-down'(state, now) {
    hero(state, now)
    inputsDown(state, now)
    state.attention = orderAttention([
      homeAssistantDisconnected(state),
      musicWentQuiet(state, now),
      lightOffline(state, 'rope'),
    ])
  },
  'nothing-running'(state, now) {
    // "Your lights are as they were: 9 on, 10 off." M1 raises no item for a light in no running zone.
    const on = zoneOf(state, 'living').lights.filter((id) => id !== 'rope' && id !== 'tube')
    for (const id of on) setLight(state, id, { power: true })
    setLight(state, 'rope', { status: 'offline', statusSince: after(now, -132 * MINUTE), power: null })
    // "Start again": the render's three looks from last night. Goodnight replaced Home sunset on the
    // whole home at 23:31 and took the living room's lights from Fireflies. The render gives Goodnight
    // no end, so the mock stops it at 07:00. Newest stop first, as engine M2 serves the list, which is
    // the reverse of the render's order.
    const lastNight = after(now, -1183 * MINUTE)
    state.recent = [
      stoppedLook(state, HOME_ZONE, 'goodnight', lastNight, after(now, -734 * MINUTE)),
      stoppedLook(state, 'living', 'fireflies', after(now, -1324 * MINUTE), lastNight),
      stoppedLook(state, HOME_ZONE, 'homesunset', after(now, -1512 * MINUTE), lastNight),
    ]
  },
  'no-lights'(state, now) {
    hero(state, now)
    state.home.anchors = []
    for (const light of state.lights) light.shape = null
  },
  reconnecting(state, now) {
    hero(state, now)
    state.link = { dropAfterMs: 1000 }
  },
  'dj-playing'(state, now) {
    hero(state, now)
    const pitch = 1.2
    state.beat = { source: 'prodjlink', bpm: 124 * (1 + pitch / 100), bar: 17, beatInBar: 3, pitchPercent: pitch, stale: false }
    state.decks = [
      { number: 1, player: 'Player 1', state: 'cued', bpm: 126, pitch_percent: 0, master: false },
      { number: 2, player: 'Player 2', state: 'playing', bpm: 124, pitch_percent: pitch, master: true },
      { number: 3, player: 'Player 3', state: 'empty', bpm: null, pitch_percent: 0, master: false },
      { number: 4, player: 'Player 4', state: 'empty', bpm: null, pitch_percent: 0, master: false },
    ]
    state.inputs.tempo = { source: 'prodjlink', lock: 'auto', bpm: state.beat.bpm, stale: false }
    state.inputs.prodjlink = { ...state.inputs.prodjlink, state: 'connected' }
    // "Music Assistant: nothing playing."
    state.inputs.music = {
      ...state.inputs.music,
      state: 'idle',
      track: null,
      loudness: 0,
      spectrum: SPECTRUM.map(() => 0),
      onsets: { kick: 0, snare: 0, hihat: 0 },
    }
  },
  'preview-only'(state, now) {
    hero(state, now)
    state.previewOnly = true
  },
}

/** A new state for the scenario, with its times counted from `now`. */
export function buildScenario(name: ScenarioName, now: Date = new Date()): ScenarioState {
  const state = base(name, now)
  BUILD[name](state, now)
  return state
}
