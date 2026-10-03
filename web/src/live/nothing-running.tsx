// §9.4 Nothing running (State-Nothing-Running): the lights as they were, and "Start again", recent looks
// with one-tap play (`GET /api/running/recent`, newest stop first: F3 decision 35). The thumbnail is a
// plain tile until F4 ports LookThumb (F3 decision 27).
import { useQuery } from '@tanstack/react-query'
import { failureText, startAgain } from '@/api/actions'
import type { RecentLook } from '@/api/contract'
import { queries } from '@/api/queries'
import { useAnnounce } from '@/design/announce'
import { Icon } from '@/design/icon'
import { formatSpan } from '@/lib/format'
import { useNow } from '@/lib/use-now'

export interface NothingRunningProps {
  /** How many lights are on, of `total` (REST's lights): "9 on, 10 off". */
  on: number
  total: number
}

export function NothingRunning({ on, total }: NothingRunningProps) {
  const recent = useQuery(queries.recentLooks()).data ?? []
  const now = useNow()
  const announce = useAnnounce()
  const again = (look: RecentLook) => {
    startAgain(look).catch((error: unknown) => announce(failureText(`start ${look.lookName} again`, error)))
  }
  const counts = total > 0 ? `: ${on} on, ${total - on} off` : ''
  return (
    <>
      <div className="flex flex-col gap-2.5 px-1 pt-6 pb-2">
        <h3 className="font-serif text-display-lg leading-none">Nothing running</h3>
        <p className="text-body text-text-2">Your lights are as they were{counts}. Nothing turns on until you start a look.</p>
      </div>
      {recent.length > 0 && (
        <section aria-labelledby="start-again" className="mt-2 flex flex-col gap-2">
          <h3 id="start-again" className="label-caps px-1 pb-1 text-text-3">
            Start again
          </h3>
          <ul className="flex flex-col gap-2">
            {recent.map((look) => (
              <li
                key={`${look.zoneId}:${look.lookId}`}
                className="flex items-center gap-3 rounded-card border border-line bg-raised p-2"
              >
                <span aria-hidden="true" className="block h-11.5 w-18 shrink-0 overflow-hidden rounded-control bg-control" />
                <span className="flex min-w-0 grow flex-col gap-0.5">
                  <span className="font-serif text-display-xs">{look.lookName}</span>
                  <span className="truncate text-meta text-text-3">
                    {look.zoneName} · {formatSpan(new Date(look.startedAt), new Date(look.stoppedAt), now)}
                  </span>
                </span>
                <button
                  type="button"
                  aria-label={`Start ${look.lookName} on ${look.zoneName} again`}
                  className="inline-flex size-9 shrink-0 items-center justify-center rounded-control border border-line bg-control text-text-2 touch-target hover:text-text"
                  onClick={() => again(look)}
                >
                  <Icon name="play" />
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  )
}
