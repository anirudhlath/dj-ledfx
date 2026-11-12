import { describe, expect, it } from 'vitest'
import { MOTIF_SLOT, MOTIFS } from './looks-render'
import { instanceMarkup, motifFor } from './motif'

describe('a look’s motif (§6.4)', () => {
  it('fills the slot with the prefix, and leaves no slot behind', () => {
    const markup = instanceMarkup(MOTIFS.aurora, 'tbX')
    expect(markup).not.toContain(MOTIF_SLOT)
    expect(markup).toContain('url(#tbX')
  })

  it("finds no motif for a thumbnail the handoff doesn't have, or none", () => {
    expect(motifFor('classic-pulse')).toBeUndefined()
    expect(motifFor(null)).toBeUndefined()
    expect(motifFor(undefined)).toBeUndefined()
    expect(motifFor('aurora')).toBe(MOTIFS.aurora)
  })

  it("finds no motif in what every object inherits, which a thumbnail id isn't", () => {
    expect(motifFor('constructor')).toBeUndefined()
    expect(motifFor('toString')).toBeUndefined()
  })
})
