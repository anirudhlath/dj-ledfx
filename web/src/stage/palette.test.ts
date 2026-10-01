import { describe, expect, it } from 'vitest'
import tokensCss from '@/styles/tokens.css?raw'
import { colourOf, cssColour, STAGE_PALETTE } from './palette'

describe("the stage's palette", () => {
  it('reads a token from tokens.css, and a render hex as it is', () => {
    const hex = /--color-stage-floor:\s*(#[0-9a-fA-F]{6})/.exec(tokensCss)![1]
    const n = parseInt(hex.slice(1), 16)
    expect(colourOf('--color-stage-floor')).toEqual([(n >> 16) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255])
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
