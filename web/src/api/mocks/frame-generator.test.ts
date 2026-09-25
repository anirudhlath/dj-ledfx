import { describe, expect, it } from 'vitest'
import { lookFixtures } from './fixtures'
import { MOTIFS, motifFor, paint, type MotifSpec } from './frame-generator'

const spec = (motif: MotifSpec['motif']): MotifSpec => ({ motif, hue: 30, spread: 40 })

describe('motifFor', () => {
  it('gives every handoff look a motif', () => {
    for (const look of lookFixtures) expect(MOTIFS).toContain(motifFor(look).motif)
  })

  it("uses the look's own motif, else its category's", () => {
    expect(motifFor({ id: 'fireflies', category: 'ambient' }).motif).toBe('twinkle')
    expect(motifFor({ id: 'not-a-look', category: 'tempo' })).toEqual(motifFor({ id: 'another', category: 'tempo' }))
  })
})

describe('paint', () => {
  it.each(MOTIFS)('%s paints the LEDs and moves over time', (motif) => {
    const before = new Uint8Array(30)
    const after = new Uint8Array(30)
    paint(before, 10, spec(motif), 0.3, 0.1, 1, 1)
    paint(after, 10, spec(motif), 1.7, 0.6, 1, 1)
    expect(before.some((value) => value > 0) || after.some((value) => value > 0)).toBe(true)
    expect(after).not.toEqual(before)
  })

  it('paints the same for the same inputs', () => {
    const one = new Uint8Array(9)
    const two = new Uint8Array(9)
    paint(one, 3, spec('ripple'), 2.5, 0.4, 0.8, 7)
    paint(two, 3, spec('ripple'), 2.5, 0.4, 0.8, 7)
    expect(one).toEqual(two)
  })

  it('scales with brightness, and paints black at 0', () => {
    const full = new Uint8Array(30)
    const half = new Uint8Array(30)
    const off = new Uint8Array(30).fill(9)
    paint(full, 10, spec('glow'), 1, 0, 1, 0)
    paint(half, 10, spec('glow'), 1, 0, 0.5, 0)
    paint(off, 10, spec('glow'), 1, 0, 0, 0)
    const total = (out: Uint8Array) => out.reduce((sum, value) => sum + value, 0)
    expect(total(half)).toBeLessThan(total(full))
    expect(total(off)).toBe(0)
  })

  it('follows the beat: a pulse is brightest on it', () => {
    const on = new Uint8Array(3)
    const late = new Uint8Array(3)
    paint(on, 1, spec('pulse'), 1, 0, 1, 0)
    paint(late, 1, spec('pulse'), 1, 0.9, 1, 0)
    expect(Math.max(...on)).toBeGreaterThan(Math.max(...late))
  })

  it('writes only its own LEDs, and takes a light with none', () => {
    const out = new Uint8Array(12)
    paint(out, 2, spec('gradient'), 1, 0, 1, 0)
    expect([...out.slice(6)]).toEqual([0, 0, 0, 0, 0, 0])
    expect(() => paint(new Uint8Array(0), 0, spec('chase'), 1, 0, 1, 0)).not.toThrow()
  })
})
