// §7.4 The sun: a disc outside the home at its real azimuth and elevation, with a dashed arc of its
// recent path and a mono label, drawn whenever it's above the horizon. It sits just outside the home
// (decision 7): SUN_MARGIN_M past where a line from the middle of the
// outline's box, the sun's way, leaves the box, raised by its elevation from the ceiling. The azimuth
// is true north's; the home's northOffsetDeg turns it onto the plan.
import type { Home, SunInput, Vec3 } from '@/api/contract'
import { formatTime } from '@/lib/format'
import { bounds } from './plan'

const POINTS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'] as const
const RAD = Math.PI / 180
/** How far outside the outline's box the sun sits. */
const SUN_MARGIN_M = 1

/** The compass point nearest a bearing, as §7.4's label names it. */
export function compass(azimuthDeg: number): (typeof POINTS)[number] {
  return POINTS[Math.round((((azimuthDeg % 360) + 360) % 360) / 45) % 8]
}

/**
 * Up, and placeable: engine M6 settles the sun's shape (contract.ts), so a point without a finite
 * elevation and azimuth is no sun at all.
 */
const up = (sun: Pick<SunInput, 'elevation' | 'azimuth'>) =>
  Number.isFinite(sun.elevation) && Number.isFinite(sun.azimuth) && sun.elevation > 0

/** Where the sun is, in plan metres, for an elevation and azimuth. */
export function sunPoint(home: Pick<Home, 'outline' | 'ceiling' | 'northOffsetDeg'>, elevationDeg: number, azimuthDeg: number): Vec3 {
  const { min, max } = bounds(home.outline)
  const [cx, cy] = [(min[0] + max[0]) / 2, (min[1] + max[1]) / 2]
  const bearing = (azimuthDeg + home.northOffsetDeg) * RAD
  // A plan bearing points (sin b, −cos b): north is up the plan, toward −y.
  const [dx, dy] = [Math.sin(bearing), -Math.cos(bearing)]
  const exit = Math.min(
    Math.abs(dx) > 1e-9 ? (max[0] - min[0]) / 2 / Math.abs(dx) : Infinity,
    Math.abs(dy) > 1e-9 ? (max[1] - min[1]) / 2 / Math.abs(dy) : Infinity,
  )
  const reach = exit + SUN_MARGIN_M
  const elevation = elevationDeg * RAD
  const across = reach * Math.cos(elevation)
  return [cx + across * dx, cy + across * dy, home.ceiling + reach * Math.sin(elevation)]
}

export interface SunScene {
  at: Vec3
  /** The recent path above the horizon, oldest first, ending at the sun. */
  path: Vec3[]
  /** §7.4's label: SUN, the elevation in whole degrees, and the compass point; null where the stage has no labels. */
  label: string | null
}

/** What the stage draws of the sun, labelled or not (behaviour.ts), or null while it's down or unknown. */
export function sunScene(
  home: Pick<Home, 'outline' | 'ceiling' | 'northOffsetDeg'>,
  sun: SunInput | null | undefined,
  labelled = true,
): SunScene | null {
  if (sun == null || !up(sun)) return null
  const at = sunPoint(home, sun.elevation, sun.azimuth)
  const path = (Array.isArray(sun.path) ? sun.path : []).filter(up).map((point) => sunPoint(home, point.elevation, point.azimuth))
  return { at, path: [...path, at], label: labelled ? `SUN ${Math.round(sun.elevation)}° · ${compass(sun.azimuth)}` : null }
}

/**
 * §8.1's readout in three runs: its first word, the elevation and compass point (Main.png sets them in
 * mono), and the sunset, empty when it doesn't parse; null while the sun is down or unknown (decision 7).
 */
export function sunReadoutRuns(sun: SunInput | null | undefined): readonly [string, string, string] | null {
  if (sun == null || !up(sun)) return null
  const sunset = typeof sun.sunset === 'string' ? Date.parse(sun.sunset) : Number.NaN
  return ['Sun ', `${Math.round(sun.elevation)}° · ${compass(sun.azimuth)}`, Number.isNaN(sunset) ? '' : ` · sets ${formatTime(new Date(sunset))}`]
}

/** §8.1's readout: the elevation, the compass point and the sunset; null while the sun is down or unknown (decision 7). */
export function sunReadout(sun: SunInput | null | undefined): string | null {
  return sunReadoutRuns(sun)?.join('') ?? null
}
