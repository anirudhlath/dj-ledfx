import { describe, expect, it } from 'vitest'
import type { Layer, Look, RunningZone, Zone } from '@/api/contract'
import { buildScenario } from '@/api/mocks/scenarios'
import { missingInputs } from '@/compose/model'
import { HERO_NOW } from '@/test/live'
import { INPUTS } from '@/zones/zone-view'
import {
  cardInputs, emptyText, LIBRARY_TABS, librarySections, looksContext, parentName, readTab, runningOn, runningPill, searchLooks, tabCounts,
} from './library-model'
import { LIBRARY, LOOK_CATEGORIES } from './looks-render'

// The library as Looks.png draws it: the `library` scenario's looks, the hero's built-in looks with the render's six stars and its two
// saved looks after them. Neither saved look is starred; `starredSaved` is the library with the second one starred, for what a star
// on a saved look changes.
const looks: Look[] = buildScenario('library', HERO_NOW).looks
const builtIns = looks.filter((look) => look.builtIn)
const fixture = (id: string): Look => {
  const look = builtIns.find((each) => each.id === id)
  if (look === undefined) throw new Error(`no fixture look ${id}`)
  return look
}
const starredSaved: Look[] = looks.map((look) => (look.id === 'mine-2' ? { ...look, starred: true } : look))
const idsOf = (shown: readonly Look[]) => shown.map((look) => look.id)
const everything = { query: '', readyOnly: false, inputs: null } as const

// F5 plan, Review Focus 1: a `cat` the app doesn't know, or none, is All.
describe('the tabs', () => {
  it('say what Looks.png says, in its order', () => {
    expect(LIBRARY_TABS.map((tab) => tab.label)).toEqual(Object.keys(LIBRARY.counts))
    expect(LIBRARY_TABS.map((tab) => tab.id)).toEqual(['all', 'starred', ...LOOK_CATEGORIES.map((category) => category.id), 'mine'])
  })

  it("read a cat it doesn't know, or none, as All", () => {
    expect(readTab(null)).toBe('all')
    expect(readTab('')).toBe('all')
    expect(readTab('calm')).toBe('all')
    expect(readTab('constructor')).toBe('all')
    expect(readTab('Tempo')).toBe('all')
    for (const { id } of LIBRARY_TABS) expect(readTab(id)).toBe(id)
  })

  it('count as Looks.png does: All the built-ins, Mine the saved ones, Starred every star', () => {
    const counts = tabCounts(looks)
    expect(counts.all).toBe(builtIns.length)
    expect(counts.mine).toBe(looks.filter((look) => !look.builtIn).length)
    expect(counts.starred).toBe(looks.filter((look) => look.starred).length)
    for (const { id } of LOOK_CATEGORIES) expect(counts[id]).toBe(builtIns.filter((look) => look.category === id).length)
  })

  it("count what the render's tabs say", () => {
    const counts = tabCounts(looks)
    for (const { id, label } of LIBRARY_TABS) expect(counts[id], label).toBe(LIBRARY.counts[label])
  })

  it('count a starred saved look in Starred and in Mine', () => {
    const counts = tabCounts(starredSaved)
    expect(counts.starred).toBe(LIBRARY.counts.Starred + 1)
    expect(counts.mine).toBe(LIBRARY.counts.Mine)
  })
})

describe('searchLooks', () => {
  const layered: Look = {
    ...fixture('fireflies'),
    id: 'layered',
    name: 'Layered look',
    layers: [{ id: 'layer-1', kind: 'glow', name: 'Under-glow', type: 'field', blend: 'add', opacity: 1, visible: true } satisfies Layer],
  }
  const all = [...looks, layered]

  it('finds a look by its name, in any case', () => {
    const { id, name } = fixture('aurora')
    expect(idsOf(searchLooks(all, name.toUpperCase()))).toContain(id)
    expect(idsOf(searchLooks(all, name.toLowerCase()))).toContain(id)
    expect(idsOf(searchLooks(all, `  ${name}  `))).toContain(id)
  })

  it("finds a look by a layer's name", () => {
    expect(searchLooks(all, 'UNDER-GLOW')).toEqual([layered])
  })

  it("finds a look by an input's name, the card's or the input's own", () => {
    const needing = (kind: string) => all.filter((look) => [...(look.needs ?? []), ...(look.uses ?? [])].some((each) => each === kind))
    const homeAssistant = needing('home-assistant')
    expect(homeAssistant.length).toBeGreaterThan(0)
    for (const query of ['HA', 'ha', INPUTS['home-assistant'].label, 'home assistant']) {
      expect(searchLooks(all, query), query).toEqual(expect.arrayContaining(homeAssistant))
    }
    // A look that neither needs nor uses Home Assistant is found only by a name or a layer's that holds "ha".
    const namesHa = (look: Look) => [look.name, ...(look.layers ?? []).map((layer) => layer.name)].some((text) => text.toLowerCase().includes('ha'))
    for (const hit of searchLooks(all, 'HA')) expect(homeAssistant.includes(hit) || namesHa(hit), hit.id).toBe(true)
    const music = needing('music')
    expect(music.length).toBeGreaterThan(0)
    expect(searchLooks(all, 'music')).toEqual(expect.arrayContaining(music))
    const usesSun: Look = { ...fixture('rain'), id: 'uses-sun', needs: [], uses: ['sun'] }
    expect(searchLooks([usesSun], 'sun')).toEqual([usesSun])
  })

  it('does not find a look by its description', () => {
    const look = fixture('fireflies')
    const words = look.description.split(' ').slice(2, 5).join(' ')
    expect(words).not.toBe('')
    expect(idsOf(searchLooks(all, words))).not.toContain(look.id)
    expect(searchLooks(all, words)).toEqual([])
  })

  it('shows every look for no words, in their order', () => {
    expect(searchLooks(all, '')).toEqual(all)
    expect(searchLooks(all, '   ')).toEqual(all)
  })
})

describe('librarySections', () => {
  it("group the looks into looks.json's categories in its order, then Mine, leaving out an empty section", () => {
    const sections = librarySections(looks, { tab: 'all', ...everything })
    expect(sections.map((s) => s.id)).toEqual([
      ...LOOK_CATEGORIES.map((c) => c.id).filter((id) => looks.some((l) => l.builtIn && l.category === id)),
      'mine',
    ])
    expect(sections.filter((s) => s.lastRow).map((s) => s.id)).toEqual(['firmware', 'mine'])
    expect(sections.filter((s) => !s.counted).map((s) => s.id)).toEqual(['firmware', 'mine'])
    expect(sections.find((s) => s.id === 'mine')!.looks.every((l) => !l.builtIn)).toBe(true)
    expect(sections.flatMap((s) => idsOf(s.looks))).toEqual(idsOf(looks))
  })

  it("name and describe each section as looks.json does, Mine as Looks.html does", () => {
    for (const section of librarySections(looks, { tab: 'all', ...everything })) {
      if (section.id === 'mine') {
        expect(section.name).toBe('Mine')
        expect(section.blurb).toBe(LIBRARY.mineBlurb)
      } else {
        const category = LOOK_CATEGORIES.find((each) => each.id === section.id)!
        expect([section.name, section.blurb]).toEqual([category.name, category.blurb])
      }
    }
  })

  it('leave out an empty section', () => {
    const noSaved = librarySections(builtIns, { tab: 'all', ...everything })
    expect(noSaved.map((s) => s.id)).not.toContain('mine')
    expect(librarySections([], { tab: 'all', ...everything })).toEqual([])
    expect(librarySections(builtIns.filter((l) => l.category === 'tempo'), { tab: 'all', ...everything }).map((s) => s.id)).toEqual(['tempo'])
  })

  it('keep the category sections on Starred, and a saved look in Mine', () => {
    const sections = librarySections(starredSaved, { tab: 'starred', ...everything })
    expect(sections.map((s) => s.id)).toEqual(['ambient', 'tempo', 'home', 'mine'])
    expect(sections.flatMap((s) => idsOf(s.looks))).toEqual(idsOf(looks.filter((l) => l.starred && l.builtIn)).concat('mine-2'))
    expect(sections.every((s) => s.looks.every((l) => l.starred))).toBe(true)
    // As Looks.png draws it, no saved look is starred, so Mine has no section on Starred.
    expect(librarySections(looks, { tab: 'starred', ...everything }).map((s) => s.id)).toEqual(['ambient', 'tempo', 'home'])
  })

  it('show one section on a category tab, of its built-in looks only', () => {
    const sections = librarySections(looks, { tab: 'tempo', ...everything })
    expect(sections.map((s) => s.id)).toEqual(['tempo'])
    expect(idsOf(sections[0].looks)).toEqual(idsOf(builtIns.filter((l) => l.category === 'tempo')))
    expect(idsOf(sections[0].looks)).not.toContain('mine-2')
    expect(librarySections(looks, { tab: 'firmware', ...everything }).map((s) => [s.id, s.counted, s.lastRow])).toEqual([
      ['firmware', false, true],
    ])
  })

  it('show one section on Mine', () => {
    const sections = librarySections(looks, { tab: 'mine', ...everything })
    expect(sections.map((s) => s.id)).toEqual(['mine'])
    expect(idsOf(sections[0].looks)).toEqual(['mine-1', 'mine-2'])
  })

  it('search within the chosen tab', () => {
    expect(idsOf(librarySections(looks, { tab: 'all', ...everything, query: 'bursts' }).flatMap((s) => s.looks))).toEqual(['bursts', 'mine-2'])
    expect(idsOf(librarySections(looks, { tab: 'mine', ...everything, query: 'bursts' }).flatMap((s) => s.looks))).toEqual(['mine-2'])
    expect(librarySections(looks, { tab: 'ambient', ...everything, query: 'bursts' })).toEqual([])
    expect(idsOf(librarySections(starredSaved, { tab: 'starred', ...everything, query: 'bursts' }).flatMap((s) => s.looks))).toEqual(['mine-2'])
    expect(librarySections(looks, { tab: 'starred', ...everything, query: 'bursts' })).toEqual([])
  })

  it("hide the looks waiting for an input with Only ready now: inputs-down's music and Home Assistant", () => {
    const { inputs } = buildScenario('inputs-down')
    const shown = librarySections(looks, { tab: 'all', query: '', readyOnly: true, inputs }).flatMap((s) => s.looks)
    expect(shown).toEqual(looks.filter((l) => missingInputs(l, inputs).length === 0))
    expect(shown.length).toBeLessThan(looks.length)
    expect(librarySections(looks, { tab: 'all', ...everything }).flatMap((s) => s.looks)).toHaveLength(looks.length)
  })

  it('hide nothing with Only ready now where the inputs are not known', () => {
    const shown = librarySections(looks, { tab: 'all', query: '', readyOnly: true, inputs: null }).flatMap((s) => s.looks)
    expect(shown).toEqual(looks)
  })
})

describe('cardInputs', () => {
  it("name each look's inputs as Looks.html does, with no input as none", () => {
    expect(builtIns.some((look) => cardInputs(look, []).length === 0)).toBe(true)
    for (const look of builtIns) expect(cardInputs(look, []).map((i) => i.name), look.id).toEqual(LIBRARY.inputs[look.id])
  })

  it("draw each input with INPUTS' icon", () => {
    const drop = fixture('drop')
    expect(cardInputs(drop, [])).toEqual([
      { kind: 'music', name: 'Music', icon: INPUTS.music.icon, missing: false },
      { kind: 'tempo', name: 'Tempo', icon: INPUTS.tempo.icon, missing: false },
    ])
    expect(cardInputs(fixture('goodnight'), [])).toEqual([{ kind: 'home-assistant', name: 'HA', icon: INPUTS['home-assistant'].icon, missing: false }])
  })

  it('list what the look needs, then what it uses, each once, in the look’s own order', () => {
    const look: Look = { ...fixture('drop'), needs: ['tempo'], uses: ['sun', 'tempo', 'music'] }
    expect(cardInputs(look, []).map((i) => i.kind)).toEqual(['tempo', 'sun', 'music'])
    expect(cardInputs({ ...look, needs: undefined, uses: undefined }, [])).toEqual([])
  })

  it('mark a missing input', () => {
    const [look] = looks.filter((l) => (l.needs ?? []).includes('music'))
    expect(cardInputs(look, ['music']).find((i) => i.kind === 'music')!.missing).toBe(true)
    const drop = cardInputs(fixture('drop'), ['music'])
    expect(drop.map((i) => [i.kind, i.missing])).toEqual([
      ['music', true],
      ['tempo', false],
    ])
    expect(cardInputs(fixture('drop'), []).some((i) => i.missing)).toBe(false)
    expect(cardInputs(fixture('goodnight'), ['home-assistant'])[0].missing).toBe(true)
  })
})

// F5 plan, Review Focus 2: a look on several zones, or on a zone /api/zones doesn't name, is a pill of the zones it can name.
describe('where a look runs', () => {
  const zones = [
    { id: 'a', name: 'Alpha' },
    { id: 'b', name: 'Beta' },
  ] as Zone[]
  const runs = (...pairs: [zoneId: string, lookId: string][]) => pairs.map(([zoneId, lookId]) => ({ zoneId, lookId }) as RunningZone)

  it("names every zone a look runs on, in running order, leaving out a zone it can't name", () => {
    expect(runningOn('x', runs(['a', 'x'], ['gone', 'x'], ['b', 'x']), zones)).toEqual(['Alpha', 'Beta'])
    expect(runningOn('x', runs(['b', 'x'], ['a', 'x']), zones)).toEqual(['Beta', 'Alpha'])
  })

  it('names no zone for a look that runs nowhere', () => {
    expect(runningOn('x', runs(['a', 'y'], ['b', 'y']), zones)).toEqual([])
    expect(runningOn('x', [], zones)).toEqual([])
  })

  it('says it in a pill: the first zone and how many more, and all of them aloud', () => {
    expect(runningPill(['Alpha'])).toEqual({ shown: 'Alpha', spoken: 'Running on Alpha' })
    expect(runningPill(['Alpha', 'Beta'])).toEqual({ shown: 'Alpha +1', spoken: 'Running on Alpha and Beta' })
    expect(runningPill(['Alpha', 'Beta', 'Gamma'])).toEqual({ shown: 'Alpha +2', spoken: 'Running on Alpha, Beta and Gamma' })
    expect(runningPill([])).toBeNull()
  })

  it("names the zones of the hero's running looks", () => {
    const { running, zones: heroZones } = buildScenario('hero')
    expect(running.length).toBeGreaterThan(0)
    for (const each of running) {
      expect(runningOn(each.lookId, running, heroZones)).toContain(heroZones.find((zone) => zone.id === each.zoneId)!.name)
    }
  })
})

describe('parentName', () => {
  it("names a saved look's parent, and none when it's gone", () => {
    expect(parentName(looks.find((l) => l.id === 'mine-1')!, looks)).toBe(fixture('fireflies').name)
    expect(parentName(looks.find((l) => l.id === 'mine-2')!, looks)).toBe(fixture('bursts').name)
    expect(parentName({ ...fixture('rain'), builtIn: false, derivedFrom: 'gone' }, looks)).toBeNull()
  })

  it('names none for a look that is not derived', () => {
    expect(parentName(fixture('rain'), looks)).toBeNull()
    expect(parentName({ ...fixture('rain'), derivedFrom: undefined }, looks)).toBeNull()
  })
})

describe('emptyText', () => {
  it('says why the grid is empty: the search first, then the switch, then the tab', () => {
    expect(emptyText({ tab: 'starred', query: 'zz', readyOnly: true })).toBe('No looks match “zz”.')
    expect(emptyText({ tab: 'starred', query: '', readyOnly: true })).toBe('No looks are ready now.')
    expect(emptyText({ tab: 'starred', query: '', readyOnly: false })).toBe('No starred looks yet.')
    expect(emptyText({ tab: 'mine', query: '', readyOnly: false })).toBe('No saved looks yet.')
    expect(emptyText({ tab: 'home', query: '', readyOnly: false })).toBe('No home looks yet.')
    expect(emptyText({ tab: 'all', query: '', readyOnly: false })).toBe('No looks yet.')
  })

  it('reads the search as the composer does, trimmed, and none for blank words', () => {
    expect(emptyText({ tab: 'all', query: '  zz ', readyOnly: false })).toBe('No looks match “zz”.')
    expect(emptyText({ tab: 'all', query: '   ', readyOnly: true })).toBe('No looks are ready now.')
  })

  it('names every category tab in the lower case', () => {
    for (const { id } of LOOK_CATEGORIES) expect(emptyText({ tab: id, query: '', readyOnly: false })).toBe(`No ${id} looks yet.`)
  })
})

describe('looksContext', () => {
  it('says how many looks there are and how many zones run', () => {
    const { running } = buildScenario('hero')
    expect(running.length).toBeGreaterThan(0)
    expect(looksContext(looks, running)).toBe(`${tabCounts(looks).all} looks · ${running.length} running`)
    expect(looksContext(looks, [])).toBe(`${LIBRARY.counts.All} looks · 0 running`)
  })

  it('says one look, not one looks', () => {
    expect(looksContext([fixture('rain')], [])).toBe('1 look · 0 running')
    expect(looksContext([], [])).toBe('0 looks · 0 running')
  })
})
