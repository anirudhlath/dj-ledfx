// Writes, or checks, src/stage/design-numbers.ts: the numbers the stage draws with, read from the
// handoff by scripts/design-extract.ts.
//   npm run design:numbers                write it
//   npm run design:numbers -- --check     fail if it isn't what the handoff says
import { readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { parseArgs } from 'node:util'
import { checkPins, designNumbersSource, extractRender, extractSpec, handoffDirs } from './design-extract.ts'

const WEB = resolve(import.meta.dirname, '..')
const OUT = resolve(WEB, 'src/stage/design-numbers.ts')
const { values } = parseArgs({ options: { check: { type: 'boolean', default: false } } })

const dirs = handoffDirs(resolve(WEB, '..'))
const renders = dirs.renders
if (renders === null) {
  console.error('design numbers: the reference renders are neither here nor in the main checkout (CLAUDE.md, "Web App Design")')
  process.exit(1)
}
const inRenders = (name: string) => resolve(renders, name.replace(/^reference\//, ''))
const read = (name: string) => readFileSync(name.startsWith('reference/') ? inRenders(name) : resolve(dirs.design, name), 'utf8')
checkPins(read('HANDOFF.sha256'), (name) => readFileSync(inRenders(name)))
const source = designNumbersSource(extractSpec(readFileSync(dirs.spec, 'utf8')), extractRender(read))

if (values.check) {
  if (readFileSync(OUT, 'utf8') !== source) {
    console.error('design numbers: src/stage/design-numbers.ts is not what the handoff says. Run: cd web && npm run design:numbers')
    process.exit(1)
  }
  console.log('design numbers match the handoff')
} else {
  writeFileSync(OUT, source)
  console.log('design numbers: wrote src/stage/design-numbers.ts')
}
