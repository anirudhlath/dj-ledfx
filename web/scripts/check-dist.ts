// Fails when MSW reached a build (decision 11). `npm run build` runs it over web/dist; pass another
// directory to check that one.
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, resolve } from 'node:path'

const MARKERS = ['mockServiceWorker', '[MSW]']
const dir = resolve(import.meta.dirname, '..', process.argv[2] ?? 'dist')

function files(path: string): string[] {
  return readdirSync(path).flatMap((name) => {
    const full = join(path, name)
    return statSync(full).isDirectory() ? files(full) : [full]
  })
}

const found = files(dir).flatMap((file) => {
  const text = readFileSync(file, 'utf8')
  return MARKERS.filter((marker) => file.includes(marker) || text.includes(marker)).map((marker) => `${file}: ${marker}`)
})

if (found.length > 0) {
  console.error(`MSW reached ${dir}:\n${found.join('\n')}`)
  process.exit(1)
}
console.log(`${dir}: no MSW`)
