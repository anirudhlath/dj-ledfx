// How the attention list draws each item (§6.2, §9.5). The server orders the items and writes their
// titles and explanations (F3 decision 15); this says which icon and tone each gets (decision 32) and
// what its actions do. `retry` draws nothing until an engine serves one (decision 14).
import type { AttentionItem, Id, RunningZone } from '@/api/contract'
import type { IconName } from '@/design/icons'

/** F3 decision 32: signal for a look in trouble, an input that's down or frames dropping; quiet otherwise. */
export type AttentionTone = 'signal' | 'quiet'

const KINDS: Record<AttentionItem['kind'], { icon: IconName | null; tone: AttentionTone }> = {
  'zone-crashed': { icon: 'alert', tone: 'signal' },
  'zone-slow': { icon: 'clock', tone: 'signal' },
  'frames-dropping': { icon: 'devices', tone: 'signal' },
  'light-offline': { icon: 'devices', tone: 'quiet' },
  // An input's icon is its own.
  'input-disconnected': { icon: null, tone: 'signal' },
  'input-stale': { icon: null, tone: 'quiet' },
}

/** The inputs State-Problems draws, by the id the server gives them; any other input gets `inputs`. */
const INPUT_ICONS: Readonly<Record<string, IconName>> = { 'home-assistant': 'ha', music: 'music' }

export function attentionLook(item: AttentionItem): { icon: IconName; tone: AttentionTone } {
  const { icon, tone } = KINDS[item.kind]
  return { icon: icon ?? INPUT_ICONS[item.subject.id] ?? 'inputs', tone }
}

/** One action, as F3 does it: Restart, or a link. */
export type AttentionAction =
  | { kind: 'restart'; label: 'Restart'; zoneId: Id; lookName: string }
  | { kind: 'link'; label: string; to: string }

/** The item's actions, in the server's order. One about a zone that has stopped since drops out. */
export function attentionActions(item: AttentionItem, running: readonly RunningZone[]): AttentionAction[] {
  const { type, id } = item.subject
  const zone = type === 'zone' ? running.find((candidate) => candidate.zoneId === id) : undefined
  const actions: AttentionAction[] = []
  for (const action of item.actions) {
    if (action === 'restart' && zone !== undefined) {
      actions.push({ kind: 'restart', label: 'Restart', zoneId: zone.zoneId, lookName: zone.lookName })
    } else if (action === 'details') {
      actions.push({ kind: 'link', label: 'Details', to: detailsOf(type, id, zone) })
    } else if (action === 'open') {
      const open = openOf(type, id, zone)
      if (open !== null) actions.push(open)
    }
  }
  return actions
}

/** A zone's look while it runs, else the zone; a light's page; the inputs. */
function detailsOf(type: AttentionItem['subject']['type'], id: Id, zone: RunningZone | undefined): string {
  if (type === 'zone') return zone === undefined ? `/live/zones/${id}` : `/looks/${zone.lookId}`
  return type === 'light' ? `/devices/${id}` : '/inputs'
}

/** "Open <look>" for a zone that runs, and the page an input or a light lives on. */
function openOf(type: AttentionItem['subject']['type'], id: Id, zone: RunningZone | undefined): AttentionAction | null {
  if (type === 'zone') return zone === undefined ? null : { kind: 'link', label: `Open ${zone.lookName}`, to: `/looks/${zone.lookId}` }
  return type === 'light' ? { kind: 'link', label: 'Open Devices', to: `/devices/${id}` } : { kind: 'link', label: 'Open Inputs', to: '/inputs' }
}
