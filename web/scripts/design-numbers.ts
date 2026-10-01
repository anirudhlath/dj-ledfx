// Writes src/stage/design-numbers.ts: the numbers and the colours the stage draws with, read from
// the handoff by scripts/design-extract.ts. src/stage/design-numbers.node.test.ts fails when the
// file is stale.
//   npm run design:numbers
import { writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { designNumbersSource, extractRender, extractSpec, readHandoff, tokenColours } from './design-extract.ts'

const WEB = resolve(import.meta.dirname, '..')
const handoff = readHandoff(resolve(WEB, '..'))
if (handoff.read === null) {
  console.error('design numbers: the reference renders are neither here nor in the main checkout (CLAUDE.md, "Web App Design")')
  process.exit(1)
}
const source = designNumbersSource(extractSpec(handoff.spec), extractRender(handoff.read), tokenColours(handoff.tokens))
writeFileSync(resolve(WEB, 'src/stage/design-numbers.ts'), source)
console.log('design numbers: wrote src/stage/design-numbers.ts')
