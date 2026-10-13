// The composer's model (§8.2, §8.10 Put a look on): the zone it puts the look on, what runs on each zone
// now, the inputs a look would wait for, the looks a category or a search shows, and the transitions to
// choose from. Pure: the composer gathers its data (REST, the live store), and tests build it from a
// scenario. The words are the spec's and the renders' (Live-PutLookOn, Phone-PutLookOn).
import type { Id, InputKind, Inputs, Look, RunningZone, Transition, Zone } from '@/api/contract'
import { newestFirst } from '@/stage/show'
import { chipsFor, transitionLabel } from '@/zones/zone-view'

/** The composer's route (spec §4.3, F4 ruling 9): Live, with the composer in the Running panel's place. */
export const COMPOSER_ROUTE = '/live/put'

/** The composer's URL (spec §4.3, F4 ruling 9): its route, with ?zone= and ?look= as chosen. */
export function composerPath(zoneId: Id | null, lookId: Id | null = null): string {
  const params = new URLSearchParams()
  if (zoneId !== null) params.set('zone', zoneId)
  if (lookId !== null) params.set('look', lookId)
  const query = params.toString()
  return query === '' ? COMPOSER_ROUTE : `${COMPOSER_ROUTE}?${query}`
}

/**
 * What every push into the composer carries as its history state (F4 ruling 13, as amended): the entry was stepped into from the page
 * before it, so leaving the composer steps back out of it (Back then goes where it went before). An entry without it, a deep link or a
 * reload of one, has no step to go back to, so leaving replaces it with Live. The choices made in place keep the state they find.
 */
export const COMPOSER_ENTRY = { composer: 'entered' } as const

/** Whether a history entry's state is COMPOSER_ENTRY. */
export const composerEntered = (state: unknown): boolean =>
  typeof state === 'object' && state !== null && 'composer' in state && state.composer === COMPOSER_ENTRY.composer

/** The `to` and `state` of a link, or a push, that opens the composer (on a zone and a look, as given). */
export function composerLink(zoneId: Id | null = null, lookId: Id | null = null): { to: string; state: typeof COMPOSER_ENTRY } {
  return { to: composerPath(zoneId, lookId), state: COMPOSER_ENTRY }
}

/** §8.2's category chips: Starred, then the looks' own categories. */
export type Category = 'starred' | Look['category']

/** "Starred, Ambient, Tempo, Audio, Home, Firmware" (§8.2), in its order. */
export const CATEGORIES: readonly { id: Category; label: string }[] = [
  { id: 'starred', label: 'Starred' },
  { id: 'ambient', label: 'Ambient' },
  { id: 'tempo', label: 'Tempo' },
  { id: 'audio', label: 'Audio' },
  { id: 'home', label: 'Home' },
  { id: 'firmware', label: 'Firmware' },
]

/** §8.2: "Home looks (whole-home scope) lock the zone to Whole home." */
export const locksToHome = (look: Look | undefined): boolean => look?.scope === 'whole-home'

/**
 * The zone the composer puts the look on (F4 ruling 9): the whole home for a home look; else the zone the
 * URL names (the room clicked), else the last one used, else the whole home. A zone that's gone is unnamed.
 * Where the list has no whole home, the last resort is its first zone (an empty list has none).
 */
export function chosenZone(zones: readonly Zone[], asked: Id | null, remembered: Id | null, look: Look | undefined): Zone | undefined {
  const home = zones.find((zone) => zone.kind === 'home')
  if (locksToHome(look)) return home
  const named = (id: Id | null) => (id === null ? undefined : zones.find((zone) => zone.id === id))
  return named(asked) ?? named(remembered) ?? home ?? zones[0]
}

/**
 * What runs on a zone now (§6.3 ZonePicker: "what's running there"): its own look, else the newest look on
 * any of its lights. A room isn't said to run a sub-zone's look, as the stage's labels have it.
 */
export function runningOn(zone: Zone, running: readonly RunningZone[], zones: readonly Zone[]): RunningZone | null {
  const own = running.find((candidate) => candidate.zoneId === zone.id)
  if (own !== undefined) return own
  const subZones = new Set(zones.filter((each) => each.kind === 'sub-zone').map((each) => each.id))
  const lights = new Set(zone.lights)
  return (
    newestFirst(running).find(
      (candidate) => !(zone.kind === 'room' && subZones.has(candidate.zoneId)) && candidate.lights.some((id) => lights.has(id)),
    ) ?? null
  )
}

/** A zone's small text in the ZonePicker (F4 ruling 4; Phone-PutLookOn's "idle" and "no lights"). */
export function zoneNote(zone: Zone, here: RunningZone | null): string {
  if (zone.lights.length === 0) return 'no lights'
  return here?.lookName ?? 'idle'
}

/** The inputs F4 can tell are missing (F4 ruling 8): the tempo clock always runs, and the sun isn't served yet. */
export type MissingInput = Extract<InputKind, 'music' | 'home-assistant'>

/** §8.2: a tile's signal words for the first input its look would wait for. */
export const MISSING_SIGNAL: Record<MissingInput, string> = {
  music: 'Waits for music',
  'home-assistant': 'Needs Home Assistant',
}

/**
 * The inputs a look needs that aren't there (F4 ruling 8), in §6.3's chip order: music with nothing playing
 * or no link (a stale one holds its last value, §9.3), and Home Assistant with no link. Only what the server
 * serves is judged: an input it doesn't send yet is never missing.
 */
export function missingInputs(look: Look, inputs: Pick<Inputs, 'music' | 'homeAssistant'> | null): MissingInput[] {
  const needs = new Set(look.needs ?? [])
  const missing: MissingInput[] = []
  const music = inputs?.music
  if (needs.has('music') && music !== undefined && (music.state === 'disconnected' || music.state === 'idle' || music.track === null)) {
    missing.push('music')
  }
  const homeAssistant = inputs?.homeAssistant
  if (needs.has('home-assistant') && homeAssistant !== undefined && homeAssistant.state === 'disconnected') missing.push('home-assistant')
  return missing
}

/**
 * A tile's or a row's name for a screen reader: the look, and what its tags and signal say (its
 * PREVIEWING tag is its aria-pressed). What a tile's icons and a row's line show of its inputs is its
 * description (lookInputs()), since the label replaces what the button holds.
 */
export function lookLabel(look: Look, here: boolean, missing: readonly MissingInput[]): string {
  return [look.name, ...(here ? ['running here'] : []), ...(missing.length > 0 ? [MISSING_SIGNAL[missing[0]]] : [])].join(', ')
}

/**
 * A look's category and the inputs it uses, in Phone-PutLookOn's words ("Ambient · no input", "Audio ·
 * Tempo · Music"): a phone row's line when it has no state to show, and what a screen reader hears of
 * every tile and row, whatever the row's line says.
 */
export function lookInputs(look: Look): string {
  const category = CATEGORIES.find((each) => each.id === look.category)?.label ?? look.category
  const inputs = chipsFor(look).map((chip) => chip.label)
  return `${category} · ${inputs.length === 0 ? 'no input' : inputs.join(' · ')}`
}

/**
 * A phone look row's line (Phone-PutLookOn): the input it would wait for, in signal (§8.2), else
 * "Previewing on screen", "Running here now", or its category and the inputs it uses.
 */
export function rowNote(look: Look, selected: boolean, here: boolean, missing: readonly MissingInput[]): { text: string; signal: boolean } {
  if (missing.length > 0) return { text: MISSING_SIGNAL[missing[0]], signal: true }
  if (selected) return { text: 'Previewing on screen', signal: false }
  if (here) return { text: 'Running here now', signal: false }
  return { text: lookInputs(look), signal: false }
}

/** The tiles a category shows, or a search's over every look (F4 ruling 10), in the server's order. */
export function looksShown(looks: readonly Look[], category: Category, query: string): Look[] {
  const words = query.trim().toLowerCase()
  if (words !== '') return looks.filter((look) => look.name.toLowerCase().includes(words))
  return looks.filter((look) => (category === 'starred' ? look.starred : look.category === category))
}

/** The category the composer opens on (F4 ruling 10): the chosen look's, else the look running there, else Ambient. */
export function openingCategory(look: Look | undefined, here: Look | undefined): Category {
  return look?.category ?? here?.category ?? 'ambient'
}

/**
 * Where an arrow key that steps `step` looks on from look `index` of `count` lands, or -1 where it goes nowhere (F4 ruling 12). A step of
 * more than one is a row: Up on the top row and Down on the last row stay put, and only a Down into a last row shorter than the one it
 * leaves lands on that row's last look. A step of one is the next look, or none past the ends.
 */
export function steppedTo(index: number, step: number, count: number): number {
  const target = index + step
  if (index < 0 || target < 0) return -1
  if (target < count) return target
  return step > 1 && Math.floor(index / step) < Math.floor((count - 1) / step) ? count - 1 : -1
}

/** The lengths every kind but a cut is offered at (F4 ruling 11). */
export const TRANSITION_SECONDS = [1, 3, 5] as const

const KINDS = ['fade', 'wipe', 'spread', 'dissolve'] as const
const CUT: Transition = { kind: 'cut', durationS: 0 }

export interface TransitionChoice {
  /** The select's value. */
  key: string
  /** "Dissolve · 3 s", or "Cut". */
  label: string
  transition: Transition
}

/** A look's own transition (§8.2's default): a cut when it has none. */
export const lookTransition = (look: Look | undefined): Transition => look?.transition ?? CUT

function choiceOf({ kind, durationS }: Transition): TransitionChoice {
  const length = kind === 'cut' || durationS <= 0 ? null : durationS
  return { key: `${kind}:${length ?? 0}`, label: transitionLabel(kind, length), transition: { kind, durationS: length ?? 0 } }
}

/** A cut, then each kind at each of those lengths. */
const OFFERED: readonly TransitionChoice[] = [
  CUT,
  ...KINDS.flatMap((kind) => TRANSITION_SECONDS.map((durationS) => ({ kind, durationS }))),
].map(choiceOf)

/**
 * The choice a transition is: the offered one that reads the same, else its own. A length reads to a tenth
 * of a second, as the cards say it, so a look's own 2.96 s is the offered "3 s", not a second choice in the
 * same words.
 */
function choiceFor(transition: Transition): TransitionChoice {
  const own = choiceOf(transition)
  return OFFERED.find((choice) => choice.label === own.label) ?? own
}

/**
 * §8.2: "Cut, Fade, Wipe, Spread, Dissolve + duration; default the look's own". A look's own transition,
 * when it reads as none of these, is offered too, after its kind's others.
 */
export function transitionChoices(look: Look | undefined): TransitionChoice[] {
  const own = choiceFor(lookTransition(look))
  if (OFFERED.includes(own)) return [...OFFERED]
  const after = OFFERED.findLastIndex((choice) => choice.transition.kind === own.transition.kind)
  return [...OFFERED.slice(0, after + 1), own, ...OFFERED.slice(after + 1)]
}

/** The key of the choice a transition is: the select's value, and always one that its look's choices hold. */
export const transitionKey = (transition: Transition): string => choiceFor(transition).key
