// The marks the overlay draws over the lights (§7.3 height cue and states on the stage, §9.1): a
// drop line from every raised compact light to a floor tick; a ring and slash for a light switched off
// elsewhere; a dashed ring (a compact light) or dashed segments (a strip) for one offline; a dotted
// ring for one running its own effect; wave marks beside a streamed copy's last sample. They depend
// on the pose and the lights' status, never on frames or colours, so they're drawn when either changes.
import type { Id, LightStatus, Vec2 } from '@/api/contract'
import { anchorIndex, type Body } from './bodies'
import { projectPoint, type CameraPose } from './camera'
import type { LightState } from './show'

export type Mark =
  | { kind: 'drop'; key: string; from: Vec2; to: Vec2 }
  | { kind: 'switched-off' | 'offline' | 'own-effect' | 'streamed-copy'; key: string; at: Vec2 }
  | { kind: 'offline-strip'; key: string; points: Vec2[] }

/** Where a light's ring sits: its anchor sample, where a compact light's core is (anchorIndex()). */
export function anchorOf(body: Body): Body['samples'][number] {
  return body.samples[anchorIndex(body)]
}

/** Each light's status: all the marks read of its state. */
export function statusesOf(states: ReadonlyMap<Id, LightState>): Map<Id, LightStatus> {
  return new Map([...states].map(([id, state]) => [id, state.status]))
}

export function lightMarks(pose: CameraPose, bodies: readonly Body[], statuses: ReadonlyMap<Id, LightStatus>): Mark[] {
  return bodies.flatMap((body, index): Mark[] => {
    const key = `${body.lightId}:${index}`
    const marks: Mark[] = []
    if (body.form === 'compact') {
      const bottom = body.samples[0]
      if (bottom[2] > 0) marks.push({ kind: 'drop', key: `${key}:drop`, from: projectPoint(pose, bottom), to: projectPoint(pose, [bottom[0], bottom[1], 0]) })
    }
    const status = statuses.get(body.lightId)
    const at = projectPoint(pose, anchorOf(body))
    switch (status) {
      case 'switched-off':
      case 'own-effect':
        marks.push({ kind: status, key: `${key}:${status}`, at })
        break
      case 'streamed-copy':
        // State-Firmware.png draws the waves beside the light's last sample.
        marks.push({ kind: status, key: `${key}:${status}`, at: projectPoint(pose, body.samples[body.samples.length - 1]) })
        break
      case 'offline':
        marks.push(
          body.form === 'compact'
            ? { kind: 'offline', key: `${key}:offline`, at }
            : { kind: 'offline-strip', key: `${key}:offline`, points: body.samples.map((sample) => projectPoint(pose, sample)) },
        )
        break
    }
    return marks
  })
}
