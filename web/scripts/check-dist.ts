// Fails a build that the mocks reached (decision 11): MSW, the mock fixtures or home.json. Or one
// whose JavaScript passes §14 Performance's budget: "first load < 400 KB gzipped JS excluding
// three.js". It sums every JS file, the lazy chunks too, so it's stricter than a first load. F2
// excludes three.js's chunk when it adds it. `npm run build` runs this over web/dist; pass another
// directory to check that one.
import { readdirSync, readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { gzipSync } from 'node:zlib'

// Strings only these carry: MSW's worker and log prefix; the fixtures' documentation-range
// addresses (RFC 5737); home.json's own `ledsEstimated`, which no API type has.
const MARKERS: Record<string, string[]> = {
  MSW: ['mockServiceWorker', '[MSW]'],
  'the mock fixtures': ['192.0.2.'],
  'home.json': ['ledsEstimated'],
}
const BUDGET_KB = 400
const dir = resolve(import.meta.dirname, '..', process.argv[2] ?? 'dist')

const all = readdirSync(dir, { recursive: true, withFileTypes: true })
  .filter((entry) => entry.isFile())
  .map((entry) => join(entry.parentPath, entry.name))
const found = all.flatMap((file) => {
  const text = readFileSync(file, 'utf8')
  return Object.entries(MARKERS).flatMap(([what, markers]) =>
    markers.filter((marker) => file.includes(marker) || text.includes(marker)).map((marker) => `${file}: ${what} (${marker})`),
  )
})
if (found.length > 0) {
  console.error(`The mocks reached ${dir}:\n${found.join('\n')}`)
  process.exit(1)
}

const kb = all.filter((file) => file.endsWith('.js')).reduce((sum, file) => sum + gzipSync(readFileSync(file)).length, 0) / 1024
if (kb >= BUDGET_KB) {
  console.error(`${dir}: ${kb.toFixed(1)} KB of gzipped JS, over the ${BUDGET_KB} KB budget (§14)`)
  process.exit(1)
}
console.log(`${dir}: no mocks, ${kb.toFixed(1)} KB of gzipped JS`)
