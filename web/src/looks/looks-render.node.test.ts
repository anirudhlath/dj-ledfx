// @vitest-environment node
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { extractLooksRender, looksRenderCss } from '../../scripts/looks-extract.ts'
import { LIVE_SPEC } from '../design/live-numbers'
import { edited, handoff } from '../test/handoff'
import { LIBRARY, LOOK_CATEGORIES, MOTIF_SLOT, MOTIFS } from './looks-render'

describe('the looks render', () => {
  // If this fails, the handoff changed: run `npm run design:numbers` in web/ and commit what it writes.
  it.runIf(handoff.read !== null)('is what Looks.html draws', () => {
    const render = extractLooksRender(handoff.read!, handoff.looks)
    expect({ MOTIFS, LOOK_CATEGORIES, LIBRARY }).toEqual({ MOTIFS: render.motifs, LOOK_CATEGORIES: render.categories, LIBRARY: render.library })
    expect(readFileSync(resolve(import.meta.dirname, 'looks-render.css'), 'utf8')).toBe(looksRenderCss(render))
  })

  it("has looks.json's categories as they are", () => {
    expect(LOOK_CATEGORIES).toEqual(JSON.parse(handoff.looks).categories)
  })

  it('has a motif for every thumbnail in looks.json, and no other', () => {
    const thumbnails = JSON.parse(handoff.looks).looks.map((look: { thumbnail: string }) => look.thumbnail)
    expect(Object.keys(MOTIFS).sort()).toEqual([...thumbnails].sort())
  })

  it("marks the tempo and audio looks' motifs as the beat's, and only those", () => {
    for (const look of JSON.parse(handoff.looks).looks) expect(MOTIFS[look.thumbnail].beat).toBe(['tempo', 'audio'].includes(look.category))
  })

  it("leaves none of the render's ids in a motif: every id, url(#…) and href=\"#…\" starts with the slot", () => {
    for (const { markup } of Object.values(MOTIFS)) {
      expect(markup).not.toMatch(/\b(lk|mn)\d+[a-z]/)
      for (const [, ref] of markup.matchAll(/(?:id="|url\(#|href="#)([^")]*)/g)) expect(ref.startsWith(MOTIF_SLOT)).toBe(true)
    }
  })

  // §5.4: "The mocks use CSS keyframes at 121.8 BPM only as a stand-in." The writer's beatMs() rests on it. These looks' motifs loop once a beat at that
  // tempo, read from the render today; a motif that loops in two beats, or four, is no stand-in for the beat and isn't listed.
  const LOOP_ONE_BEAT = ['ball', 'bursts', 'fountain', 'speakers', 'spectrum', 'vortex']

  it("draws exactly these beat motifs at §5.4's stand-in tempo, once a beat", () => {
    const loops = (markup: string) => [...markup.matchAll(/animation: ([^;"]*)/g)].flatMap((a) => [...a[1].matchAll(/\bt_\w+ ([\d.]+)s/g)].map((d) => Number(d[1])))
    const oneBeat = JSON.parse(handoff.looks).looks
      .filter((look: { thumbnail: string }) => MOTIFS[look.thumbnail].beat && loops(MOTIFS[look.thumbnail].markup).some((s) => Math.abs(s - 60 / LIVE_SPEC.mockBpm) < 5e-4))
      .map((look: { id: string }) => look.id)
    expect(oneBeat.sort()).toEqual(LOOP_ONE_BEAT)
  })

  it("reads the library Looks.html holds, and its tabs' counts agree with its cards", () => {
    const ids = new Set(JSON.parse(handoff.looks).looks.map((look: { id: string }) => look.id))
    expect(LIBRARY.counts.Starred).toBe(LIBRARY.starred.length) // Looks.html stars no saved look
    expect(LIBRARY.counts.Mine).toBe(LIBRARY.mine.length)
    expect(LIBRARY.counts.All).toBe(ids.size)
    for (const id of [...LIBRARY.starred, ...LIBRARY.mine.map((m) => m.from), ...Object.keys(LIBRARY.running), LIBRARY.hovered]) expect(ids.has(id)).toBe(true)
  })

  it.runIf(handoff.read !== null)('names the look whose ids no longer read', () => {
    // Its first id renamed: the prefix is no longer one the render uses, and the leftover-prefix check alone would let it through.
    const renamed = (html: string) => html.replace('id="lk6', 'id="zz6')
    expect(() => extractLooksRender(edited('Looks', renamed), handoff.looks)).toThrow(/Looks\.html's motif for aurora/)
  })

  it.runIf(handoff.read !== null)('names the render that draws a motif two ways', () => {
    const moved = (html: string) => html.replace(/(<svg class="tb "[^>]*>[\s\S]*?<circle cx=")([\d.]+)/, (_, head: string, x: string) => `${head}${Number(x) + 9}`)
    expect(() => extractLooksRender(edited('Live-PutLookOn', moved), handoff.looks)).toThrow(/Live-PutLookOn\.html draws the motif for \w+ unlike Looks\.html/)
    expect(() => extractLooksRender(edited('Phone-PutLookOn', moved), handoff.looks)).toThrow(/Phone-PutLookOn\.html draws the motif for \w+ unlike Looks\.html/)
  })

  it.runIf(handoff.read !== null)('names the saved look drawn unlike the look it came from', () => {
    const moved = (html: string) => html.replace(/(id="mn1[a-z]+"[\s\S]*?<circle cx=")([\d.]+)/, (_, head: string, x: string) => `${head}${Number(x) + 9}`)
    expect(() => extractLooksRender(edited('Looks', moved), handoff.looks)).toThrow(/Looks\.html's saved look .+ is drawn unlike \w+/)
  })

  // Each of the extractor's other checks names what moved, the render and the look or card. Names come from looks.json and the library, never typed.
  describe.runIf(handoff.read !== null)('names what else of Looks.html moved', () => {
    const { looks } = JSON.parse(handoff.looks) as { looks: { id: string; name: string; thumbnail: string }[] }
    const [first, second] = looks
    const [saved] = LIBRARY.mine
    const [runningId] = Object.keys(LIBRARY.running)
    const running = Object.keys(LIBRARY.running).length
    // A keyframe one motif alone animates with: taking it out leaves that look's motif with nothing to play.
    const users = new Map<string, string[]>()
    for (const look of looks) {
      const names = [...MOTIFS[look.thumbnail].markup.matchAll(/animation:([^;"]*)/g)].flatMap((a) => a[1].match(/\bt_\w+/g) ?? [])
      for (const name of new Set(names)) users.set(name, [...(users.get(name) ?? []), look.id])
    }
    const [[lone, [loner]]] = [...users].filter(([, ids]) => ids.length === 1)
    const dot = '<span style="width: 6px; height: 6px; animation: livedot 1s"></span>'
    const scrim = '<div style="background: linear-gradient(to top, #000, transparent)"></div>'
    const afterSaved = (html: string, added: string) => html.replace(`>${saved.name}</h3>`, `>${saved.name}</h3>${added}`)
    const parent = looks.find((look) => look.id === saved.from)!
    const renamed = (from: string, to: string) => (html: string) => html.replace(`>${from}</h3>`, `>${to}</h3>`)
    const without = (name: string) => (html: string) => {
      const at = html.indexOf(`>${name}</h3>`)
      return html.slice(0, html.lastIndexOf('<article', at)) + html.slice(html.indexOf('</article>', at) + '</article>'.length)
    }
    const tabs = /(<button type="button" aria-pressed="(?:true|false)" style="[^"]*">[^<]+)<span style="[^"]*">\d+<\/span>/g

    it.each<[string, string, (html: string) => string, string]>([
      ['a card that is no look', 'Looks', renamed(first.name, 'Unlisted'), "Looks.html's card Unlisted is no look in looks.json"],
      ['a look drawn twice', 'Looks', renamed(second.name, first.name), `Looks.html draws ${first.id} twice`],
      ['a look with no card', 'Looks', without(first.name), `Looks.html has no card for ${first.id}`],
      ['a motif with an svg in it', 'Looks', (html) => html.replace('</defs>', '</defs><svg></svg>'), `Looks.html's motif for ${first.id} no longer reads`],
      // The id= row is the brief's own test above; these two are the other places a motif names an id. The renamed prefix isn't one the slot replaces.
      ['a url(#…) to an id of no slot', 'Looks', (html) => html.replace('url(#lk6', 'url(#zz6'), "Looks.html's motif for aurora no longer reads"],
      ['a href to an id of no slot', 'Looks', (html) => html.replace('</defs>', '</defs><use href="#zz6zz"></use>'), `Looks.html's motif for ${first.id} no longer reads`],
      [
        'a keyframe a motif animates with',
        'Looks',
        (html) => html.replace(new RegExp(`@keyframes ${lone}(?!\\w)`), '@keyframes u_lost'),
        `Looks.html's motif for ${loner} animates with ${lone}, which its t_* keyframes don't hold`,
      ],
      ['a star', 'Looks', (html) => html.replace(`aria-label="Star ${first.name}"`, `aria-label="Fave ${first.name}"`), `Looks.html's star on ${first.id} no longer reads`],
      ['a scrim', 'Looks', (html) => html.replaceAll('linear-gradient(to top', 'linear-gradient(to bottom'), "Looks.html's hovered card no longer reads: 0 draw a scrim"],
      ['a second scrim', 'Looks', (html) => afterSaved(html, scrim), "Looks.html's hovered card no longer reads: 2 draw a scrim"],
      [
        'a scrim on a saved look',
        'Looks',
        (html) => afterSaved(html.replace('linear-gradient(to top', 'linear-gradient(to bottom'), scrim),
        `Looks.html's hovered card no longer reads: the scrim is on the saved look ${saved.name}`,
      ],
      ['a running pill on a saved look', 'Looks', (html) => afterSaved(html, dot), `Looks.html's running pills no longer read: ${running + 1} drawn, ${running} on a built-in look's card with a zone`],
      [
        'a running pill with no zone',
        'Looks',
        (html) => html.replace(new RegExp(`(width: 6px; height: 6px;[^"]*animation: livedot[^"]*"></span>)(${LIBRARY.running[runningId]})</span>`), '$1<b>$2</b></span>'),
        `Looks.html's running pills no longer read: ${running} drawn, ${running - 1} on a built-in look's card with a zone`,
      ],
      ['a saved look with no parent', 'Looks', (html) => html.replace(`>From ${parent.name}<`, `>${parent.name}<`), `Looks.html's saved look ${saved.name} no longer says where it came from`],
      ['a saved look from no look', 'Looks', (html) => html.replace(`>From ${parent.name}<`, '>From Nobody<'), `Looks.html's saved look ${saved.name} comes from Nobody, which looks.json doesn't have`],
      ['a saved look with no description', 'Looks', (html) => html.replace(`>${saved.description}<`, '><'), `Looks.html's saved look ${saved.name} no longer reads its description`],
      ['the tab pills', 'Looks', (html) => html.replaceAll(tabs, '$1'), "Looks.html's tab pills no longer read"],
      ["the Mine header's blurb", 'Looks', (html) => html.replace(`>${LIBRARY.mineBlurb}<`, '><'), "Looks.html's Mine header no longer reads"],
      ['the .tb rules and keyframes', 'Looks', (html) => html.replaceAll('@keyframes t_', '@keyframes u_').replaceAll('.tb ', '.tc '), "Looks.html's .tb rules and t_* keyframes no longer read"],
      [
        'a look a PutLookOn render names',
        'Live-PutLookOn',
        (html) => html.replace(/(<svg class="tb "[\s\S]*?<\/svg>[\s\S]*?<span style="font-family: 'Instrument Serif'[^"]*">)[^<]*/, '$1Unlisted'),
        "Live-PutLookOn.html draws a motif for Unlisted, which looks.json doesn't have",
      ],
    ])('%s', (_, render, edit, message) => {
      expect(() => extractLooksRender(edited(render, edit), handoff.looks)).toThrow(`design numbers: ${message}`)
    })
  })
})
