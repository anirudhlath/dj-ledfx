// @vitest-environment node
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  checkPins, extractLive, extractLiveRender, extractRender, extractSpec, readHandoff, tokenColours,
} from '../../scripts/design-extract.ts'
import { LIVE_RENDER, LIVE_SPEC } from '../design/live-numbers'
import { RENDER, SPEC, TOKENS } from './design-numbers'

// If one of these fails, the handoff changed: run `npm run design:numbers` in web/ and commit the
// files it writes. Never edit design-numbers.ts or live-numbers.ts by hand.
const handoff = readHandoff(resolve(import.meta.dirname, '../../..'))

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

  it('name the sentence that moved', () => {
    expect(() => extractSpec('')).toThrow(/§7\.1 Floors/)
    expect(() => extractLive('')).toThrow(/§4\.4/)
  })

  it('come only from pinned files', () => {
    expect(() => checkPins('', ['reference/Main.html'], () => new Uint8Array())).toThrow(/reference\/Main\.html isn't the file HANDOFF\.sha256 pins/)
  })
})
