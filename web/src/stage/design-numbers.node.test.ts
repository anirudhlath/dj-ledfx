// @vitest-environment node
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { checkPins, extractRender, extractSpec, readHandoff, tokenColours } from '../../scripts/design-extract.ts'
import { RENDER, SPEC, TOKENS } from './design-numbers'

// If one of these fails, the handoff changed: run `npm run design:numbers` in web/ and commit the
// file it writes. Never edit design-numbers.ts by hand.
const handoff = readHandoff(resolve(import.meta.dirname, '../../..'))

describe('the design numbers', () => {
  it("are what the spec's sentences say", () => {
    expect(SPEC).toEqual(extractSpec(handoff.spec))
  })

  it("are tokens.css's colours", () => {
    expect(TOKENS).toEqual(tokenColours(handoff.tokens))
  })

  // The renders aren't in git: a checkout without them (CI) skips this one.
  it.runIf(handoff.read !== null)('are what the pinned renders draw', () => {
    expect(RENDER).toEqual(extractRender(handoff.read!))
  })

  it('name the sentence that moved', () => {
    expect(() => extractSpec('')).toThrow(/§7\.1 Floors/)
  })

  it('come only from pinned files', () => {
    expect(() => checkPins('', ['reference/Main.html'], () => new Uint8Array())).toThrow(/reference\/Main\.html isn't the file HANDOFF\.sha256 pins/)
  })
})
