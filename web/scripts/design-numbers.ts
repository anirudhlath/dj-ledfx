// Writes src/stage/design-numbers.ts, the numbers and the colours the stage draws with, and
// src/pages/live-numbers.ts, the numbers Live lays its page out by, read from the handoff by
// scripts/design-extract.ts. src/stage/design-numbers.node.test.ts fails when either is stale.
//   npm run design:numbers
import { writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { designNumbersSource, extractLive, extractRender, extractSpec, liveNumbersSource, readHandoff, tokenColours } from './design-extract.ts'

const WEB = resolve(import.meta.dirname, '..')
const handoff = readHandoff(resolve(WEB, '..'))
if (handoff.read === null) {
  console.error('design numbers: the reference renders are neither here nor in the main checkout (CLAUDE.md, "Web App Design")')
  process.exit(1)
}
const files = {
  'src/stage/design-numbers.ts': designNumbersSource(extractSpec(handoff.spec), extractRender(handoff.read), tokenColours(handoff.tokens)),
  'src/pages/live-numbers.ts': liveNumbersSource(extractLive(handoff.spec)),
}
for (const [file, source] of Object.entries(files)) {
  writeFileSync(resolve(WEB, file), source)
  console.log(`design numbers: wrote ${file}`)
}
