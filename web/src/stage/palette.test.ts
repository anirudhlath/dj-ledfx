import { describe, expect, it } from 'vitest'
import { TOKENS } from './design-numbers'
import { parseHex } from '@/lib/light-colour'
import { colourOf, cssColour, STAGE_PALETTE } from './palette'

describe("the stage's palette", () => {
  it("reads a token from tokens.css's colours, and a render hex as it is", () => {
    const [r, g, b] = parseHex(TOKENS['--color-stage-floor'])!
    expect(colourOf('--color-stage-floor')).toEqual([r / 255, g / 255, b / 255])
    expect(colourOf('#ff0000')).toEqual([1, 0, 0])
  })

  it('throws on a name tokens.css lacks', () => {
    expect(() => colourOf('--color-stage-floor-x')).toThrow(/no colour --color-stage-floor-x/)
  })

  it('writes CSS colours as var() for tokens', () => {
    expect(cssColour('--color-text')).toBe('var(--color-text)')
    expect(cssColour('#123456')).toBe('#123456')
  })

  it('has every colour the scene paints, in 0–1', () => {
    for (const colour of Object.values(STAGE_PALETTE)) expect(colour.every((v) => v >= 0 && v <= 1)).toBe(true)
  })
})
