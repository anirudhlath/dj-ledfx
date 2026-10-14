import { describe, expect, it } from 'vitest'
import type { Look } from '@/api/contract'
import { lookName } from '@/api/mocks/fixtures'
import { buildScenario, type ScenarioName } from '@/api/mocks/scenarios'
import { HERO_NOW } from '@/test/live'
import {
  CATEGORIES,
  chosenZone,
  COMPOSER_ENTRY,
  composerEntered,
  composerLink,
  composerPath,
  lookInputs,
  lookLabel,
  looksShown,
  lookTransition,
  missingInputs,
  openingCategory,
  rowNote,
  runningOn,
  steppedTo,
  tileTag,
  transitionChoices,
  transitionKey,
  zoneNote,
} from './model'

const hero = buildScenario('hero', HERO_NOW)
const zone = (id: string) => hero.zones.find((candidate) => candidate.id === id)!
const look = (id: string) => hero.looks.find((candidate) => candidate.id === id)!

describe("the composer's URL", () => {
  it('names the zone and the look chosen, each only when there is one', () => {
    expect(composerPath(null)).toBe('/live/put')
    expect(composerPath('living')).toBe('/live/put?zone=living')
    expect(composerPath('living', 'embers')).toBe('/live/put?zone=living&look=embers')
    expect(composerPath(null, 'embers')).toBe('/live/put?look=embers')
  })

  // F4 ruling 13, as amended: a push into the composer carries a marker in its history state, and nothing else is taken for one.
  it('is opened by a link that carries the entry marker, which nothing else is taken for', () => {
    expect(composerLink('living', 'embers')).toEqual({ to: '/live/put?zone=living&look=embers', state: COMPOSER_ENTRY })
    expect(composerLink().to).toBe('/live/put')
    expect(composerEntered(composerLink().state)).toBe(true)
    for (const other of [undefined, null, 'entered', 7, {}, { composer: 'left' }]) expect(composerEntered(other)).toBe(false)
  })
})

describe('the zone the composer puts a look on', () => {
  it("is the URL's, else the last one used, else the whole home", () => {
    expect(chosenZone(hero.zones, 'kitchen', 'living', look('embers'))?.id).toBe('kitchen')
    expect(chosenZone(hero.zones, null, 'living', look('embers'))?.id).toBe('living')
    expect(chosenZone(hero.zones, null, null, undefined)?.kind).toBe('home')
  })

  it('passes over a zone that has gone', () => {
    expect(chosenZone(hero.zones, 'group-9', 'group-8', undefined)?.kind).toBe('home')
  })

  it('is the whole home, wherever it sits in the list, when nothing is named', () => {
    expect(chosenZone([...hero.zones].reverse(), null, null, undefined)?.kind).toBe('home')
  })

  it("is the list's first zone when nothing is named and none is the whole home", () => {
    const rooms = hero.zones.filter((each) => each.kind !== 'home')
    expect(chosenZone(rooms, null, null, undefined)?.id).toBe(rooms[0].id)
  })

  // §8.2: "Home looks (whole-home scope) lock the zone to Whole home."
  it('is the whole home for a home look, whatever was asked', () => {
    expect(chosenZone(hero.zones, 'living', 'kitchen', look('homesunset'))?.kind).toBe('home')
  })
})

describe('what runs on a zone', () => {
  const note = (id: string) => zoneNote(zone(id), runningOn(zone(id), hero.running, hero.zones))

  it('is its own look, else the newest on its lights', () => {
    expect(note('living')).toBe(lookName('fireflies'))
    expect(note('office')).toBe(lookName('comets'))
    expect(note('kitchen')).toBe(lookName('homesunset'))
  })

  // Sub-zone 'office' is in room 'bedroom' and runs the newest look; the room's other lights run the home's.
  it("never says a room runs a sub-zone's look", () => {
    expect(note('bedroom')).toBe(lookName('homesunset'))
  })

  // Live-PutLookOn's whole-home chip says the home's own look, though a newer look runs on some of its lights.
  it("is the zone's own look before a newer one on its lights", () => {
    expect(note('home')).toBe(lookName('homesunset'))
  })

  it("is the newest look on any of the lights, a sub-zone's included, where the zone has none of its own", () => {
    const without = hero.running.filter((each) => each.zoneId !== 'home')
    expect(runningOn(zone('home'), without, hero.zones)?.lookName).toBe(lookName('comets'))
  })

  it('is idle where nothing runs, and says when a zone has no lights', () => {
    const quiet = buildScenario('nothing-running', HERO_NOW)
    const kitchen = quiet.zones.find((candidate) => candidate.id === 'kitchen')!
    expect(zoneNote(kitchen, runningOn(kitchen, quiet.running, quiet.zones))).toBe('idle')
    expect(note('counter')).toBe('no lights')
  })
})

describe('the inputs a look would wait for', () => {
  const missing = (scenario: ScenarioName, id: string) => {
    const state = buildScenario(scenario, HERO_NOW)
    return missingInputs(look(id), state.inputs)
  }

  it('are none while the music plays and Home Assistant answers', () => {
    expect(missing('hero', 'spectrum')).toEqual([])
    expect(missing('hero', 'goodnight')).toEqual([])
  })

  it('are the music while nothing plays, and Home Assistant while it has no link', () => {
    expect(missing('dj-playing', 'spectrum')).toEqual(['music'])
    expect(missing('inputs-down', 'goodnight')).toEqual(['home-assistant'])
  })

  // §9.3: a stale input's looks hold its last value.
  it("aren't the music while it's only stale", () => {
    expect(missing('inputs-down', 'spectrum')).toEqual([])
  })

  it('are never the tempo, and none an input the server doesn\'t serve yet', () => {
    expect(missing('inputs-down', 'bursts')).toEqual([])
    expect(missingInputs(look('spectrum'), { ...hero.inputs, music: undefined })).toEqual([])
    expect(missingInputs(look('spectrum'), null)).toEqual([])
  })

  // F4 ruling 8: the music is missing while it's disconnected, idle or has no track.
  it('are the music, whichever way it is missing', () => {
    const { music } = hero.inputs
    for (const gone of [{ state: 'disconnected' as const }, { state: 'idle' as const }, { track: null }]) {
      expect(missingInputs(look('spectrum'), { ...hero.inputs, music: { ...music, ...gone } })).toEqual(['music'])
    }
  })

  it('are only what the look needs, and never a Home Assistant that is only stale', () => {
    const { music, homeAssistant } = hero.inputs
    const musicGone = { ...hero.inputs, music: { ...music, state: 'disconnected' as const } }
    const bothGone = { ...musicGone, homeAssistant: { ...homeAssistant, state: 'disconnected' as const } }
    expect(missingInputs(look('embers'), bothGone)).toEqual([])
    expect(missingInputs(look('goodnight'), musicGone)).toEqual([])
    expect(missingInputs(look('goodnight'), { ...hero.inputs, homeAssistant: { ...homeAssistant, state: 'stale' } })).toEqual([])
  })

  // §6.3's chip order, whichever order the look lists what it needs in.
  it("come in the chips' order: the music, then Home Assistant", () => {
    const { music, homeAssistant } = hero.inputs
    const bothGone = {
      ...hero.inputs,
      music: { ...music, state: 'disconnected' as const },
      homeAssistant: { ...homeAssistant, state: 'disconnected' as const },
    }
    const needsBoth: Look = { ...look('goodnight'), needs: ['home-assistant', 'music'] }
    expect(missingInputs(needsBoth, bothGone)).toEqual(['music', 'home-assistant'])
  })
})

describe('the looks the composer shows', () => {
  const ids = (looks: Look[]) => looks.map((each) => each.id)

  it("are a category's, in the server's order", () => {
    expect(ids(looksShown(hero.looks, 'tempo', ''))).toEqual(ids(hero.looks.filter((each) => each.category === 'tempo')))
    const starred = hero.looks.map((each) => ({ ...each, starred: each.id === 'lava' || each.id === 'comets' }))
    expect(ids(looksShown(starred, 'starred', ''))).toEqual(['lava', 'comets'])
  })

  it("are a search's over every category, whatever the case", () => {
    expect(ids(looksShown(hero.looks, 'tempo', ` ${lookName('homesunset').toUpperCase()} `))).toEqual(['homesunset'])
    expect(looksShown(hero.looks, 'ambient', 'zzzz')).toEqual([])
  })

  it("open on the chosen look's category, else the running look's, else Ambient", () => {
    expect(openingCategory(look('comets'), look('fireflies'))).toBe('tempo')
    expect(openingCategory(undefined, look('homesunset'))).toBe('home')
    expect(openingCategory(undefined, undefined)).toBe('ambient')
  })

  it('come in §8.2\'s categories', () => {
    expect(CATEGORIES.map((category) => category.label)).toEqual(['Starred', 'Ambient', 'Tempo', 'Audio', 'Home', 'Firmware'])
  })
})

// F4 ruling 12: the arrows move through the looks "by a row" (two across in the panel, one in a list).
describe('where an arrow key steps among the looks', () => {
  // Five looks in two columns: 0 1 / 2 3 / 4, the last row one short.
  it('moves a row up or down, and a look along', () => {
    expect([steppedTo(3, -2, 5), steppedTo(1, 2, 5), steppedTo(0, 2, 5), steppedTo(2, 1, 5), steppedTo(2, -1, 5)]).toEqual([1, 3, 2, 3, 1])
  })

  it('stays put where Up or Down would leave the grid, whichever tile of the row it is', () => {
    expect([steppedTo(0, -2, 5), steppedTo(1, -2, 5), steppedTo(4, 2, 5)]).toEqual([-1, -1, -1])
    // A full last row: Down on either of its tiles leaves too.
    expect([steppedTo(4, 2, 6), steppedTo(5, 2, 6)]).toEqual([-1, -1])
  })

  it('lands on the last look where Down goes into a last row that is shorter', () => {
    expect([steppedTo(3, 2, 5), steppedTo(2, 2, 5)]).toEqual([4, 4])
  })

  it('goes nowhere past either end of a list, or from a look that is not in it', () => {
    expect([steppedTo(0, -1, 3), steppedTo(2, 1, 3), steppedTo(2, 1, 1), steppedTo(-1, 1, 3), steppedTo(-1, 2, 5)]).toEqual([-1, -1, -1, -1, -1])
  })
})

describe("a look's words in the composer", () => {
  // Phone-PutLookOn's rows: "Previewing on screen", "Running here now", "Ambient · no input".
  it("say what a phone row's line says", () => {
    expect(rowNote(look('embers'), true, true, false, [])).toEqual({ text: 'Previewing on screen', signal: false })
    expect(rowNote(look('fireflies'), false, false, true, [])).toEqual({ text: 'Running here now', signal: false })
    // The look the stage previews can be the one the zone runs: the row says it's previewing.
    expect(rowNote(look('fireflies'), true, true, true, [])).toEqual({ text: 'Previewing on screen', signal: false })
    expect(rowNote(look('aurora'), false, false, false, [])).toEqual({ text: 'Ambient · no input', signal: false })
    expect(rowNote(look('spectrum'), false, false, false, []).text).toMatch(/^Audio · Music/)
    // A look that uses two inputs says both, in §6.3's chip order.
    expect(rowNote(look('drop'), false, false, false, []).text).toBe('Audio · Tempo · Music')
  })

  // The tag and the row's note say what the stage shows, so a look whose preview is refused (a zone with no lights, or any refusal) claims
  // none of it: a refused look that runs here says so, and any other falls back to its inputs. aria-pressed is the choice, not the claim.
  it("don't claim a preview that is refused", () => {
    expect(rowNote(look('embers'), true, false, false, [])).toEqual({ text: 'Ambient · no input', signal: false })
    expect(rowNote(look('fireflies'), true, false, true, [])).toEqual({ text: 'Running here now', signal: false })
    // The input it would wait for still shows, chosen or not.
    expect(rowNote(look('spectrum'), true, false, false, ['music'])).toEqual({ text: 'Waits for music', signal: true })
    // Another look is not the one previewed, whatever the flag says.
    expect(rowNote(look('aurora'), false, true, false, []).text).toBe('Ambient · no input')
  })

  it('give a tile one tag: PREVIEWING on the look previewed, else RUNNING HERE on the look that runs, else none', () => {
    expect(tileTag(true, true, false)).toBe('previewing')
    expect(tileTag(true, true, true)).toBe('previewing')
    expect(tileTag(true, false, true)).toBe('here')
    expect(tileTag(true, false, false)).toBeNull()
    expect(tileTag(false, true, true)).toBe('here')
    expect(tileTag(false, true, false)).toBeNull()
    expect(tileTag(false, false, false)).toBeNull()
  })

  // §8.2: "its tile says 'Waits for music' / 'Needs Home Assistant' in signal", chosen or not.
  it('say the input a look would wait for first, in signal', () => {
    expect(rowNote(look('spectrum'), true, true, false, ['music'])).toEqual({ text: 'Waits for music', signal: true })
    expect(lookLabel(look('goodnight'), false, ['home-assistant'])).toBe(`${look('goodnight').name}, Needs Home Assistant`)
    expect(lookLabel(look('fireflies'), true, [])).toBe(`${look('fireflies').name}, running here`)
  })

  // missingInputs() hands over the inputs in §6.3's chip order, so the first is the one a tile says.
  it('say only the first of several inputs, after the tag', () => {
    const both = ['music', 'home-assistant'] as const
    expect(rowNote(look('spectrum'), false, false, false, both)).toEqual({ text: 'Waits for music', signal: true })
    expect(lookLabel(look('spectrum'), true, both)).toBe(`${look('spectrum').name}, running here, Waits for music`)
  })

  // Phone-PutLookOn's "Ambient · no input": the look's category, then the inputs it uses in §6.3's chip order. A tile's icons
  // are aria-hidden, so a tile gives a screen reader these words as its description.
  it("say a look's category and the inputs it uses", () => {
    expect(lookInputs(look('aurora'))).toBe('Ambient · no input')
    expect(lookInputs(look('spectrum'))).toBe('Audio · Music')
    expect(lookInputs(look('drop'))).toBe('Audio · Tempo · Music')
  })
})

describe('the transitions', () => {
  it('are a cut and each kind at 1, 3 and 5 s, said as the cards say them', () => {
    const choices = transitionChoices(look('embers'))
    expect(choices).toHaveLength(13)
    expect(choices[0]).toMatchObject({ key: 'cut:0', label: 'Cut' })
    expect(choices.find((choice) => choice.key === 'dissolve:3')?.label).toBe('Dissolve · 3 s')
  })

  // §8.2: "default the look's own".
  it("default to the look's own, offered after its kind's others where it's another length", () => {
    const own = { ...look('embers'), transition: { kind: 'wipe' as const, durationS: 2.5 } }
    expect(transitionKey(lookTransition(own))).toBe('wipe:2.5')
    const keys = transitionChoices(own).map((choice) => choice.key)
    expect(keys.slice(keys.indexOf('wipe:5'), keys.indexOf('wipe:5') + 2)).toEqual(['wipe:5', 'wipe:2.5'])
    expect(transitionKey(lookTransition(look('embers')))).toBe('cut:0')
  })

  it('say a length to a tenth of a second, as the cards do', () => {
    const own = { ...look('embers'), transition: { kind: 'spread' as const, durationS: 2.46 } }
    expect(transitionChoices(own).find((choice) => choice.key === 'spread:2.46')?.label).toBe('Spread · 2.5 s')
  })

  // A look's own length that the cards say as an offered one ("3 s" for 2.96 s) is that choice, not a second
  // choice in the same words.
  it("never read alike, wherever a look's own length falls", () => {
    for (const durationS of [2.96, 3.0000000000000004, 3, 2.5]) {
      const own = { ...look('embers'), transition: { kind: 'wipe' as const, durationS } }
      const choices = transitionChoices(own)
      expect(new Set(choices.map((choice) => choice.label)).size).toBe(choices.length)
      expect(choices.map((choice) => choice.key)).toContain(transitionKey(lookTransition(own)))
    }
  })

  it("make a look's own length the offered choice it reads as, and send that", () => {
    for (const durationS of [2.96, 3.0000000000000004]) {
      const own = { ...look('embers'), transition: { kind: 'wipe' as const, durationS } }
      expect(transitionKey(lookTransition(own))).toBe('wipe:3')
      expect(transitionChoices(own)).toHaveLength(13)
      expect(transitionChoices(own).find((choice) => choice.key === 'wipe:3')?.transition).toEqual({ kind: 'wipe', durationS: 3 })
    }
  })

  it('say no length for a cut, or for a transition that has none', () => {
    expect(transitionKey({ kind: 'cut', durationS: 3 })).toBe('cut:0')
    const none = { ...look('embers'), transition: { kind: 'fade' as const, durationS: 0 } }
    expect(transitionChoices(none).find((choice) => choice.key === 'fade:0')?.label).toBe('Fade')
  })
})
