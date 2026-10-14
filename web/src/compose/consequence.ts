// The composer's consequence line (§8.2: "an explanation of consequences"; §11.3: "The UI must show the
// consequence before Start"): what starting the look takes over and stops, what the lights that wouldn't
// stream it do instead (the preview's answer, F4 ruling 1), and what a look that waits for an input does.
// The desktop says it all (Live-PutLookOn); the phone says one short line (Phone-PutLookOn). F4 ruling 14
// has the words.
import type { Id, InputKind, Light, Look, PreviewLight, RunningZone, Zone } from '@/api/contract'
import { formatList } from '@/lib/format'
import { effectWord } from '@/lights/firmware'
import { newestFirst } from '@/stage/show'
import { waitingText } from '@/zones/zone-view'

export interface ConsequencePart {
  text: string
  /** A look's name: serif italic in the renders. */
  look?: boolean
}

export interface Consequence {
  /** The desktop's line, sentence after sentence. */
  parts: ConsequencePart[]
  /** The phone's one line: "Takes over from <look>". */
  short: ConsequencePart[]
  /** Start can't go: no look is chosen, or the zone has no lights. */
  blocked: boolean
}

export interface ConsequenceSources {
  zone: Zone
  look: Look | undefined
  running: readonly RunningZone[]
  /** The home's lights by id, for their names. */
  lights: ReadonlyMap<Id, Pick<Light, 'id' | 'name'>>
  /** What each of the zone's lights would do: the preview's answer, null until it comes. */
  plan: readonly PreviewLight[] | null
  /** The inputs the look would wait for, in §6.3's chip order. */
  missing: readonly InputKind[]
  /** What the failure says, when the server refused the look on the zone: Start's, else the preview's. */
  refused: string | null
}

const said = (text: string): ConsequencePart => ({ text })
const named = (text: string): ConsequencePart => ({ text, look: true })
const capital = (text: string) => text.charAt(0).toUpperCase() + text.slice(1)

/** "<A>", "<A> and <B>": look names in serif italic, joined as formatList joins. */
function looks(names: readonly string[]): ConsequencePart[] {
  return names.flatMap((name, index) => [...(index === 0 ? [] : [said(index === names.length - 1 ? ' and ' : ', ')]), named(name)])
}

/** "the <zone>"; the whole home is "the whole home". */
export const zonePhrase = (zone: Zone): string => (zone.kind === 'home' ? 'the whole home' : `the ${zone.name}`)

const only = (sentence: string, blocked: boolean): Consequence => ({ parts: [said(sentence)], short: [said(sentence)], blocked })

const unique = (names: readonly string[]) => [...new Set(names)]

/** A light named with a number: "<name> 2". */
const NUMBERED = /^(.*\S)\s+\d+$/

/** "Box" is "Boxes", "Pantry" is "Pantries", "Bay" is "Bays". */
function plural(word: string): string {
  if (/(x|z|ch|sh)$/i.test(word)) return `${word}es`
  if (/[^aeiou]y$/i.test(word)) return `${word.slice(0, -1)}ies`
  return `${word}s`
}

/** A name that's plural already ("Fairy lights") has no plural to fold into: its lights are named one by one. */
const foldable = (stem: string) => !/s$/i.test(stem)

/**
 * The lights by name, each "the <name>" (F4 ruling 14). Numbered lights of one name fold into its plural when
 * every light of that name in the home is there ("the <name>s"), unless the name is plural already, and more
 * than three names say how many.
 */
export function lightsPhrase(ids: readonly Id[], lights: ReadonlyMap<Id, Pick<Light, 'id' | 'name'>>): string {
  const stem = (name: string) => NUMBERED.exec(name)?.[1] ?? null
  const chosen = new Set(ids)
  const phrases: string[] = []
  const folded = new Set<string>()
  for (const id of ids) {
    const name = lights.get(id)?.name ?? id
    const base = stem(name)
    const siblings = base === null ? [] : [...lights.values()].filter((light) => stem(light.name) === base)
    if (base !== null && foldable(base) && siblings.length > 1 && siblings.every((light) => chosen.has(light.id))) {
      if (!folded.has(base)) phrases.push(`the ${plural(base)}`)
      folded.add(base)
    } else {
      phrases.push(`the ${name}`)
    }
  }
  return phrases.length > 3 ? `${ids.length} lights` : formatList(phrases)
}

/**
 * The lights that wouldn't stream the look, one sentence per effect, their own effects first: "The <name>
 * and the <name> will run <effect>." and "… will get a streamed copy of <effect>."
 */
function firmwareSentences(plan: readonly PreviewLight[], lights: ConsequenceSources['lights']): string[] {
  const groups = new Map<string, { mode: PreviewLight['mode']; effect: string; ids: Id[] }>()
  for (const { id, mode, effect } of plan) {
    if (mode === 'streaming' || effect === null) continue
    const key = `${mode}:${effect}`
    const group = groups.get(key) ?? { mode, effect, ids: [] }
    group.ids.push(id)
    groups.set(key, group)
  }
  return [...groups.values()]
    .sort((a, b) => Number(a.mode === 'streamed-copy') - Number(b.mode === 'streamed-copy'))
    .map(({ mode, effect, ids }) => {
      const who = capital(lightsPhrase(ids, lights))
      return mode === 'own-effect' ? `${who} will run ${effect}.` : `${who} will get a streamed copy of ${effectWord(effect)}.`
    })
}

export function consequence({ zone, look, running, lights, plan, missing, refused }: ConsequenceSources): Consequence {
  if (look === undefined) return only('Choose a look to see it on the stage first.', true)
  if (zone.lights.length === 0) return only(`${capital(zonePhrase(zone))} has no lights.`, true)
  if (refused !== null) return only(refused, false)

  const taking = new Set(zone.lights)
  const own = running.find((candidate) => candidate.zoneId === zone.id)
  const others = newestFirst(running).filter((other) => other.zoneId !== zone.id && other.lights.some((id) => taking.has(id)))
  const from = unique([...(own !== undefined && own.lookId !== look.id ? [own.lookName] : []), ...others.map((other) => other.lookName)])
  const stops = unique(others.filter((other) => other.lights.every((id) => taking.has(id))).map((other) => other.lookName))
  const again = own !== undefined && own.lookId === look.id
  const waiting = missing.length > 0 ? waitingText(missing[0]) : null

  const parts: ConsequencePart[] = []
  const sentence = (...next: ConsequencePart[]) => {
    if (parts.length > 0) parts.push(said(' '))
    parts.push(...next)
  }
  if (from.length > 0) sentence(said(`Takes over ${zonePhrase(zone)} from `), ...looks(from), said('.'))
  if (again) sentence(said('Starts '), named(look.name), said(` again on ${zonePhrase(zone)}.`))
  if (from.length === 0 && !again) sentence(said(`Nothing runs on ${zonePhrase(zone)} now.`))
  if (stops.length > 0) sentence(...looks(stops), said(stops.length === 1 ? ' stops.' : ' stop.'))
  for (const line of firmwareSentences(plan ?? [], lights)) sentence(said(line))
  if (waiting !== null) sentence(said(waiting))

  const short =
    waiting !== null
      ? [said(waiting)]
      : from.length > 0
        ? [said('Takes over from '), ...looks(from)]
        : again
          ? [said('Starts '), named(look.name), said(' again')]
          : [said('Nothing runs here now')]
  return { parts, short, blocked: false }
}
