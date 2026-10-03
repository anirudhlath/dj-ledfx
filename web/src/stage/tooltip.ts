// What the light tooltip says (§7.6 live: "hover tooltip on a light (name, hex + intensity, look ·
// zone, model · latency)"), and the light's colour now, from the frame store. Hex is uppercase (§10).
import type { Id, Light, RunningZone } from '@/api/contract'
import type { LightFrame } from '@/api/frames'
import { formatLatency, formatTime } from '@/lib/format'
import { hexOf, intensityOf, type RGB } from '@/lib/light-colour'
import { isStreamed, newestFirst, restingColour, type LightState } from './show'

export interface TooltipText {
  name: string
  /** "<look> · <zone>": the newest look running on the light; null when none is. */
  running: string | null
}

export function tooltipText(light: Light, running: readonly RunningZone[], zoneNames: ReadonlyMap<Id, string>): TooltipText {
  const zone = newestFirst(running).find((candidate) => candidate.lights.includes(light.id))
  const where = zone === undefined ? undefined : zoneNames.get(zone.zoneId)
  return {
    name: light.name,
    running: zone === undefined ? null : where === undefined ? zone.lookName : `${zone.lookName} · ${where}`,
  }
}

/**
 * The last line: the model, then the latency the engine times the light's frames by, once one is
 * known. An override comes first; then `liveMs`, the stats channel's latency_ms (the light's
 * effective latency, its manual offset included); and until the first stats message, REST's
 * measure (which leaves the offset out). REST's estimated flag gives the "~".
 */
export function deviceLine(light: Light, liveMs: number | null): string {
  const { overrideMs, measuredMs, estimated } = light.latency
  const ms = liveMs ?? measuredMs
  const latency = overrideMs != null ? formatLatency(overrideMs) : ms !== null ? formatLatency(ms, estimated) : null
  return latency === null ? light.model : `${light.model} · ${latency}`
}

/** The light's colour now: its frame's LEDs averaged, else the colour it rests on; null when neither. */
export function currentColour(frame: LightFrame | undefined, state: LightState): RGB | null {
  if (isStreamed(state) && frame !== undefined && frame.count > 0) {
    let [r, g, b] = [0, 0, 0]
    for (let i = 0; i < frame.count; i++) {
      r += frame.rgb[i * 3]
      g += frame.rgb[i * 3 + 1]
      b += frame.rgb[i * 3 + 2]
    }
    return [r / frame.count, g / frame.count, b / frame.count]
  }
  return restingColour(state)
}

/** The second line: the colour's hex and intensity, or what the light is doing instead; null when nothing is known. */
export function colourLine(state: LightState, rgb: RGB | null): string | null {
  if (state.status === 'offline') return `Offline since ${formatTime(new Date(state.since))}`
  if (state.status === 'switched-off') return 'Switched off elsewhere'
  if (rgb !== null) return `${hexOf(rgb)} · ${Math.round(intensityOf(rgb) * 100)}%`
  return state.power === false ? 'Off' : null
}
