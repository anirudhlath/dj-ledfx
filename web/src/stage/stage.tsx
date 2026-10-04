// The stage on Live (§8.1, §8.10): its data, then the view. Live loads this module lazily, so
// three.js and React Three Fiber arrive in a chunk of their own (§14: the first load's budget
// excludes three.js).
import type { Id, Room } from '@/api/contract'
import { StagePending } from './stage-pending'
import type { StageVariant } from './behaviour'
import { StageView } from './stage-view'
import { useStageData } from './use-stage-data'

/** "Click a room → /live/put?zone=<room>" (§8.1): a room's zone has the room's id. */
const composerFor = (room: Room) => `/live/put?zone=${encodeURIComponent(room.id)}`

export interface StageProps {
  variant: StageVariant
  /** The zone to outline (Task 12). */
  outlined?: Id | null
  /** §7.6 focus: the zone the stage frames (Zone detail). */
  focus?: Id | null
}

export default function Stage({ variant, outlined = null, focus = null }: StageProps) {
  const data = useStageData()
  if (data === null) return <StagePending />
  return <StageView data={data} variant={variant} route="live" roomTo={composerFor} outlined={outlined} focus={focus} />
}
