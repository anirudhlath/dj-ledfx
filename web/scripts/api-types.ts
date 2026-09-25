// Writes, or checks, web/src/api/generated/: the backend's OpenAPI schema and the TypeScript types
// openapi-typescript makes from it (spec §12, "generated OpenAPI types").
//   npm run api:types                       write both files from the backend's code
//   npm run api:check                       fail if the committed files aren't what the code makes
//   npm run api:check -- --url <server>     also fail if a running server's schema differs (GET only)
import { execFileSync } from 'node:child_process'
import { readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { parseArgs } from 'node:util'
import { describeDrift, generateTypes } from './generate-types.ts'

const WEB = resolve(import.meta.dirname, '..')
const SCHEMA = resolve(WEB, 'src/api/generated/openapi.json')
const TYPES = resolve(WEB, 'src/api/generated/schema.d.ts')

const { values } = parseArgs({
  options: { check: { type: 'boolean', default: false }, url: { type: 'string' } },
})

/** The schema the backend's code serves, as scripts/dump_openapi.py prints it. */
function backendSchema(): string {
  return execFileSync('uv', ['run', 'python', 'scripts/dump_openapi.py'], {
    cwd: resolve(WEB, '..'),
    encoding: 'utf8',
  })
}

if (!values.check && values.url === undefined) {
  const schema = backendSchema()
  writeFileSync(SCHEMA, schema)
  writeFileSync(TYPES, await generateTypes(schema))
  console.log('api types: wrote src/api/generated/openapi.json and schema.d.ts')
} else {
  const problems: string[] = []
  const committed = readFileSync(SCHEMA, 'utf8')
  if (values.check) {
    const schema = backendSchema()
    if (schema !== committed) {
      const drift = describeDrift(JSON.parse(committed), JSON.parse(schema))
      problems.push(...(drift.length > 0 ? drift : ['openapi.json is formatted differently']).map((line) => `code: ${line}`))
    }
    if (readFileSync(TYPES, 'utf8') !== (await generateTypes(committed))) {
      problems.push('schema.d.ts is not what openapi.json generates')
    }
  }
  if (values.url !== undefined) {
    const served: unknown = await (await fetch(new URL('/openapi.json', values.url))).json()
    problems.push(...describeDrift(JSON.parse(committed), served).map((line) => `${values.url}: ${line}`))
  }
  if (problems.length > 0) {
    console.error(['api types drifted:', ...problems.map((line) => `  ${line}`), 'Run: cd web && npm run api:types'].join('\n'))
    process.exit(1)
  }
  console.log('api types match')
}
