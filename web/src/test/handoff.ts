// The design handoff, for the node tests that read it (`*.node.test.ts`: design-numbers, looks-render). Node only, so
// tsconfig.app.json leaves it out and tsconfig.node.json compiles it.
import { resolve } from 'node:path'
import { readHandoff, type ReadText } from '../../scripts/design-extract.ts'

/** The handoff, read from this checkout; its renders from here or the main checkout, and `read` is null where they're missing (CI). */
export const handoff = readHandoff(resolve(import.meta.dirname, '../../..'))

/** The handoff's renders with one of them edited in memory, for how an extractor fails when a render moves: no file is written. */
export const edited = (render: string, edit: (html: string) => string): ReadText => (name) =>
  name === `reference/${render}.html` ? edit(handoff.read!(name)) : handoff.read!(name)
