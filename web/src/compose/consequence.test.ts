import { describe, expect, it } from 'vitest'
import type { Id, PreviewLight } from '@/api/contract'
import { COPIED_EFFECT, lightPlan, lookName } from '@/api/mocks/fixtures'
import { buildScenario, type ScenarioState } from '@/api/mocks/scenarios'
import { effectWord } from '@/lights/firmware'
import { HERO_NOW } from '@/test/live'
import { waitingText } from '@/zones/zone-view'
import { consequence, lightsPhrase, type ConsequencePart, type ConsequenceSources } from './consequence'

const text = (parts: readonly ConsequencePart[]) => parts.map((part) => part.text).join('')
const looksIn = (parts: readonly ConsequencePart[]) => parts.filter((part) => part.look === true).map((part) => part.text)
const capital = (words: string) => words.charAt(0).toUpperCase() + words.slice(1)

const hero = buildScenario('hero', HERO_NOW)
const zoneName = (state: ScenarioState, id: Id) => state.zones.find((zone) => zone.id === id)!.name

/** The composer's sources for a look on a zone, with the preview's answer as the mock gives it. */
function sources(state: ScenarioState, zoneId: Id, lookId: Id | null, overrides: Partial<ConsequenceSources> = {}): ConsequenceSources {
  const zone = state.zones.find((candidate) => candidate.id === zoneId)!
  const look = lookId === null ? undefined : state.looks.find((candidate) => candidate.id === lookId)!
  const lights = new Map(state.lights.map((light) => [light.id, light]))
  const plan = look === undefined ? null : zone.lights.map((id): PreviewLight => ({ id, ...lightPlan(look, lights.get(id)!) }))
  return { zone, look, running: state.running, lights, plan, missing: [], refused: null, ...overrides }
}

describe('the consequence line', () => {
  // Live-PutLookOn: "Takes over the <room> from <look>." then the lights that run their own effect.
  it('says what the look takes over, and what the lights that run their own effect will run', () => {
    const given = sources(hero, 'living', 'embers')
    const said = consequence(given)
    expect(text(said.parts)).toMatch(new RegExp(`^Takes over the ${zoneName(hero, 'living')} from ${lookName('fireflies')}\\. `))
    expect(looksIn(said.parts)).toEqual([lookName('fireflies')])
    const own = given.plan!.filter((light) => light.mode === 'own-effect')
    expect(own.length).toBeGreaterThan(0)
    expect(text(said.parts)).toContain(`${capital(lightsPhrase(own.map((light) => light.id), given.lights))} will run ${own[0].effect}.`)
    expect(said.blocked).toBe(false)
  })

  // Phone-PutLookOn: "Takes over from <look>", with no firmware sentence.
  it('says it in one short line on the phone', () => {
    const said = consequence(sources(hero, 'living', 'embers'))
    expect(text(said.short)).toBe(`Takes over from ${lookName('fireflies')}`)
    expect(looksIn(said.short)).toEqual([lookName('fireflies')])
  })

  // §11.3: "A zone left with no lights stops."
  it('names every look it takes lights from, newest first, and the zones that stop', () => {
    expect(text(consequence(sources(hero, 'bedroom', 'embers')).parts)).toMatch(
      new RegExp(`^Takes over the ${zoneName(hero, 'bedroom')} from ${lookName('comets')} and ${lookName('homesunset')}\\. ${lookName('comets')} stops\\.`),
    )
    expect(text(consequence(sources(hero, 'home', 'aurora')).parts)).toMatch(
      new RegExp(
        `^Takes over the whole home from ${lookName('homesunset')}, ${lookName('comets')} and ${lookName('fireflies')}\\. ` +
          `${lookName('comets')} and ${lookName('fireflies')} stop\\.`,
      ),
    )
  })

  it('says a look running there already starts again', () => {
    const said = consequence(sources(hero, 'living', 'fireflies'))
    expect(text(said.parts)).toMatch(new RegExp(`^Starts ${lookName('fireflies')} again on the ${zoneName(hero, 'living')}\\.`))
    expect(text(said.short)).toBe(`Starts ${lookName('fireflies')} again`)
  })

  it("doesn't say nothing runs where the look itself runs", () => {
    expect(text(consequence(sources(hero, 'living', 'fireflies')).parts)).not.toContain('Nothing runs')
  })

  // The same look can run on two zones; the whole home's start takes the lights of both.
  it('names a look once, however many zones run it', () => {
    const running = hero.running.map((each) => (each.zoneId === 'office' ? { ...each, lookId: 'fireflies', lookName: lookName('fireflies') } : each))
    expect(text(consequence(sources(hero, 'home', 'aurora', { running })).parts)).toMatch(
      new RegExp(`^Takes over the whole home from ${lookName('homesunset')} and ${lookName('fireflies')}\\. ${lookName('fireflies')} stops\\.`),
    )
  })

  it('says nothing runs there now', () => {
    const quiet = buildScenario('nothing-running', HERO_NOW)
    const said = consequence(sources(quiet, 'kitchen', 'embers'))
    expect(text(said.parts)).toMatch(new RegExp(`^Nothing runs on the ${zoneName(quiet, 'kitchen')} now\\.`))
    expect(text(said.short)).toBe('Nothing runs here now')
  })

  it('asks for a look first, and blocks Start until one is chosen', () => {
    const said = consequence(sources(hero, 'living', null))
    expect(text(said.parts)).toBe('Choose a look to see it on the stage first.')
    expect(said.blocked).toBe(true)
  })

  it('says a zone with no lights has none, and blocks Start', () => {
    const said = consequence(sources(hero, 'counter', 'embers'))
    expect(text(said.parts)).toBe(`The ${zoneName(hero, 'counter')} has no lights.`)
    expect(said.blocked).toBe(true)
  })

  // F4 ruling 3: the engine refuses a whole-home look until M6, and says so.
  it("says why the server refused the preview, and leaves Start to say it again", () => {
    const refused = "Couldn't preview the look. Home looks (whole-home scope) arrive in M6"
    const said = consequence(sources(hero, 'home', 'wisp', { refused }))
    expect(text(said.parts)).toBe(refused)
    expect(text(said.short)).toBe(refused)
    expect(said.blocked).toBe(false)
  })

  // §8.2: "the consequence line says what will happen".
  it('says what a look waiting for an input does', () => {
    const quiet = buildScenario('dj-playing', HERO_NOW)
    const said = consequence(sources(quiet, 'living', 'spectrum', { missing: ['music'] }))
    expect(text(said.parts).endsWith(` ${waitingText('music')}`)).toBe(true)
    expect(text(said.short)).toBe(waitingText('music'))
  })

  // The model puts the inputs in the chips' order (model.test.ts); the line says the first it's given.
  it("says only the first input it's given", () => {
    const said = consequence(sources(hero, 'living', 'spectrum', { missing: ['music', 'home-assistant'] }))
    expect(text(said.short)).toBe(waitingText('music'))
    expect(text(said.parts)).not.toContain(waitingText('home-assistant'))
  })

  it('says which lights get a streamed copy, after those that run their own effect', () => {
    const said = text(consequence(sources(hero, 'home', 'firmware')).parts)
    expect(said).toMatch(new RegExp(`will get a streamed copy of ${effectWord(COPIED_EFFECT)}\\.$`))
    expect(said.indexOf(' will run ')).toBeLessThan(said.indexOf(' will get a streamed copy '))
  })
})

describe('lights by name', () => {
  const named = (...names: string[]) => new Map(names.map((name, index) => [`l${index}`, { id: `l${index}`, name }]))
  const lights = named('Alpha 1', 'Alpha 2', 'Beta', 'Box 1', 'Box 2', 'Gamma 1', 'Gamma 2')

  it('fold numbered lights into their plural when all of them are there', () => {
    expect(lightsPhrase(['l0', 'l1', 'l2'], lights)).toBe('the Alphas and the Beta')
    expect(lightsPhrase(['l3', 'l4'], lights)).toBe('the Boxes')
    expect(lightsPhrase(['l0', 'l2'], lights)).toBe('the Alpha 1 and the Beta')
  })

  it('fold a name ending in a consonant and y into its -ies plural, and one ending in a vowel and y into -s', () => {
    const rooms = named('Pantry 1', 'Pantry 2', 'Bay 1', 'Bay 2')
    expect(lightsPhrase(['l0', 'l1'], rooms)).toBe('the Pantries')
    expect(lightsPhrase(['l2', 'l3'], rooms)).toBe('the Bays')
  })

  it('keep the case of a name in capitals in its plural', () => {
    const caps = named('PARTY 1', 'PARTY 2', 'BOX 1', 'BOX 2', 'BAR 1', 'BAR 2', 'BAY 1', 'BAY 2')
    expect(lightsPhrase(['l0', 'l1'], caps)).toBe('the PARTIES')
    expect(lightsPhrase(['l2', 'l3'], caps)).toBe('the BOXES')
    expect(lightsPhrase(['l4', 'l5'], caps)).toBe('the BARS')
    expect(lightsPhrase(['l6', 'l7'], caps)).toBe('the BAYS')
  })

  it("name the lights of a name that's plural already one by one, whatever its case", () => {
    const strings = named('Fairy lights 1', 'Fairy lights 2', 'FAIRY LIGHTS 1', 'FAIRY LIGHTS 2')
    expect(lightsPhrase(['l0', 'l1'], strings)).toBe('the Fairy lights 1 and the Fairy lights 2')
    expect(lightsPhrase(['l2', 'l3'], strings)).toBe('the FAIRY LIGHTS 1 and the FAIRY LIGHTS 2')
  })

  it('say how many when there are more than three names', () => {
    expect(lightsPhrase(['l0', 'l2', 'l3', 'l5'], lights)).toBe('4 lights')
  })
})
