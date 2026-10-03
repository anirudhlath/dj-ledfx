// The Running panel's header line, as §8.1 and the renders write it: "3 zones · all 19 lights" (Main),
// "1 zone · all 19 lights" (State-Firmware), "3 zones + 1 overlay" (Live-Doorbell), "4 zones · 1 stopped"
// (State-Problems) and "on screen only" (State-Preview-Only).
import type { RunningZone } from '@/api/contract'

const count = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`

export function runningSummary(zones: readonly RunningZone[], overlays: number, lightCount: number, previewOnly: boolean | null): string {
  if (previewOnly === true) return 'on screen only'
  const head = overlays > 0 ? `${count(zones.length, 'zone')} + ${count(overlays, 'overlay')}` : count(zones.length, 'zone')
  const stopped = zones.filter((zone) => zone.state === 'crashed').length
  if (stopped > 0) return `${head} · ${stopped} stopped`
  if (overlays > 0) return head
  const lit = new Set(zones.flatMap((zone) => zone.lights)).size
  return `${head} · ${lit > 0 && lit === lightCount ? `all ${lightCount} lights` : count(lit, 'light')}`
}
