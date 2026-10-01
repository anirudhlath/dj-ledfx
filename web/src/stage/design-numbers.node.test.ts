// @vitest-environment node
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { checkPins, extractRender, extractSpec, handoffDirs } from '../../scripts/design-extract.ts'
import { RENDER, SPEC } from './design-numbers'

// If one of these fails, the handoff changed: run `npm run design:numbers` in web/ and commit the
// file it writes. Never edit design-numbers.ts by hand.
const dirs = handoffDirs(resolve(import.meta.dirname, '../../..'))

describe('the design numbers', () => {
  it("are what the spec's sentences say", () => {
    expect(SPEC).toEqual(extractSpec(readFileSync(dirs.spec, 'utf8')))
  })

  // The renders aren't in git: a checkout without them (CI) skips this one.
  it.runIf(dirs.renders !== null)("are what the pinned renders draw", () => {
    const renders = dirs.renders!
    const inRenders = (name: string) => resolve(renders, name.replace(/^reference\//, ''))
    const read = (name: string) => readFileSync(name.startsWith('reference/') ? inRenders(name) : resolve(dirs.design, name), 'utf8')
    checkPins(read('HANDOFF.sha256'), (name) => readFileSync(inRenders(name)))
    expect(RENDER).toEqual(extractRender(read))
  })

  it('name the sentence that moved', () => {
    expect(() => extractSpec('')).toThrow(/§7\.1 Floors/)
  })
})
