import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

// CLAUDE.md "Web App Design": the handoff's files are used byte for byte. If this fails, the
// handoff changed or a copy was edited. Copy the file again; never edit either side.
const REPO = resolve(import.meta.dirname, '../../..')
const HANDOFF = 'docs/design/web-app'
const COPIES = [
  { name: 'tokens.css', copy: 'web/src/styles/tokens.css' },
  { name: 'icons.ts', copy: 'web/src/design/icons.ts' },
]

const read = (path: string) => readFileSync(resolve(REPO, path))

describe('design payload copies', () => {
  const pins = read(`${HANDOFF}/HANDOFF.sha256`).toString('utf8')

  for (const { name, copy } of COPIES) {
    it(`${copy} is ${HANDOFF}/${name}, byte for byte`, () => {
      const same = read(copy).equals(read(`${HANDOFF}/${name}`))
      expect(same, `run from the repo root: cp ${HANDOFF}/${name} ${copy}`).toBe(true)
    })

    it(`${HANDOFF}/${name} still matches its HANDOFF.sha256 pin`, () => {
      const hash = createHash('sha256').update(read(`${HANDOFF}/${name}`)).digest('hex')
      expect(pins).toContain(`${hash}  ${name}\n`)
    })
  }
})
