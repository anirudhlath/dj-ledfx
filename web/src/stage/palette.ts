// The stage's colours, by name: a tokens.css custom property ("--color-stage-floor") or, where the
// renders draw a colour tokens.css lacks, RENDER's hex (scripts/design-extract.ts names each). WebGL
// takes them as 0–1 sRGB numbers, read from tokens.css itself; CSS and SVG take var(--…).
import tokensCss from '@/styles/tokens.css?raw'
import { RENDER } from './design-numbers'
import { parseHex, type Colour } from './light-maths'

const TOKENS = new Map([...tokensCss.matchAll(/(--color-[\w-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)].map((m) => [m[1], m[2]]))

/** A colour for WebGL. Throws on a name tokens.css doesn't have: a typo, or a handoff that renamed it. */
export function colourOf(name: string): Colour {
  const hex = name.startsWith('--') ? TOKENS.get(name) : name
  const rgb = parseHex(hex)
  if (rgb === null) throw new Error(`stage palette: no colour ${name}`)
  return [rgb[0] / 255, rgb[1] / 255, rgb[2] / 255]
}

/** A colour for CSS or SVG. */
export const cssColour = (name: string): string => (name.startsWith('--') ? `var(${name})` : name)

/** A font size for CSS: a render's px, or a tokens.css size ("--text-data"). */
export const cssSize = (size: string | number): string | number => (typeof size === 'number' ? size : `var(${size})`)

/** Everything the scene paints (§7.1, §7.3). */
export const STAGE_PALETTE = {
  bg: colourOf('--color-bg'),
  text: colourOf('--color-text'),
  floor: colourOf('--color-stage-floor'),
  floorEdge: colourOf('--color-stage-floor-edge'),
  wallTop: colourOf('--color-stage-wall-top'),
  wallSide: colourOf('--color-stage-wall-side'),
  wallSide2: colourOf('--color-stage-wall-side-2'),
  columnTop: colourOf('--color-stage-column-top'),
  furnitureTop: colourOf('--color-stage-furniture-top'),
  furnitureSide: colourOf(RENDER.furniture.sideFacing),
  furnitureSide2: colourOf(RENDER.furniture.sideOther),
  furnitureEdge: colourOf(RENDER.furniture.edge.colour),
  courtyard: colourOf('--color-stage-courtyard'),
  courtyardDot: colourOf(RENDER.courtyard.dotColour),
  balconyHatch: colourOf(RENDER.balcony.hatchColour),
  lightOff: colourOf('--color-stage-light-off'),
  stripDark: colourOf(RENDER.strip.darkColour),
} as const

export type StagePalette = typeof STAGE_PALETTE

