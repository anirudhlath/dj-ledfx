// The zone view model (§6.3): what a ZoneCard, a ZoneRow and the phone's Zone detail say about a running
// zone. It's worked out from REST (the zones, the looks, the lights) and the live store (what runs, each
// light's state, whose beat the clock follows, the attention feed). Pure: use-zone-world.ts gathers the
// data, and tests build the same world from a scenario. The words are the renders' (Main, State-Problems,
// State-Sheet) and F3 decisions 10–17's.
import type {
  AttentionItem,
  Id,
  InputKind,
  Light,
  LightUpdate,
  Look,
  Overlay,
  RunningZone,
  TempoSource,
  Zone,
  ZoneTransition,
} from '@/api/contract'
import type { IconName } from '@/design/icons'
import { formatDuration, formatList, formatTime } from '@/lib/format'
import { effectWord } from '@/lights/firmware'
import { lightStates, type LightState } from '@/stage/show'

export interface ZoneWorld {
  zones: ReadonlyMap<Id, Zone>
  looks: ReadonlyMap<Id, Look>
  lights: ReadonlyMap<Id, Light>
  /** Each light's state: the latest push's, else REST's. */
  states: ReadonlyMap<Id, LightState>
  /** How many lights the home has, for "all N lights". */
  lightCount: number
  /** Whose beat the clock follows; null before the first beat. */
  beatSource: TempoSource | null
  /** The zones running slow, for "The other zones are fine." */
  slow: ReadonlySet<Id>
  /** When each slow zone's `zone-slow` item says it began. */
  slowSince: ReadonlyMap<Id, string>
}

export interface WorldSources {
  zones: readonly Zone[] | undefined
  looks: readonly Look[] | undefined
  lights: readonly Light[] | undefined
  updates: Readonly<Record<Id, LightUpdate>> | null
  beatSource: TempoSource | null
  running: readonly RunningZone[]
  attention: readonly AttentionItem[] | null
}

export interface InputChip {
  kind: InputKind
  label: string
  icon: IconName
  /** The zone waits for it: the chip turns signal (§6.3). */
  waiting: boolean
}

export interface NotePart {
  text: string
  /** In signal, semibold: "Rope offline" (Main.png). */
  strong?: boolean
  /** A number, in mono: the slow note's actual fps (State-Problems). */
  mono?: boolean
}

export interface ZoneNote {
  /** signal: the whole note in the signal colour (crashed, slow); quiet: text-3, its strong parts in signal. */
  tone: 'signal' | 'quiet'
  parts: NotePart[]
}

export interface TransitionView {
  /** The look it leaves, struck through on the card. */
  from: string
  /** "Dissolve · 3 s", or "Dissolve" with no duration (F3 decision 16). */
  label: string
  /** The served progress, 0–1. */
  progress: number
  /** The served duration, which moves the bar on between pushes (F3 decision 16); null when unsaid. */
  durationS: number | null
}

export interface SwatchLight {
  light: Light
  state: LightState
}

export interface ZoneView {
  zoneId: Id
  /** The zone's name; its id until REST has it (Review Focus 4). */
  name: string
  /** The push's, so it's there before REST's list. */
  lookName: string
  /** §6.3's context line (F3 decision 10). */
  context: string
  /** The look's input chips, in INPUTS' order; null when REST doesn't know the look, so no chip is wrong. */
  inputs: InputChip[] | null
  /** "Evening" (F3 decision 11). */
  modifiers: string[]
  /** F3 decision 12. */
  since: string
  /** The state's note, then the lights' (F3 decision 13). */
  notes: ZoneNote[]
  transition: TransitionView | null
  /** A swatch for each of the zone's lights that REST knows, in the zone's order. */
  lights: SwatchLight[]
}

/** The inputs a look can need or use, in §6.3's chip order (F3 decision 11). */
export const INPUTS: Record<InputKind, { label: string; icon: IconName }> = {
  sun: { label: 'Sun', icon: 'sun' },
  tempo: { label: 'Tempo', icon: 'tempo' },
  music: { label: 'Music', icon: 'music' },
  'home-assistant': { label: 'Home Assistant', icon: 'ha' },
}
const INPUT_ORDER = Object.keys(INPUTS) as InputKind[]

/** Whose beat a tempo look follows (F3 decision 10; "on the music's beat", Main.png). */
const BEAT: Record<TempoSource, string> = {
  music: "on the music's beat",
  prodjlink: "on the DJ's beat",
  internal: 'on the beat',
}

/** A transition's kind: the card's bar says its label, the stage's tag what it's doing (State-Transition). */
export const TRANSITION: Record<ZoneTransition['kind'], { label: string; doing: string }> = {
  cut: { label: 'Cut', doing: 'cutting' },
  fade: { label: 'Fade', doing: 'fading' },
  wipe: { label: 'Wipe', doing: 'wiping' },
  spread: { label: 'Spread', doing: 'spreading' },
  dissolve: { label: 'Dissolve', doing: 'dissolving' },
}

/** §6.3: "Nothing playing on Music Assistant. The look waits dark and starts with the music." */
const WAITING_FOR_MUSIC = 'Nothing playing on Music Assistant. The look waits dark and starts with the music.'

const clamp01 = (value: number) => Math.min(Math.max(value, 0), 1)
const lightCount = (count: number) => (count === 1 ? '1 light' : `${count} lights`)
const timeOf = (at: string) => formatTime(new Date(at))

function byId<T extends { id: Id }>(items: readonly T[] | undefined): Map<Id, T> {
  return new Map((items ?? []).map((item) => [item.id, item]))
}

/** The world every card on the page reads. */
export function zoneWorld({ zones, looks, lights, updates, beatSource, running, attention }: WorldSources): ZoneWorld {
  const slowSince = new Map<Id, string>()
  for (const item of attention ?? []) {
    if (item.kind === 'zone-slow' && item.subject.type === 'zone') slowSince.set(item.subject.id, item.since)
  }
  return {
    zones: byId(zones),
    looks: new Map((looks ?? []).flatMap((look) => (look.id == null ? [] : [[look.id, look] as const]))),
    lights: byId(lights),
    states: lightStates(lights ?? [], updates),
    lightCount: lights?.length ?? 0,
    beatSource,
    slow: new Set(running.filter((zone) => zone.state === 'slow').map((zone) => zone.zoneId)),
    slowSince,
  }
}

function contextLine(zone: Zone | undefined, look: Look | undefined, running: RunningZone, world: ZoneWorld): string {
  const inputs = [...(look?.needs ?? []), ...(look?.uses ?? [])]
  if (inputs.includes('tempo') && world.beatSource !== null) return BEAT[world.beatSource]
  if (zone?.kind === 'home') {
    if (world.lightCount > 0 && running.lights.length === world.lightCount) return `all ${world.lightCount} lights`
    if (running.covers != null && running.covers.length > 0) return running.covers.join(' · ')
  }
  return lightCount(running.lights.length)
}

/** A look's input chips in INPUTS' order; an input it waits for is marked, and shown even if the look doesn't list it. */
export function chipsFor(look: Look, waitingFor: readonly InputKind[] = []): InputChip[] {
  const waiting = new Set(waitingFor)
  const used = new Set([...(look.needs ?? []), ...(look.uses ?? []), ...waiting])
  return INPUT_ORDER.filter((kind) => used.has(kind)).map((kind) => ({ kind, ...INPUTS[kind], waiting: waiting.has(kind) }))
}

function sinceLine(running: RunningZone, now: Date, compact: boolean): string {
  if (running.state === 'crashed' && running.error != null) return `stopped at ${timeOf(running.error.at)}`
  const since = `since ${timeOf(running.since)}`
  if (running.state === 'slow' || compact) return since
  return `${since} · ${formatDuration(now.getTime() - Date.parse(running.since))}`
}

/** "The Kitchen lights are", or "Kitchen lights are" for a name that already says so (as engine M1 words it). */
const holding = (name: string) => (name.toLowerCase().endsWith('lights') ? `${name} are` : `The ${name} lights are`)

function stateNote(running: RunningZone, world: ZoneWorld, name: string, now: Date): ZoneNote | null {
  switch (running.state) {
    case 'crashed': {
      const { error } = running
      const at = error == null ? '' : ` at ${timeOf(error.at)}`
      const what = error?.layer ? `Layer “${error.layer}” raised an error${at}.` : `The look raised an error${at}.`
      return { tone: 'signal', parts: [{ text: `${what} ${holding(name)} holding the last frame.` }] }
    }
    case 'slow': {
      if (running.fps == null) return null
      const since = world.slowSince.get(running.zoneId)
      const lasting = since === undefined ? '' : ` for ${formatDuration(now.getTime() - Date.parse(since), 'min')}`
      const others = [...world.slow].some((id) => id !== running.zoneId) ? '' : ' The other zones are fine.'
      return {
        tone: 'signal',
        parts: [{ text: String(Math.round(running.fps.actual)), mono: true }, { text: ` of ${running.fps.target} fps${lasting}.${others}` }],
      }
    }
    case 'waiting': {
      const waitingFor = running.waitingFor ?? []
      const first = INPUT_ORDER.find((kind) => waitingFor.includes(kind))
      if (first === undefined) return null
      const text =
        first === 'music' ? WAITING_FOR_MUSIC : `Waiting for ${INPUTS[first].label}. The look waits dark and starts when it's there.`
      return { tone: 'quiet', parts: [{ text }] }
    }
    default:
      return null
  }
}

/**
 * Main.png: "Rope offline since 17:02 · Candle 2 was switched off elsewhere and rejoins when it's back on";
 * `short`, Phone-Live's: "Rope offline · Candle 2 switched off elsewhere".
 */
function lightsNote(lights: readonly SwatchLight[], short = false): ZoneNote | null {
  const parts: NotePart[] = []
  const add = (...next: NotePart[]) => {
    if (parts.length > 0) parts.push({ text: ' · ' })
    parts.push(...next)
  }
  for (const { light, state } of lights) {
    if (state.status !== 'offline') continue
    add({ text: `${light.name} offline`, strong: true }, ...(short ? [] : [{ text: ` since ${timeOf(state.since)}` }]))
  }
  for (const { light, state } of lights) {
    if (state.status !== 'switched-off') continue
    add({ text: short ? `${light.name} switched off elsewhere` : `${light.name} was switched off elsewhere and rejoins when it's back on` })
  }
  return parts.length === 0 ? null : { tone: 'quiet', parts }
}

/** The phone's card's lights note (Phone-Live). */
export const shortLightsNote = (lights: readonly SwatchLight[]): ZoneNote | null => lightsNote(lights, true)

/**
 * State-Firmware: "Every light runs its own built-in effect. The Govee lamp has none, so it gets a streamed
 * copy of Flame." Said only when every light of the zone runs its own effect or a copy of one. The names are
 * the lights' own (§10), and the effect is said when the copies share one.
 */
function firmwareNote(lights: readonly SwatchLight[]): ZoneNote | null {
  const own = lights.filter(({ state }) => state.status === 'own-effect')
  const copies = lights.filter(({ state }) => state.status === 'streamed-copy')
  if (own.length === 0 || own.length + copies.length < lights.length) return null
  const every = 'Every light runs its own built-in effect.'
  if (copies.length === 0) return { tone: 'quiet', parts: [{ text: every }] }
  const effects = new Set(copies.map(({ state }) => state.ownEffect))
  const [effect] = effects
  const of = effects.size === 1 && effect !== null ? ` of ${effectWord(effect)}` : ''
  const names = formatList(copies.map(({ light }) => light.name))
  const rest = copies.length === 1 ? `${names} has none, so it gets a streamed copy${of}.` : `${names} have none, so they get streamed copies${of}.`
  return { tone: 'quiet', parts: [{ text: `${every} ${rest}` }] }
}

/** A served transition as the card and the stage's tag say it; null without one. */
export function transitionView(transition: ZoneTransition | null | undefined): TransitionView | null {
  if (transition == null) return null
  const { label } = TRANSITION[transition.kind]
  // A duration that isn't above zero (or isn't a number) says nothing.
  const durationS = transition.durationS != null && transition.durationS > 0 ? transition.durationS : null
  const said = durationS === null ? label : `${label} · ${Math.round(durationS * 10) / 10} s`
  return { from: transition.from, label: said, progress: clamp01(transition.progress), durationS }
}

/** What a card says about a running zone; `compact` is F3 decision 2's compact card. */
export function zoneView(running: RunningZone, world: ZoneWorld, now: Date, compact = false): ZoneView {
  const zone = world.zones.get(running.zoneId)
  const look = world.looks.get(running.lookId)
  const name = zone?.name ?? running.zoneId
  const lights = running.lights.flatMap((id) => {
    const light = world.lights.get(id)
    const state = world.states.get(id)
    return light === undefined || state === undefined ? [] : [{ light, state }]
  })
  return {
    zoneId: running.zoneId,
    name,
    lookName: running.lookName,
    context: contextLine(zone, look, running, world),
    inputs: look === undefined ? null : chipsFor(look, running.waitingFor ?? []),
    modifiers: look?.modifiers?.evening === true ? ['Evening'] : [],
    since: sinceLine(running, now, compact),
    notes: [stateNote(running, world, name, now), compact ? null : firmwareNote(lights), compact ? null : lightsNote(lights)].filter(
      (note) => note !== null,
    ),
    transition: running.state === 'transition' ? transitionView(running.transition) : null,
    lights,
  }
}

/** How long an overlay has left, in ms, never below zero (F3 decision 17). */
export function overlayLeftMs(overlay: Overlay, nowMs: number): number {
  return Math.max(0, Date.parse(overlay.endsAt) - nowMs)
}

/**
 * An overlay's progress, 0–1 (F3 decision 17): the server's `progress` when it had `leftAtFirstMs` to run,
 * moving on toward 1 as `leftNowMs` falls to 0.
 */
export function overlayProgress(progress: number, leftAtFirstMs: number, leftNowMs: number): number {
  if (leftAtFirstMs <= 0) return 1
  return clamp01(progress + (1 - progress) * (1 - leftNowMs / leftAtFirstMs))
}

/**
 * A transition's progress `elapsedMs` after the server said `progress` (F3 decision 16): on toward 1 at
 * `durationS`, never past it; held where the server left it when there's no duration.
 */
export function transitionProgress(progress: number, durationS: number | null, elapsedMs: number): number {
  if (durationS === null || durationS <= 0) return clamp01(progress)
  return clamp01(progress + Math.max(0, elapsedMs) / 1000 / durationS)
}
