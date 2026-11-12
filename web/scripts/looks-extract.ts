// What the Looks page draws, read from the handoff rather than retyped (CLAUDE.md, "Web App Design"): the 29 look
// motifs and the library state from reference/Looks.html (motifs checked against the two PutLookOn renders that draw
// the same ones), the categories from looks.json, the `.tb` rules and `t_*` keyframes from Looks.html's <style>.
// Each failure names the render and the look. `npm run design:numbers` writes src/looks/looks-render.ts and .css.
import type { ReadText } from './design-extract.ts'

/** What a thumb's own id prefix replaces in a motif: each `LookThumb` fills it with one of its own, so two thumbs never share a gradient. */
export const MOTIF_SLOT = '@@'

export interface Motif {
  /** The inner markup of the render's `<svg class="tb ">`, its ids starting with `MOTIF_SLOT`. */
  markup: string
  /** Whether the motif follows the beat: its look's category is tempo or audio. */
  beat: boolean
}

/** The library Looks.html draws. Every id is looks.json's. */
export interface Library {
  /** Each tab's number, by its label. */
  counts: Record<string, number>
  starred: string[]
  /** The zone name a look's pill draws. */
  running: Record<string, string>
  /** Each built-in card's input names; `[]` for "No input". */
  inputs: Record<string, string[]>
  /** The saved looks, with the look each came from. */
  mine: { name: string; from: string; description: string }[]
  mineBlurb: string
  /** The card whose scrim is drawn. */
  hovered: string
}

export interface LooksRender {
  motifs: Record<string, Motif>
  categories: unknown[]
  library: Library
  css: string
}

interface LookEntry {
  id: string
  name: string
  category: string
  thumbnail: string
}

/** A card of Looks.html. */
interface Card {
  name: string
  html: string
  /** The motif's markup as drawn, ids and all. */
  raw: string
}

/** A built-in look's card. A saved look's (in the Mine section) is a plain `Card`. */
interface Built extends Card {
  look: LookEntry
}

function fail(message: string): never {
  throw new Error(`design numbers: ${message}`)
}

/** An `<svg class="tb ">`'s inner markup; nothing nests another svg in it, so the first `</svg>` ends it. */
const TB = /<svg class="tb "[^>]*>([\s\S]*?)<\/svg>/
const REFERS = /(id="|url\(#|href="#)/

/** `markup` with the prefix of each id (`lk<n>` of a built-in look's, `mn<n>` of a saved one's) replaced by the slot. */
function slotted(markup: string): string {
  return markup.replace(new RegExp(`${REFERS.source}(?:lk|mn)\\d+(?=[a-z])`, 'g'), `$1${MOTIF_SLOT}`)
}

/** Whether `markup`, once slotted, still holds an id of the render's own, or one that doesn't start with the slot. */
function leavesIds(markup: string): boolean {
  if (/\b(?:lk|mn)\d+[a-z]/.test(markup)) return true
  return [...markup.matchAll(/(?:id="|url\(#|href="#)([^")]*)/g)].some((ref) => !ref[1].startsWith(MOTIF_SLOT))
}

/** A motif's ids with their longest common prefix replaced by the slot: the renders' prefixes differ (`lk3`, `pe`, `pt0`) and the rest doesn't. */
function withoutPrefix(markup: string): string {
  const ids = [...markup.matchAll(/ id="([^"]*)"/g)].map((id) => id[1])
  if (ids.length === 0) return markup
  const prefix = ids.reduce((common, id) => {
    let end = 0
    while (end < common.length && common[end] === id[end]) end++
    return common.slice(0, end)
  })
  const escaped = prefix.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return markup.replace(new RegExp(`${REFERS.source}${escaped}`, 'g'), `$1${MOTIF_SLOT}`)
}

/** Looks.html's cards in order, each with the section it sits in deciding what it is: saved in Mine, else the look its name is in looks.json. */
function readCards(html: string, builtIn: ReadonlyMap<string, LookEntry>): { built: Built[]; saved: Card[] } {
  const built: Built[] = []
  const saved: Card[] = []
  let section = ''
  for (const m of html.matchAll(/<h2[^>]*>([^<]*)<\/h2>|<article[^>]*>[\s\S]*?<\/article>/g)) {
    if (m[1] !== undefined) {
      section = m[1]
      continue
    }
    const name = /<h3[^>]*>([^<]*)<\/h3>/.exec(m[0])?.[1] ?? fail('Looks.html has a card with no name')
    const look = section === 'Mine' ? undefined : (builtIn.get(name) ?? fail(`Looks.html's card ${name} is no look in looks.json and isn't in Mine`))
    const what = look === undefined ? `saved look ${name}` : `motif for ${look.id}`
    const raw = TB.exec(m[0])?.[1]
    if (raw === undefined || raw.includes('<svg')) fail(`Looks.html's ${what} no longer reads`)
    const card = { name, html: m[0], raw }
    if (look === undefined) saved.push(card)
    else built.push({ ...card, look })
  }
  return { built, saved }
}

/** The `.tb` rules and `@keyframes t_*` of a stylesheet, each whole, in the file's order. */
function motifRules(css: string): string[] {
  const rules: string[] = []
  let depth = 0
  let start = 0
  for (let at = 0; at < css.length; at++) {
    if (css[at] === '{') depth++
    else if (css[at] === '}' && --depth === 0) {
      rules.push(css.slice(start, at + 1).trim())
      start = at + 1
    }
  }
  return rules.filter((rule) => /^(?:\.tb(?![\w-])|@keyframes t_\w+\s*\{)/.test(rule))
}

/** The tab pills' numbers, each tab by its label. */
function readCounts(html: string): Record<string, number> {
  const tabs = [...html.matchAll(/<button type="button" aria-pressed="(?:true|false)" style="[^"]*">([^<]+)<span style="[^"]*">(\d+)<\/span><\/button>/g)]
  if (tabs.length === 0) fail("Looks.html's tab pills no longer read")
  return Object.fromEntries(tabs.map((tab) => [tab[1], Number(tab[2])]))
}

/** A built-in card's input names: the spans after its description, "No input" being none. */
function readInputs(card: Built): string[] {
  const spans = /<\/p><div style="display: flex; gap: 10px; padding-left: 2px">([\s\S]*?)<\/div><\/article>/.exec(card.html)?.[1]
  const names = [...(spans ?? '').matchAll(/<span[^>]*>([\s\S]*?)<\/span>/g)].map((span) => span[1].replace(/<svg[\s\S]*?<\/svg>/g, '').replace(/<[^>]*>/g, '').trim())
  if (names.length === 0) fail(`Looks.html's inputs for ${card.look.id} no longer read`)
  return names.length === 1 && names[0] === 'No input' ? [] : names
}

/** Each motif a PutLookOn render draws, found by the look's name beside it, must be the one Looks.html draws. */
function checkRender(render: string, html: string, motifs: ReadonlyMap<string, Built>): void {
  const title = /<span style="font-family: 'Instrument Serif'[^"]*">([^<]*)<\/span>/g
  for (const svg of html.matchAll(new RegExp(TB.source, 'g'))) {
    title.lastIndex = svg.index + svg[0].length
    const name = title.exec(html)?.[1] ?? fail(`${render}.html draws a motif with no look's name after it`)
    const card = motifs.get(name) ?? fail(`${render}.html draws a motif for ${name}, which looks.json doesn't have`)
    if (withoutPrefix(svg[1]) !== withoutPrefix(card.raw)) fail(`${render}.html draws the motif for ${card.look.id} unlike Looks.html`)
  }
}

export function extractLooksRender(read: ReadText, looksJson: string): LooksRender {
  const { categories, looks } = JSON.parse(looksJson) as { categories: unknown[]; looks: LookEntry[] }
  const html = read('reference/Looks.html')
  const byName = new Map(looks.map((look) => [look.name, look]))
  const { built, saved } = readCards(html, byName)

  // Motifs: one card for each look, its ids on the slot.
  const motifs: Record<string, Motif> = {}
  const cards = new Map<string, Built>()
  for (const card of built) {
    const { look } = card
    if (cards.has(look.name)) fail(`Looks.html draws ${look.id} twice`)
    cards.set(look.name, card)
    const markup = slotted(card.raw)
    if (leavesIds(markup)) fail(`Looks.html's motif for ${look.id} no longer reads`)
    motifs[look.thumbnail] = { markup, beat: ['tempo', 'audio'].includes(look.category) }
  }
  for (const look of looks) if (!cards.has(look.name)) fail(`Looks.html has no card for ${look.id}`)

  // Saved looks: each drawn as the look it came from.
  const mine = saved.map((card) => {
    const parentName = />From ([^<]+)<\/span>/.exec(card.html)?.[1] ?? fail(`Looks.html's saved look ${card.name} no longer says where it came from`)
    const parent = byName.get(parentName) ?? fail(`Looks.html's saved look ${card.name} comes from ${parentName}, which looks.json doesn't have`)
    if (slotted(card.raw) !== motifs[parent.thumbnail].markup) fail(`Looks.html's saved look ${card.name} is drawn unlike ${parent.id}`)
    const description = /<p style="[^"]*">([^<]+)<\/p>/.exec(card.html)?.[1] ?? fail(`Looks.html's saved look ${card.name} no longer reads its description`)
    return { name: card.name, from: parent.id, description }
  })

  // The other renders draw the same motifs.
  for (const render of ['Live-PutLookOn', 'Phone-PutLookOn']) checkRender(render, read(`reference/${render}.html`), cards)

  // The library.
  const starred: string[] = []
  const running: Record<string, string> = {}
  const inputs: Record<string, string[]> = {}
  for (const card of built) {
    const { id } = card.look
    const star = /aria-label="(?:Star|Unstar) [^"]*" aria-pressed="(true|false)"/.exec(card.html)?.[1] ?? fail(`Looks.html's star on ${id} no longer reads`)
    if (star === 'true') starred.push(id)
    const zone = /<span style="width: 6px; height: 6px;[^"]*animation: livedot[^"]*"><\/span>([^<]+)<\/span>/.exec(card.html)?.[1]
    if (zone !== undefined) running[id] = zone
    inputs[id] = readInputs(card)
  }
  const scrimmed = [...built, ...saved].filter((card) => card.html.includes('linear-gradient(to top'))
  const hovered = built.find((card) => card.html.includes('linear-gradient(to top'))
  if (scrimmed.length !== 1 || hovered === undefined) fail(`Looks.html's hovered card no longer reads: ${scrimmed.length} draw a scrim`)
  const mineBlurb = /<h2[^>]*>Mine<\/h2><span[^>]*>([^<]+)<\/span>/.exec(html)?.[1] ?? fail("Looks.html's Mine header no longer reads")

  const style = /<style>([\s\S]*?)<\/style>/.exec(html)?.[1] ?? ''
  const rules = motifRules(style)
  if (rules.length === 0) fail("Looks.html's .tb rules and t_* keyframes no longer read")

  return {
    motifs,
    categories,
    library: { counts: readCounts(html), starred, running, inputs, mine, mineBlurb, hovered: hovered.look.id },
    css: rules.join('\n'),
  }
}

const HEADER = `Generated by \`npm run design:numbers\` (web/scripts/design-numbers.ts) from the pinned Looks.html (the motifs, the library and
the .tb rules and keyframes, the motifs checked against Live-PutLookOn.html and Phone-PutLookOn.html) and looks.json (the
categories). Don't edit it: after a new handoff, run the command again.`

/** src/looks/looks-render.ts: no imports, so the first load takes only what LookThumb and the library draw from. */
export function looksRenderSource(render: LooksRender): string {
  const lines = HEADER.split('\n').map((line) => `// ${line}`)
  return `${lines.join('\n')}
// Each motif's ids start with MOTIF_SLOT, which a thumb replaces with a prefix of its own.
export const MOTIF_SLOT = ${JSON.stringify(MOTIF_SLOT)}

/** The inner markup of each look's \`<svg class="tb ">\`, by its looks.json \`thumbnail\`. */
export const MOTIFS: Readonly<Record<string, { readonly markup: string; readonly beat: boolean }>> = ${JSON.stringify(render.motifs, null, 2)}

export const LOOK_CATEGORIES = ${JSON.stringify(render.categories, null, 2)} as const

/** What Looks.html draws of the library: ids are looks.json's, tabs are by label. */
interface Library {
  readonly counts: Readonly<Record<string, number>>
  readonly starred: readonly string[]
  readonly running: Readonly<Record<string, string>>
  readonly inputs: Readonly<Record<string, readonly string[]>>
  readonly mine: readonly { readonly name: string; readonly from: string; readonly description: string }[]
  readonly mineBlurb: string
  readonly hovered: string
}

export const LIBRARY: Library = ${JSON.stringify(render.library, null, 2)}
`
}

/** src/looks/looks-render.css. */
export function looksRenderCss(render: LooksRender): string {
  return `/*\n${HEADER.split('\n').map((line) => ` * ${line}`).join('\n')}\n */\n${render.css}\n`
}
