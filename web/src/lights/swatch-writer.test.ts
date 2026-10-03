import { describe, expect, it } from 'vitest'
import type { LightFrame } from '@/api/frames'
import { swatchFill } from '@/lib/light-colour'
import { pillFill } from './swatch-writer'

const frameOf = (leds: number[][]): LightFrame => ({ rgb: Uint8Array.from(leds.flat()), seq: 1, count: leds.length, at: 0, recent: 1 })

describe('pillFill', () => {
  // §6.6 "Multizone or matrix: a … pill with a left-to-right gradient of its zones".
  it("runs a pill's LEDs left to right, each a swatch's fill", () => {
    expect(pillFill(frameOf([[255, 0, 0], [0, 255, 0], [0, 0, 255]]))).toBe(
      `linear-gradient(90deg, ${swatchFill([255, 0, 0])} 0%, ${swatchFill([0, 255, 0])} 50%, ${swatchFill([0, 0, 255])} 100%)`,
    )
  })

  it('samples a long light evenly, from its first LED to its last', () => {
    const leds = Array.from({ length: 60 }, (_, i) => [i * 4, 0, 0])
    const fill = pillFill(frameOf(leds))
    expect(fill.match(/%/g)).toHaveLength(10)
    expect(fill.startsWith(`linear-gradient(90deg, ${swatchFill([0, 0, 0])} 0%`)).toBe(true)
    expect(fill.endsWith(`${swatchFill([236, 0, 0])} 100%)`)).toBe(true)
  })
})
