// @vitest-environment node
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  checkPins, extractLive, extractLiveRender, extractRender, extractSpec, readHandoff, tokenColours, type ReadText,
} from '../../scripts/design-extract.ts'
import { LIVE_RENDER, LIVE_SPEC } from '../design/live-numbers'
import { RENDER, SPEC, TOKENS } from './design-numbers'

// If one of these fails, the handoff changed: run `npm run design:numbers` in web/ and commit the
// files it writes. Never edit design-numbers.ts or live-numbers.ts by hand.
const handoff = readHandoff(resolve(import.meta.dirname, '../../..'))

/** The handoff's renders with one of them edited in memory, for how the extractor fails when a render moves: no file is written. */
const edited = (render: string, edit: (html: string) => string): ReadText => (name) =>
  name === `reference/${render}.html` ? edit(handoff.read!(name)) : handoff.read!(name)

describe('the design numbers', () => {
  it("are what the spec's sentences say", () => {
    expect(SPEC).toEqual(extractSpec(handoff.spec))
  })

  it("are what the spec's sentences say outside the stage too", () => {
    expect(LIVE_SPEC).toEqual(extractLive(handoff.spec))
  })

  it("are tokens.css's colours", () => {
    expect(TOKENS).toEqual(tokenColours(handoff.tokens))
  })

  // The renders aren't in git: a checkout without them (CI) skips this one.
  it.runIf(handoff.read !== null)('are what the pinned renders draw', () => {
    expect(RENDER).toEqual(extractRender(handoff.read!))
    expect(LIVE_RENDER).toEqual(extractLiveRender(handoff.read!))
  })

  // §5.4: "The pip lights to `text` with a soft glow and fades to `control-hover` by the end of the beat."
  it('draw a pip as §5.4 says it moves, inside one beat', () => {
    expect(LIVE_RENDER.pip.lit).toBe('--color-text')
    expect(LIVE_RENDER.pip.rest).toBe('--color-control-hover')
    expect(LIVE_RENDER.pip.endBeats).toBe(1)
    expect(LIVE_RENDER.pip.riseBeats).toBeLessThan(LIVE_RENDER.pip.holdBeats)
    expect(LIVE_RENDER.pip.holdBeats).toBeLessThan(LIVE_RENDER.pip.endBeats)
  })

  // F3 decision 34: §6.3 gives a ZoneRow's "small swatches" no size, so they are the renders' (State-Problems, Live-Doorbell).
  it("size a ZoneRow's small swatches below a card's", () => {
    expect(LIVE_RENDER.rowSwatchPx).toBeLessThan(LIVE_SPEC.swatch.px)
  })

  // §6.4: LookThumb is "a small 16:10 scene", and the composer's tile holds one (F4 ruling 7).
  it("draw a look's thumb at 16:10", () => {
    expect(LIVE_RENDER.lookThumb.width / LIVE_RENDER.lookThumb.height).toBe(16 / 10)
  })

  // Phone-PutLookOn draws the chosen zone's outline narrower than the spec's number, which Live-PutLookOn's matches; the phone's
  // render isn't scaled (its floor strokes are as wide as the desktop's), so the narrower outline is the render's own.
  it("draw the phone's zone outline narrower than the desktop's", () => {
    expect(LIVE_RENDER.phoneOutlinePx).toBeGreaterThan(0)
    expect(LIVE_RENDER.phoneOutlinePx).toBeLessThan(SPEC.compose.outlinePx)
  })

  // The composer's thumb and its chosen-zone notes use these three as raw CSS colours. If tokens.css ever gains one of the hexes,
  // colour() names its custom property instead (`--color-…`), and the style built from that would silently be nothing.
  it("give the composer's three colours as hex", () => {
    expect(LIVE_RENDER.lookThumb.background).toMatch(/^#/)
    expect(LIVE_RENDER.selectedZoneNote.chip).toMatch(/^#/)
    expect(LIVE_RENDER.selectedZoneNote.button).toMatch(/^#/)
  })

  // §7.4: "firefly and ember particles (tiny glowing points)". F10 draws every particle as Main.html draws a firefly.
  it('draw a particle as a glow fading to nothing at its edge, round a smaller, whiter core', () => {
    const { glow, core } = RENDER.particle
    expect(glow.stops.map((stop) => stop.at)).toEqual([0, ...glow.stops.slice(1, -1).map((stop) => stop.at), 1])
    expect(glow.stops.at(-1)!.alpha).toBe(0)
    expect(core.lift).toBeGreaterThan(0)
    expect(core.lift).toBeLessThan(1)
    expect(core.share).toBeLessThan(glow.stops[1].at)
    expect(core.minPx).toBeLessThan(core.maxPx)
  })

  // A firefly whose core no longer keeps the rule is named, with its sizes.
  it.runIf(handoff.read !== null)('name the firefly drawn off the rule', () => {
    const swollen = (html: string) => html.replace(/(<g class="ff0"><circle [^>]+><\/circle><circle cx="[\d.]+" cy="[\d.]+" r=")[\d.]+"/, '$13"')
    expect(() => extractRender(edited('Main', swollen))).toThrow(/fireflies: each a glow and a core draw a core of [\d.]+ px on a glow of [\d.]+ px, off the rule/)
  })

  it('name the sentence that moved', () => {
    expect(() => extractSpec('')).toThrow(/§7\.1 Floors/)
    expect(() => extractLive('')).toThrow(/§4\.4/)
    expect(() => extractLive(handoff.spec.replace('**`LookTile`** (composer', '**`LookTile`** (library'))).toThrow(/§6\.4 LookTile/)
  })

  // A render whose thumb moved is named, whichever it is: it never drops out and leaves the other's to stand for both.
  it.runIf(handoff.read !== null)('name the render whose thumb moved', () => {
    const renamed = (html: string) => html.replaceAll('<svg class="tb "', '<svg class="tile "')
    expect(() => extractLiveRender(edited('Phone-PutLookOn', renamed))).toThrow(/Phone-PutLookOn\.html's thumb no longer reads/)
    expect(() => extractLiveRender(edited('Live-PutLookOn', renamed))).toThrow(/Live-PutLookOn\.html's thumb no longer reads/)
  })

  // The phone's outline is read from the one path Phone-PutLookOn draws it with: a render that moves it is named.
  it.runIf(handoff.read !== null)('name the render whose zone outline moved', () => {
    const filled = (html: string) => html.replace(/(<path d="M[\d. L]+ Z") fill="none"/, '$1 fill="#000000"')
    expect(() => extractLiveRender(edited('Phone-PutLookOn', filled))).toThrow(/Phone-PutLookOn\.html's zone outline no longer reads/)
  })

  // Thumbs that still read but draw another scene in one render: the two renders are named together.
  it.runIf(handoff.read !== null)('name the renders that draw a thumb two ways', () => {
    const taller = (html: string) => html.replaceAll(/(<svg class="tb " viewBox="0 0 \d+ )\d+"/g, (_, head: string) => `${head}999"`)
    const paler = (html: string) => html.replaceAll(/(<svg class="tb "[^>]*background: )#[0-9a-f]{6}/g, (_, head: string) => `${head}#123456`)
    const twoWays = /Live-PutLookOn\.html's thumb and Phone-PutLookOn\.html's thumb draw the scene two ways/
    expect(() => extractLiveRender(edited('Phone-PutLookOn', taller))).toThrow(twoWays)
    expect(() => extractLiveRender(edited('Phone-PutLookOn', paler))).toThrow(twoWays)
  })

  it('come only from pinned files', () => {
    expect(() => checkPins('', ['reference/Main.html'], () => new Uint8Array())).toThrow(/reference\/Main\.html isn't the file HANDOFF\.sha256 pins/)
  })
})
