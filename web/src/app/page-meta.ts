import { useMatches } from 'react-router'
import type { ChromeState } from '@/chrome/state'

export interface MetaContext {
  now: Date
  chrome: ChromeState
}

/** What the chrome shows for a route (spec §4.1, §4.2). Set as the route's `handle`. */
export interface PageMeta {
  /** The top bar title and the document title. */
  title: string
  /** The line beside the title on desktop. */
  context?: (at: MetaContext) => string
  /** The phone header's serif title, when it differs ("Home" on Live). */
  phoneTitle?: string
  /** The line under the phone title. Phones show no context without it. */
  phoneContext?: (at: MetaContext) => string
  /** Phone only: the tempo strip under the header (Live). */
  tempoStrip?: boolean
}

const FALLBACK: PageMeta = { title: 'dj-ledfx' }

/** The meta of the deepest matched route that has one. */
export function usePageMeta(): PageMeta {
  const matches = useMatches()
  for (let i = matches.length - 1; i >= 0; i--) {
    const meta = matches[i].handle as PageMeta | undefined
    if (meta?.title) return meta
  }
  return FALLBACK
}
