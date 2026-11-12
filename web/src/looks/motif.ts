// A look's motif (§6.4), the inner markup of Looks.html's `<svg class="tb">`, keyed by looks.json's
// `thumbnail` (F5 decision 2). The markup is generated (`looks-render.ts`); this is how a thumb reads it.
import { MOTIF_SLOT, MOTIFS } from './looks-render'

export type Motif = (typeof MOTIFS)[string]

/** The look's motif, or none: a classic, a thumbnail id the handoff doesn't have, or no thumbnail (F5 decision 7). */
export function motifFor(thumbnail: string | null | undefined): Motif | undefined {
  // Own keys only: a thumbnail id of "constructor" is no motif, whatever every object inherits.
  return thumbnail != null && Object.hasOwn(MOTIFS, thumbnail) ? MOTIFS[thumbnail] : undefined
}

/** One thumb's copy of a motif: its ids start with `prefix`, so two thumbs of one look share no gradient (F5 decision 3). */
export function instanceMarkup(motif: Motif, prefix: string): string {
  return motif.markup.replaceAll(MOTIF_SLOT, prefix)
}
