// A value that keeps its identity while the caller's test says it's the same as the last one, so a
// memo, or a memo() component, keyed on it holds across renders whose inputs changed in ways it
// doesn't read: the stage's light layer across a `lights` push that changes only colours, say.
import { useState } from 'react'

export function useStable<T>(value: T, same: (kept: T, next: T) => boolean): T {
  const [kept, keep] = useState(value)
  if (kept === value || same(kept, value)) return kept
  // React's way to adjust state to a prop: the render starts again at once with the new value kept.
  keep(value)
  return value
}

/** Two maps with the same keys, each with the same value (Object.is). */
export function sameEntries<K, V>(a: ReadonlyMap<K, V>, b: ReadonlyMap<K, V>): boolean {
  if (a.size !== b.size) return false
  for (const [key, value] of a) if (!b.has(key) || !Object.is(b.get(key), value)) return false
  return true
}
