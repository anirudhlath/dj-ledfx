// The stage's zone tags (State-Problems, State-Transition; F3 decision 18): a crashed zone's
// "<look> stopped · HH:MM", a slow zone's "<actual> fps · target <target>", and a transition's
// "<from> → <to> · <doing>", which its moving percentage follows (decision 16). Each sits at the middle of
// its zone's lights, newest zone first; a zone with no placed lights has none.
import type { Id, RunningZone, Vec3 } from '@/api/contract'
import { formatTime } from '@/lib/format'
import { TRANSITION, transitionView } from '@/zones/zone-view'
import type { Body } from './bodies'
import { newestFirst } from './show'
import { zoneMiddle } from './zone-shape'

export type ZoneTag =
  | { zoneId: Id; kind: 'crashed' | 'slow'; text: string; at: Vec3 }
  | { zoneId: Id; kind: 'transition'; text: string; at: Vec3; progress: number; durationS: number | null }

export function zoneTags(running: readonly RunningZone[], bodies: readonly Body[]): ZoneTag[] {
  return newestFirst(running).flatMap((zone): ZoneTag[] => {
    const at = zoneMiddle(bodies, zone.lights)
    if (at === null) return []
    const { zoneId, lookName } = zone
    if (zone.state === 'crashed') {
      const when = zone.error == null ? '' : ` · ${formatTime(new Date(zone.error.at))}`
      return [{ zoneId, kind: 'crashed', text: `${lookName} stopped${when}`, at }]
    }
    if (zone.state === 'slow' && zone.fps != null) {
      return [{ zoneId, kind: 'slow', text: `${Math.round(zone.fps.actual)} fps · target ${zone.fps.target}`, at }]
    }
    const transition = zone.state === 'transition' ? transitionView(zone.transition) : null
    if (transition === null || zone.transition == null) return []
    const text = `${transition.from} → ${lookName} · ${TRANSITION[zone.transition.kind].doing}`
    return [{ zoneId, kind: 'transition', text, at, progress: transition.progress, durationS: transition.durationS }]
  })
}
