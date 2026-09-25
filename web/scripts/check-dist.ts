// Fails a build that MSW reached (decision 11), or whose JavaScript passes §14 Performance's budget:
// "first load < 400 KB gzipped JS excluding three.js". It sums every JS file, the lazy chunks too,
// so it's stricter than a first load. F2 excludes three.js's chunk when it adds it. `npm run build`
// runs this over web/dist; pass another directory to check that one.
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { gzipSync } from 'node:zlib'

const MARKERS = ['mockServiceWorker', '[MSW]']
const BUDGET_KB = 400
const dir = resolve(import.meta.dirname, '..', process.argv[2] ?? 'dist')

function files(path: string): string[] {
  return readdirSync(path).flatMap((name) => {
    const full = join(path, name)
    return statSync(full).isDirectory() ? files(full) : [full]
  })
}

const all = files(dir)
const found = all.flatMap((file) => {
  const text = readFileSync(file, 'utf8')
  return MARKERS.filter((marker) => file.includes(marker) || text.includes(marker)).map((marker) => `${file}: ${marker}`)
})
if (found.length > 0) {
  console.error(`MSW reached ${dir}:\n${found.join('\n')}`)
  process.exit(1)
}

const kb = all.filter((file) => file.endsWith('.js')).reduce((sum, file) => sum + gzipSync(readFileSync(file)).length, 0) / 1024
if (kb >= BUDGET_KB) {
  console.error(`${dir}: ${kb.toFixed(1)} KB of gzipped JS, over the ${BUDGET_KB} KB budget (§14)`)
  process.exit(1)
}
console.log(`${dir}: no MSW, ${kb.toFixed(1)} KB of gzipped JS`)
