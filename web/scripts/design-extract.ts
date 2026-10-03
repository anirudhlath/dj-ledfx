// The numbers the stage draws with, read from the handoff rather than retyped (CLAUDE.md, "Web App
// Design"): SPEC from the web app spec's own sentences, RENDER from the reference renders' markup,
// TOKENS from tokens.css. Each entry names where its number lives. A sentence or an element that
// moved fails loudly here, naming the entry; `npm run design:numbers` writes
// src/stage/design-numbers.ts and src/design/live-numbers.ts from these.
import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'

/** Reads one file of docs/design/web-app by its name there: tokens.css, or a render ("reference/Main.html"). */
export type ReadText = (name: string) => string

interface Entry {
  /** Where the number lives, for the error when it can't be found. */
  where: string
  pattern: RegExp
  take: (m: RegExpExecArray) => unknown
}

const n = (value: string) => Number(value)
const pct = (value: string) => Number(value) / 100

/** Every match of `pattern` in `text`; at least one. */
function matches(text: string, entry: Pick<Entry, 'where' | 'pattern'>): RegExpExecArray[] {
  const flags = entry.pattern.flags.includes('g') ? entry.pattern.flags : `${entry.pattern.flags}g`
  const found = [...text.matchAll(new RegExp(entry.pattern.source, flags))]
  if (found.length === 0) throw new Error(`design numbers: ${entry.where} no longer reads ${entry.pattern}`)
  return found
}

/**
 * The first match; every other match must capture the same values (one look, drawn many times).
 * `compared` names the groups that must agree, when others hold a position.
 */
function same(text: string, entry: Pick<Entry, 'where' | 'pattern'>, compared?: number[]): RegExpExecArray {
  const [first, ...rest] = matches(text, entry)
  const key = (m: RegExpExecArray) => JSON.stringify(compared === undefined ? m.slice(1) : compared.map((group) => m[group]))
  const odd = rest.find((m) => key(m) !== key(first))
  if (odd !== undefined) throw new Error(`design numbers: ${entry.where} draws it two ways: ${key(first)} and ${key(odd)}`)
  return first
}

// ── SPEC: the web app spec's sentences ──────────────────────────────────────────────────────

const SPEC_ENTRIES: Record<string, Entry> = {
  floorEdgePx: { where: '§7.1 Floors', pattern: /`stage-floor` with a ([\d.]+) px `stage-floor-edge` outline/, take: (m) => n(m[1]) },
  balconyHatchDeg: { where: '§7.1 Balcony', pattern: /\*\*Balcony\*\* \(off the sunroom\): ([\d.]+)° hatch/, take: (m) => n(m[1]) },
  window: {
    where: '§7.1 Windows',
    pattern: /wall below ([\d.]+) m, then a glass pane \(text at ([\d.]+)%\) to the cut height with a ([\d.]+) px top edge \(text at ([\d.]+)%\)/,
    take: (m) => ({ sillM: n(m[1]), glassAlpha: pct(m[2]), edgePx: n(m[3]), edgeAlpha: pct(m[4]) }),
  },
  glassDoorSillM: { where: '§7.1 Glass door', pattern: /same as a window with a ([\d.]+) m sill/, take: (m) => n(m[1]) },
  columnAboveCutM: { where: '§7.1 Columns', pattern: /at cut height \+ ([\d.]+)/, take: (m) => n(m[1]) },
  ghostAlpha: { where: '§7.1 Ghost volume', pattern: /as a faint line \(text at ([\d.]+)%\)/, take: (m) => pct(m[1]) },
  camera: {
    where: '§7.2',
    pattern: /\*\*Turned ([\d.]+)° clockwise from north-up, tilted ([\d.]+)° above the horizon\*\*/,
    take: (m) => ({ turnDeg: n(m[1]), tiltDeg: n(m[2]) }),
  },
  fit: {
    where: '§7.2 fit',
    pattern: /Fit the whole outline plus ([\d.]+) m of height with ([\d.]+) px side padding, ([\d.]+) px top and ([\d.]+) px bottom on desktop Live/,
    take: (m) => ({ heightM: n(m[1]), sidePx: n(m[2]), topPx: n(m[3]), bottomPx: n(m[4]) }),
  },
  rotate: {
    where: '§7.2 view controls',
    pattern: /orbit ±([\d.]+)° around the vertical in ([\d.]+)° steps/,
    take: (m) => ({ maxDeg: n(m[1]), stepDeg: n(m[2]) }),
  },
  samples: {
    where: '§7.3 sample points',
    pattern: /point \((\d+)\), cylinder \((\d+) up the height when taller than ([\d.]+) m, else (\d+)\), line \((\d+)\), bent line \((\d+) along the path\), grid \((\d+) across\)/,
    take: (m) => ({
      point: n(m[1]),
      cylinderTall: n(m[2]),
      cylinderTallerThanM: n(m[3]),
      cylinderShort: n(m[4]),
      line: n(m[5]),
      bentLine: n(m[6]),
      grid: n(m[7]),
    }),
  },
  core: {
    where: '§7.3 Core',
    pattern: /\*\*Core:\*\* ([\d.]+) px dot \(screen space, `sizeAttenuation: false`\), colour lifted toward white by `([\d.]+) \+ ([\d.]+)·intensity`\. A dark light shows a ([\d.]+) px `stage-light-off` dot/,
    take: (m) => ({ px: n(m[1]), liftBase: n(m[2]), liftPerIntensity: n(m[3]), darkPx: n(m[4]) }),
  },
  halo: {
    where: '§7.3 Halo',
    pattern: /radius `([\d.]+) px · \(([\d.]+) \+ ([\d.]+)·intensity\)` for single-point lights, `([\d.]+) px · \(…\)` for strip samples; radial falloff: ([\d.]+)%·i at the centre, ([\d.]+)%·i at ([\d.]+)% radius, 0 at the edge/,
    take: (m) => ({
      pointPx: n(m[1]),
      base: n(m[2]),
      perIntensity: n(m[3]),
      stripPx: n(m[4]),
      falloff: { centre: pct(m[5]), mid: pct(m[6]), midAt: pct(m[7]) },
    }),
  },
  pool: {
    where: '§7.3 Floor pool',
    pattern: /radius in metres `\(([\d.]+) \+ ([\d.]+)·z\) · \(([\d.]+) \+ ([\d.]+)·intensity\)` \(×([\d.]+) for multi-sample lights\)\. Falloff ([\d.]+)%·i centre, ([\d.]+)%·i at ([\d.]+)%, 0 at the edge/,
    take: (m) => ({
      baseM: n(m[1]),
      perZ: n(m[2]),
      intensityBase: n(m[3]),
      perIntensity: n(m[4]),
      multiSample: n(m[5]),
      falloff: { centre: pct(m[6]), mid: pct(m[7]), midAt: pct(m[8]) },
    }),
  },
  stripPx: { where: '§7.3 Strips', pattern: /as a ([\d.]+)–([\d.]+) px line in the segment's colour/, take: (m) => ({ min: n(m[1]), max: n(m[2]) }) },
  dropLine: {
    where: '§7.3 Height cue',
    pattern: /a dashed drop line \(([\d.]+)\/([\d.]+), text at ([\d.]+)%\)/,
    take: (m) => ({ dashPx: n(m[1]), gapPx: n(m[2]), alpha: pct(m[3]) }),
  },
  frozen: { where: '§7.6 frozen', pattern: /Last frame, grayscale ([\d.]+)%, brightness ([\d.]+)%/, take: (m) => ({ grayscale: pct(m[1]), brightness: pct(m[2]) }) },
  dprCap: { where: '§7.5', pattern: /cap DPR at ([\d.]+)/, take: (m) => n(m[1]) },
  phoneFps: { where: '§7.5', pattern: /drop to ([\d.]+) fps on phone/, take: (m) => n(m[1]) },
  target: {
    where: '§7.5',
    pattern: /Target ([\d.]+) fps with all ([\d.]+) LEDs and ([\d.]+) pools/,
    take: (m) => ({ fps: n(m[1]), leds: n(m[2]), pools: n(m[3]) }),
  },
  label: {
    where: '§5.2',
    pattern: /room labels are ([\d.]+) px sans caps with the running look beneath in ([\d.]+) px serif italic/,
    take: (m) => ({ capsPx: n(m[1]), lookPx: n(m[2]) }),
  },
  focus: {
    where: '§7.2 Focus framing',
    pattern: /Focus framing \(zone detail, editor preview, composer on phone\): fit the zone's polygon, tilt ([\d.]+)°/,
    take: (m) => ({ tiltDeg: n(m[1]) }),
  },
  compose: {
    where: '§7.6 compose',
    pattern: /Rooms outside the chosen zone dimmed to ([\d.]+)%; chosen zone outlined in ([\d.]+) px `text`/,
    take: (m) => ({ dimmed: pct(m[1]), outlinePx: n(m[2]) }),
  },
  quality: {
    where: '§14 Performance',
    pattern: /stage ≥ (\d+) fps p95 with \d+ LEDs streaming at \d+ fps on desktop, ≥ (\d+) fps on a recent phone; main thread idle ≥ (\d+)% on Live/,
    take: (m) => ({ desktopFps: n(m[1]), phoneFps: n(m[2]), idle: pct(m[3]) }),
  },
}

/** The numbers everything outside the stage draws with: the first load carries these, and not the stage's. */
const LIVE_ENTRIES: Record<string, Entry> = {
  widePx: { where: '§4.4', pattern: /\| ≥ (\d+) px \| Desktop \(designed at/, take: (m) => n(m[1]) },
  phoneStage: { where: '§8.10 Live', pattern: /stage (\d+) × (\d+) \(no labels\)/, take: (m) => ({ width: n(m[1]), height: n(m[2]) }) },
  swatch: {
    where: '§6.6',
    pattern:
      /(\d+) px circle \((\d+) phone, (\d+) devices table\)\.\n- Live: fill = the light's colour mixed from `(#[0-9a-f]{6})` toward the colour by `([\d.]+) \+ intensity` \(clamped\), with a glow `0 0 (\d+)px` of the colour scaled by intensity; intensity ≤ ([\d.]+) shows `(#[0-9a-f]{6})` \(dark\)\.\n- Multizone or matrix: a ([\d.]+)× wide pill with a left-to-right gradient of its zones\.\n- Running its own effect: ([\d.]+) px dotted `text-2` outline, ([\d.]+) px offset\.\n- Streamed copy: ([\d.]+) px dashed `text-3` outline, ([\d.]+) px offset\.\n- Offline: hollow, ([\d.]+) px dashed signal border\.\n- Switched off elsewhere: hollow, ([\d.]+) px `text-3` border with a diagonal slash/,
    take: (m) => ({
      px: n(m[1]),
      phonePx: n(m[2]),
      tablePx: n(m[3]),
      fromColour: m[4],
      mixBase: n(m[5]),
      glowPx: n(m[6]),
      darkAt: n(m[7]),
      darkColour: m[8],
      pillRatio: n(m[9]),
      ownEffectPx: n(m[10]),
      ownEffectOffsetPx: n(m[11]),
      streamedPx: n(m[12]),
      streamedOffsetPx: n(m[13]),
      offlinePx: n(m[14]),
      switchedOffPx: n(m[15]),
    }),
  },
  reducedMotionMs: {
    where: '§5.4',
    pattern: /The stage still updates light colours, at most once per (second|minute)/,
    take: (m) => (m[1] === 'second' ? 1000 : 60_000),
  },
  tape: {
    where: '§5.6',
    pattern:
      /the whole app window gets a (\d+) px \(phone (\d+) px\) tape frame on all four edges, the top-bar switch track turns to tape, the Running panel header gets a (\d+) px tape bar/,
    take: (m) => ({ framePx: n(m[1]), phoneFramePx: n(m[2]), panelBarPx: n(m[3]) }),
  },
  frozenCardsOpacity: { where: '§9.4 Reconnecting', pattern: /cards at (\d+)% opacity and inert/, take: (m) => pct(m[1]) },
  attentionPopoverPx: {
    where: '§6.2 AttentionButton',
    pattern: /`AttentionPopover` \(desktop, (\d+) px, anchored under the button\)/,
    take: (m) => n(m[1]),
  },
}

/** Each entry's number, from the spec's text. Each sentence must say it once. */
function extract(spec: string, entries: Record<string, Entry>): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(entries).map(([key, entry]) => {
      const found = matches(spec, entry)
      if (found.length > 1) throw new Error(`design numbers: ${entry.where} says it ${found.length} times; make ${entry.pattern} name one`)
      return [key, entry.take(found[0])]
    }),
  )
}

/** SPEC: the stage's numbers, from the spec's text. */
export const extractSpec = (spec: string): Record<string, unknown> => extract(spec, SPEC_ENTRIES)

/** LIVE_SPEC: the numbers outside the stage, from the spec's text. */
export const extractLive = (spec: string): Record<string, unknown> => extract(spec, LIVE_ENTRIES)

// ── RENDER: the reference renders' markup ───────────────────────────────────────────────────

/** The render's stage: its largest <svg>, with its size. */
function stage(html: string, where: string): { width: number; height: number; body: string } {
  let best: { width: number; height: number; body: string } | null = null
  for (const m of html.matchAll(/<svg xmlns="http:\/\/www\.w3\.org\/2000\/svg" width="(\d+)" height="(\d+)"[^>]*>([\s\S]*?)<\/svg>/g)) {
    const [width, height] = [n(m[1]), n(m[2])]
    if (best === null || width * height > best.width * best.height) best = { width, height, body: m[3] }
  }
  if (best === null) throw new Error(`design numbers: ${where} has no stage <svg>`)
  return best
}

/** TOKENS: tokens.css's colours, each `--color-*` custom property's hex, in the file's order. */
export function tokenColours(tokens: string): Record<string, string> {
  return Object.fromEntries([...tokens.matchAll(/(--color-[\w-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)].map((m) => [m[1], m[2]]))
}

/** A render's colour as the stage names it: tokens.css's custom property when one has it, else the hex. */
function colour(tokens: string, hex: string): string {
  const named = Object.entries(tokenColours(tokens)).find(([, value]) => value.toLowerCase() === hex.toLowerCase())
  return named?.[0] ?? hex.toLowerCase()
}

/** An `rgba(r,g,b,a)` the render wrote as four groups from `at`: its colour (as colour() names it) and alpha. */
function rgba(tokens: string, m: RegExpExecArray, at: number): { colour: string; alpha: number } {
  const hex = `#${[0, 1, 2].map((i) => n(m[at + i]).toString(16).padStart(2, '0')).join('')}`
  return { colour: colour(tokens, hex), alpha: n(m[at + 3]) }
}

/** A font size: tokens.css's `--text-*` property when one is that size, else the px. */
function font(tokens: string, px: string): string | number {
  for (const m of tokens.matchAll(/(--text-[\w-]+):\s*([\d.]+)px\s*;/g)) if (n(m[2]) === n(px)) return m[1]
  return n(px)
}

const luminance = (hex: string) => [1, 3, 5].reduce((sum, at) => sum + parseInt(hex.slice(at, at + 2), 16), 0)

/** The renders RENDER reads. */
const RENDERS = ['reference/Main.html', 'reference/State-Firmware.html']
/** The renders LIVE_RENDER reads. */
const LIVE_RENDERS = ['reference/Main.html', 'reference/State-Sheet.html']

/** Fails unless each named file of docs/design/web-app is the one HANDOFF.sha256 (`pins`) pins. */
export function checkPins(pins: string, names: readonly string[], readBytes: (name: string) => Uint8Array): void {
  for (const name of names) {
    const hash = createHash('sha256').update(readBytes(name)).digest('hex')
    if (!pins.includes(`${hash}  ${name}\n`)) throw new Error(`${name} isn't the file HANDOFF.sha256 pins`)
  }
}

const RGBA = String.raw`rgba\((\d+),(\d+),(\d+),([\d.]+)\)`
const re = (source: string) => new RegExp(source)

/** RENDER: what the stage takes from the renders, where neither the spec nor tokens.css says it. */
export function extractRender(read: ReadText): Record<string, unknown> {
  const tokens = read('tokens.css')
  const mainHtml = read('reference/Main.html')
  const mainStage = stage(mainHtml, 'Main.html')
  const main = mainStage.body
  const firmware = stage(read('reference/State-Firmware.html'), 'State-Firmware.html').body

  const drop = same(main, {
    where: 'Main.html, a drop line and its floor tick',
    pattern: re(String.raw`<path d="M[\d. ]+L[\d. ]+" stroke="rgba\([\d,.]+\)" stroke-width="([\d.]+)" stroke-dasharray="[\d. ]+"></path><ellipse cx="[\d.]+" cy="[\d.]+" rx="([\d.]+)" ry="[\d.]+" fill="${RGBA}"></ellipse>`),
  })
  const off = same(main, {
    where: 'Main.html, the switched-off ring and its slash',
    pattern: re(String.raw`<circle cx="([\d.]+)" cy="[\d.]+" r="([\d.]+)" fill="(#[0-9a-f]{6})" stroke="${RGBA}" stroke-width="([\d.]+)" stroke-dasharray="none"></circle><path d="M([\d.]+) [\d.]+ L[\d.]+ [\d.]+"`),
  }, [2, 3, 4, 5, 6, 7, 8])
  const offline = same(main, {
    where: 'Main.html, the offline strip',
    pattern: re(String.raw`stroke="${RGBA}" stroke-width="([\d.]+)" stroke-dasharray="([\d.]+) ([\d.]+)" stroke-linecap="round"`),
  })
  const ghost = same(main, {
    where: "Main.html, the ghost volume's vertical lines",
    pattern: re(String.raw`<path d="M([\d.]+) [\d.]+ L\1 [\d.]+" stroke="rgba\([\d,.]+\)" stroke-width="([\d.]+)" fill="none"></path>`),
  }, [2])
  const furniture = same(main, {
    where: "Main.html, a furniture block's two sides and its top",
    pattern: re(String.raw`<path d="M[^"]+Z" fill="(#[0-9a-f]{6})"></path><path d="M[^"]+Z" fill="(#[0-9a-f]{6})"></path><path d="M[^"]+Z" fill="#[0-9a-f]{6}" stroke="${RGBA}" stroke-width="([\d.]+)"></path>`),
  })
  const sun = same(main, {
    where: "Main.html, the sun's path, glow, disc and label",
    pattern: re(String.raw`<path d="M[\d. L]+" stroke="${RGBA}" stroke-width="([\d.]+)" stroke-dasharray="([\d.]+) ([\d.]+)" fill="none"></path><circle cx="[\d.]+" cy="([\d.]+)" r="([\d.]+)" fill="url\(#([\w-]+)\)"[^>]*></circle><circle cx="[\d.]+" cy="[\d.]+" r="([\d.]+)" fill="(#[0-9a-f]{6})"></circle><text x="[\d.]+" y="([\d.]+)" text-anchor="middle" style="font:(\d+) ([\d.]+)px[^"]*" fill="(#[0-9a-f]{6})">SUN `),
  })
  const gradient = same(mainHtml, {
    where: `Main.html, the sun glow's gradient #${sun[10]}`,
    pattern: re(String.raw`<radialGradient id="${sun[10]}">([\s\S]*?)</radialGradient>`),
  })[1]
  const stops = matches(gradient, {
    where: "Main.html, the sun glow's stops",
    pattern: /<stop offset="([\d.]+)" stop-color="(#[0-9a-f]{6})" stop-opacity="([\d.]+)"><\/stop>/,
  })
  const label = same(main, {
    where: "Main.html, the first room label's two lines, after the sun's",
    pattern: />SUN [^<]*<\/text><text x="[\d.]+" y="([\d.]+)"[^>]*>[^<]*<\/text><text x="[\d.]+" y="([\d.]+)"/,
  })
  const page = (where: string, pattern: RegExp) => same(mainHtml, { where, pattern })
  const dots = page(
    "Main.html, the courtyard's dot pattern",
    /<pattern id="([\w-]+)" width="(\d+)" height="\d+" patternUnits="userSpaceOnUse"><circle cx="[\d.]+" cy="[\d.]+" r="([\d.]+)" fill="(#[0-9a-f]{6})"><\/circle><\/pattern>/,
  )
  const dotsFill = page("Main.html, the courtyard's dotted fill", re(String.raw`fill="url\(#${dots[1]}\)" opacity="([\d.]+)"`))
  const hatch = page(
    "Main.html, the balcony's hatch pattern",
    /<pattern id="[\w-]+" width="(\d+)" height="\d+" patternUnits="userSpaceOnUse" patternTransform="rotate\([\d.]+\)"><line x1="0" y1="0" x2="0" y2="\d+" stroke="(#[0-9a-f]{6})" stroke-width="([\d.]+)"><\/line><\/pattern>/,
  )
  const legend = page(
    'Main.html, the light-state legend',
    re(String.raw`<div style="position: absolute; left: (\d+)px; bottom: (\d+)px"><div style="display: flex; align-items: center; gap: (\d+)px; font-size: ([\d.]+)px; color: (#[0-9a-f]{6}); "><span style="display: inline-flex; align-items: center; gap: (\d+)px"><span style="width: (\d+)px; height: \d+px; border-radius: 50%; background: (#[0-9a-f]{6}); box-shadow: 0 0 (\d+)px rgba\([\d,]+,([\d.]+)\)"></span>Live colour</span><span style="display: inline-flex; align-items: center; gap: \d+px"><span style="width: \d+px; height: \d+px; border-radius: 50%; background: (#[0-9a-f]{6});`),
  )
  const controls = page(
    'Main.html, the view controls',
    /<div style="position: absolute; right: (\d+)px; bottom: (\d+)px; display: flex; gap: (\d+)px"><button type="button" aria-label="Rotate view"/,
  )
  const tools = page(
    "Main.html, the stage's tools (3D | Plan and the switches)",
    /<div style="position: absolute; left: (\d+)px; top: (\d+)px; display: flex; align-items: center; gap: (\d+)px"><div style="display: inline-flex; gap: \d+px; padding: \d+px;/,
  )
  const readout = page(
    'Main.html, the sun readout',
    /<div style="position: absolute; right: (\d+)px; top: (\d+)px; display: flex; align-items: center; gap: (\d+)px; font-size: ([\d.]+)px; color: (#[0-9a-f]{6})"><svg width="(\d+)" height="\d+" viewBox="0 0 24 24" fill="none" stroke="(#[0-9a-f]{6})"/,
  )
  const tip = page(
    'Main.html, the tooltip',
    /<div role="tooltip" style="position: absolute; left: (\d+)px; top: (\d+)px; width: (\d+)px;[^"]*"><div style="display: flex; align-items: center; gap: (\d+)px"><span[^>]*style="display: inline-block; width: (\d+)px; height: \d+px; border-radius: 50%; background: #[0-9a-f]{6}; box-shadow: 0 0 (\d+)px/,
  )
  const leader = page(
    "Main.html, the tooltip's leader line",
    /<div aria-hidden="true" style="position: absolute; left: ([\d.]+)px; top: ([\d.]+)px; width: ([\d.]+)px; height: ([\d.]+)px; background: (#[0-9a-f]{6}); transform-origin: 0 0; transform: rotate\((-?[\d.]+)deg\)"/,
  )
  const ring = same(firmware, {
    where: 'State-Firmware.html, the own-effect ring',
    pattern: re(String.raw`<circle cx="[\d.]+" cy="[\d.]+" r="([\d.]+)" fill="none" stroke="${RGBA}" stroke-width="([\d.]+)" stroke-dasharray="([\d.]+) ([\d.]+)">`),
  })
  const waves = same(firmware, {
    where: "State-Firmware.html, the streamed copy's wave marks beside its light's last sample",
    pattern: re(String.raw`<path d="M[\d.]+ [\d.]+ L([\d.]+) ([\d.]+)"[^>]*></path><path d="M([\d.]+) ([\d.]+) q([\d.]+) (-?[\d.]+) ([\d.]+) 0 t([\d.]+) 0 M[\d.]+ ([\d.]+) q[^"]*" stroke="${RGBA}" stroke-width="([\d.]+)"`),
  })

  // The strips' segments are drawn in their colour; the dark ones in a token (§7.3: "visible even when dark").
  const strokes = matches(main, {
    where: "Main.html, the strips' segments",
    pattern: /<path d="M[\d. ]+L[\d. ]+" stroke="(#[0-9a-f]{6})" stroke-width="[\d.]+" stroke-linecap="round">/,
  })
  const dark = [...new Set(strokes.map((m) => colour(tokens, m[1])).filter((name) => name.startsWith('--')))]
  if (dark.length !== 1) throw new Error(`design numbers: Main.html's dark strip segments name ${dark.length} tokens, not one`)

  const [faceA, faceB] = [furniture[1], furniture[2]]
  const facing = luminance(faceA) >= luminance(faceB) ? faceA : faceB
  return {
    stage: { widthPx: mainStage.width, heightPx: mainStage.height },
    dropLine: { widthPx: n(drop[1]) },
    floorTick: { radiusPx: n(drop[2]), ...rgba(tokens, drop, 3) },
    switchedOff: { ringPx: n(off[2]), fill: colour(tokens, off[3]), ...rgba(tokens, off, 4), widthPx: n(off[8]), slashHalfPx: n(off[1]) - n(off[9]) },
    offlineStrip: { ...rgba(tokens, offline, 1), widthPx: n(offline[5]), dashPx: n(offline[6]), gapPx: n(offline[7]) },
    ghost: { widthPx: n(ghost[2]) },
    strip: { darkColour: dark[0] },
    furniture: {
      sideFacing: colour(tokens, facing),
      sideOther: colour(tokens, facing === faceA ? faceB : faceA),
      edge: { ...rgba(tokens, furniture, 3), widthPx: n(furniture[7]) },
    },
    sun: {
      path: { ...rgba(tokens, sun, 1), widthPx: n(sun[5]), dashPx: n(sun[6]), gapPx: n(sun[7]) },
      glow: {
        radiusPx: n(sun[9]),
        colour: colour(tokens, stops[0][2]),
        stops: stops.map((stop) => ({ at: n(stop[1]), alpha: n(stop[3]) })),
      },
      disc: { radiusPx: n(sun[11]), colour: colour(tokens, sun[12]) },
      label: { dyPx: n(sun[13]) - n(sun[8]), weight: n(sun[14]), font: font(tokens, sun[15]), colour: colour(tokens, sun[16]) },
    },
    label: { lineGapPx: n(label[2]) - n(label[1]) },
    courtyard: { dotSpacingPx: n(dots[2]), dotRadiusPx: n(dots[3]), dotColour: colour(tokens, dots[4]), opacity: n(dotsFill[1]) },
    balcony: { hatchSpacingPx: n(hatch[1]), hatchColour: colour(tokens, hatch[2]), hatchWidthPx: n(hatch[3]) },
    legend: {
      leftPx: n(legend[1]),
      bottomPx: n(legend[2]),
      gapPx: n(legend[3]),
      font: font(tokens, legend[4]),
      colour: colour(tokens, legend[5]),
      itemGapPx: n(legend[6]),
      dotPx: n(legend[7]),
      liveSample: colour(tokens, legend[8]),
      glowPx: n(legend[9]),
      glowAlpha: n(legend[10]),
      ownEffectSample: colour(tokens, legend[11]),
    },
    controls: { rightPx: n(controls[1]), bottomPx: n(controls[2]), gapPx: n(controls[3]) },
    tools: { leftPx: n(tools[1]), topPx: n(tools[2]), gapPx: n(tools[3]) },
    readout: {
      rightPx: n(readout[1]),
      topPx: n(readout[2]),
      gapPx: n(readout[3]),
      font: font(tokens, readout[4]),
      colour: colour(tokens, readout[5]),
      iconPx: n(readout[6]),
      iconColour: colour(tokens, readout[7]),
    },
    tooltip: {
      dxPx: n(tip[1]) - n(leader[1]),
      dyPx: n(tip[2]) - n(leader[2]),
      widthPx: n(tip[3]),
      nameGapPx: n(tip[4]),
      swatchPx: n(tip[5]),
      swatchGlowPx: n(tip[6]),
      leader: { lengthPx: n(leader[3]), widthPx: n(leader[4]), colour: colour(tokens, leader[5]), angleDeg: n(leader[6]) },
    },
    ownEffect: { ringPx: n(ring[1]), ...rgba(tokens, ring, 2), widthPx: n(ring[6]), dashPx: n(ring[7]), gapPx: n(ring[8]) },
    streamedCopy: {
      dxPx: n(waves[3]) - n(waves[1]),
      dyPx: n(waves[4]) - n(waves[2]),
      risePx: -n(waves[6]),
      halfPx: n(waves[7]),
      rowGapPx: n(waves[9]) - n(waves[4]),
      ...rgba(tokens, waves, 10),
      widthPx: n(waves[14]),
    },
  }
}

/**
 * LIVE_RENDER: what everything outside the stage takes from the renders. The pips' curve, from Main.html's
 * `@keyframes pip`, is turned from a cycle's percentages into beats: the four pips share one animation,
 * each a beat behind the last, so a cycle is as many beats as the delays' step goes into it. An overlay's
 * gold is State-Sheet.html's: tokens.css has no colour for it.
 */
export function extractLiveRender(read: ReadText): Record<string, unknown> {
  const tokens = read('tokens.css')
  const main = read('reference/Main.html')
  const sheet = read('reference/State-Sheet.html')
  const curve = same(main, {
    where: 'Main.html @keyframes pip',
    pattern:
      /@keyframes pip\{0%,100%\{background:(#[0-9a-f]{6});box-shadow:none\}([\d.]+)%,([\d.]+)%\{background:(#[0-9a-f]{6});box-shadow:0 0 (\d+)px rgba\((\d+),(\d+),(\d+),([\d.]+)\)\}([\d.]+)%\{background:(#[0-9a-f]{6});box-shadow:none\}\}/,
  })
  if (curve[11] !== curve[1]) throw new Error('design numbers: Main.html @keyframes pip rests on two colours')
  const delays = matches(main, { where: 'Main.html pips', pattern: /animation: pip ([\d.]+)s linear -([\d.]+)s infinite/ })
  const steps = delays.slice(1).map((m, i) => n(delays[i][2]) - n(m[2]))
  if (steps.length === 0 || steps.some((step) => Math.abs(step - steps[0]) > 1e-3)) {
    throw new Error('design numbers: the pips in Main.html are not one beat apart')
  }
  const beats = Math.round(n(delays[0][1]) / steps[0])
  const glow = rgba(tokens, curve, 6)
  const card = same(sheet, {
    where: 'State-Sheet.html overlay card',
    pattern:
      /background: (#[0-9a-f]{6}); border: 1px solid (#[0-9a-f]{6})"><div style="display: flex; align-items: center; justify-content: space-between"><span style="font-size: [\d.]+px; font-weight: 600; color: (#[0-9a-f]{6})">[^<]* s left<\/span>[\s\S]*?<div style="height: \d+px; border-radius: \d+px; background: (#[0-9a-f]{6}); overflow: hidden"><div style="width: \d+%; height: 100%; background: (#[0-9a-f]{6})"><\/div>/,
  })
  return {
    pip: {
      rest: colour(tokens, curve[1]),
      lit: colour(tokens, curve[4]),
      riseBeats: pct(curve[2]) * beats,
      holdBeats: pct(curve[3]) * beats,
      endBeats: pct(curve[10]) * beats,
      glowPx: n(curve[5]),
      glow: glow.colour,
      glowAlpha: glow.alpha,
    },
    overlay: { background: card[1], border: card[2], ink: card[3], track: card[4], fill: card[5] },
  }
}

/** src/design/live-numbers.ts: the numbers outside the stage, a module of their own so the first load doesn't carry the stage's. */
export function liveNumbersSource(spec: Record<string, unknown>, render: Record<string, unknown>): string {
  return `// Generated by \`npm run design:numbers\` (web/scripts/design-numbers.ts) from the web app spec
// (LIVE_SPEC) and the pinned reference renders (LIVE_RENDER). Don't edit it: after a new handoff, run
// the command again. The numbers everything outside the stage draws with; the stage's are in
// src/stage/design-numbers.ts, which only the stage's lazy chunk loads. A colour is a tokens.css
// custom property where tokens.css has it, else the render's own hex.
export const LIVE_SPEC = ${JSON.stringify(spec, null, 2)} as const

export const LIVE_RENDER = ${JSON.stringify(render, null, 2)} as const
`
}

/** src/stage/design-numbers.ts. */
export function designNumbersSource(spec: Record<string, unknown>, render: Record<string, unknown>, tokens: Record<string, string>): string {
  return `// Generated by \`npm run design:numbers\` (web/scripts/design-numbers.ts) from the web app spec
// (SPEC), the pinned reference renders (RENDER) and tokens.css (TOKENS). Don't edit it: after a new
// handoff, run the command again. A colour is a tokens.css custom property where tokens.css has
// it, else the render's own hex.
export const SPEC = ${JSON.stringify(spec, null, 2)} as const

export const RENDER = ${JSON.stringify(render, null, 2)} as const

/** tokens.css's colours, by custom property: what the stage paints WebGL with (palette.ts). */
export const TOKENS: Readonly<Record<string, string>> = ${JSON.stringify(tokens, null, 2)}
`
}

/** The handoff the design numbers are read from. */
export interface Handoff {
  /** The web app spec. */
  spec: string
  /** tokens.css. */
  tokens: string
  /** Reads tokens.css or a render, each render RENDER or LIVE_RENDER reads the one HANDOFF.sha256 pins; null where the renders are missing (CI). */
  read: ReadText | null
}

/** The main checkout, which `git rev-parse --git-common-dir` names; null outside git. */
function mainCheckout(repo: string): string | null {
  try {
    const common = execFileSync('git', ['rev-parse', '--path-format=absolute', '--git-common-dir'], { cwd: repo, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] })
    return dirname(common.trim())
  } catch {
    return null
  }
}

/**
 * Reads the handoff: the spec and design files from this checkout, and the renders from here or,
 * as they aren't in git (CLAUDE.md, "Web App Design"), from the main checkout. Throws if a render
 * isn't the one HANDOFF.sha256 pins.
 */
export function readHandoff(repo: string): Handoff {
  const design = resolve(repo, 'docs/design/web-app')
  const spec = readFileSync(resolve(repo, 'docs/superpowers/specs/2026-09-23-web-app-rebuild-design.md'), 'utf8')
  const tokens = readFileSync(resolve(design, 'tokens.css'), 'utf8')
  const main = existsSync(resolve(design, 'reference/Main.html')) ? repo : mainCheckout(repo)
  const renders = main === null ? null : resolve(main, 'docs/design/web-app/reference')
  if (renders === null || !existsSync(resolve(renders, 'Main.html'))) return { spec, tokens, read: null }
  const path = (name: string) => (name.startsWith('reference/') ? resolve(renders, name.slice('reference/'.length)) : resolve(design, name))
  checkPins(readFileSync(path('HANDOFF.sha256'), 'utf8'), [...new Set([...RENDERS, ...LIVE_RENDERS])], (name) => readFileSync(path(name)))
  return { spec, tokens, read: (name) => readFileSync(path(name), 'utf8') }
}
