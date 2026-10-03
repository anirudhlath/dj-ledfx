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

export default function Stage({ variant, outlined = null }: { variant: StageVariant; outlined?: Id | null }) {
  const data = useStageData()
  if (data === null) return <StagePending />
  return <StageView data={data} variant={variant} route="live" roomTo={composerFor} outlined={outlined} />
}
