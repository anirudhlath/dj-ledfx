// §11.5's tempo source popover (F3 decisions 6 and 7): §6.7's SourceChain, §8.8's sentence, the hold and
// the way out of it, and the lock. The tempo module's source button is its trigger, on desktop.
import { useState, type ReactElement } from 'react'
import { failureText, setTempoLock } from '@/api/actions'
import type { TempoLock } from '@/api/contract'
import { useLive } from '@/api/live-store'
import { useAnnounce } from '@/design/announce'
import { Button } from '@/design/button'
import { Popover } from '@/design/overlays'
import { Segmented } from '@/design/segmented'
import { SourceChain } from './source-chain'
import { sourceStatuses } from './sources'

const LOCKS = [
  { value: 'auto', label: 'Auto' },
  { value: 'prodjlink', label: 'Pro DJ Link' },
  { value: 'music', label: 'Music' },
  { value: 'internal', label: 'Internal' },
] as const satisfies readonly { value: TempoLock; label: string }[]

/** §8.8's copy, under the chain. */
export const SOURCE_SENTENCE =
  "The first source that's available drives the clock. Tapping sets Internal and takes over until music or a DJ starts again."

export function TempoSourcePopover({ trigger }: { trigger: ReactElement }) {
  return (
    <Popover trigger={trigger} title="Tempo source" align="start">
      <TempoSource />
    </Popover>
  )
}

/** The popover's body. It mounts only while the popover is open, so it follows the inputs only then. */
function TempoSource() {
  const inputs = useLive((state) => state.inputs)
  const decks = useLive((state) => state.decks)
  const active = useLive((state) => state.beat?.source ?? null)
  const announce = useAnnounce()
  const [sending, setSending] = useState(false)
  const lock = (next: TempoLock) => {
    const releasing = next === 'auto' && inputs?.tempo.held === true
    setSending(true)
    setTempoLock(next)
      .catch((error: unknown) => announce(failureText(releasing ? 'give the tempo back' : 'lock the tempo', error)))
      .finally(() => setSending(false))
  }
  return (
    <div className="flex w-96 max-w-[calc(100vw-2rem)] flex-col gap-3 px-3.5 pb-3.5">
      {inputs !== null && active !== null && (
        <SourceChain direction="column" active={active} statuses={sourceStatuses(inputs, decks ?? [])} />
      )}
      <p className="text-meta text-text-3">{SOURCE_SENTENCE}</p>
      {inputs?.tempo.held === true && (
        <div className="flex items-center gap-3 rounded-tile border border-line px-3 py-2.5">
          <p className="flex-1 text-meta text-text-2">Internal holds the tempo until a DJ starts again.</p>
          <Button variant="secondary" size="sm" disabled={sending} onClick={() => lock('auto')}>
            Back to Auto
          </Button>
        </div>
      )}
      {inputs !== null && (
        <div className="flex flex-col gap-1.5">
          <span className="label-caps">Lock</span>
          <Segmented label="Lock the tempo to" value={inputs.tempo.lock} options={LOCKS} onValueChange={lock} />
        </div>
      )}
    </div>
  )
}
