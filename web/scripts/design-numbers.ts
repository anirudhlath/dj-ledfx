// Writes src/stage/design-numbers.ts, the numbers and the colours the stage draws with, and
// src/design/live-numbers.ts, the numbers everything outside the stage draws with, read from the handoff by
// scripts/design-extract.ts; and src/looks/looks-render.ts and looks-render.css, the look motifs and the library
// Looks.html draws, read by scripts/looks-extract.ts. src/stage/design-numbers.node.test.ts and
// src/looks/looks-render.node.test.ts fail when any of them is stale.
//   npm run design:numbers
import { writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import {
  designNumbersSource, extractLive, extractLiveRender, extractRender, extractSpec, liveNumbersSource, readHandoff, tokenColours,
} from './design-extract.ts'
import { extractLooksRender, looksRenderCss, looksRenderSource } from './looks-extract.ts'

const WEB = resolve(import.meta.dirname, '..')
const handoff = readHandoff(resolve(WEB, '..'))
if (handoff.read === null) {
  console.error('design numbers: the reference renders are neither here nor in the main checkout (CLAUDE.md, "Web App Design")')
  process.exit(1)
}
const looks = extractLooksRender(handoff.read, handoff.looks)
const files = {
  'src/stage/design-numbers.ts': designNumbersSource(extractSpec(handoff.spec), extractRender(handoff.read), tokenColours(handoff.tokens)),
  'src/design/live-numbers.ts': liveNumbersSource(extractLive(handoff.spec), extractLiveRender(handoff.read)),
  'src/looks/looks-render.ts': looksRenderSource(looks),
  'src/looks/looks-render.css': looksRenderCss(looks),
}
for (const [file, source] of Object.entries(files)) {
  writeFileSync(resolve(WEB, file), source)
  console.log(`design numbers: wrote ${file}`)
}
