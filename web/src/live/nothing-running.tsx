// §9.4 Nothing running (State-Nothing-Running): the lights as they were, and "Start again", recent looks
// with one-tap play (`GET /api/running/recent`, newest stop first: F3 decision 35). The thumbnail is a
// plain tile until F4 ports LookThumb (F3 decision 27).
import { useQuery } from '@tanstack/react-query'
import { failureText, startAgain } from '@/api/actions'
import type { RecentLook } from '@/api/contract'
import { queries } from '@/api/queries'
import { useAnnounce } from '@/design/announce'
import { cx } from '@/design/cx'
import { Icon } from '@/design/icon'
import { formatSpan } from '@/lib/format'
import { useNow } from '@/lib/use-now'

export interface NothingRunningProps {
  /** How many lights are on, of `total` (REST's lights): "9 on, 10 off". */
  on: number
  total: number
  /** Phone-State-Nothing-Running: smaller, one sentence, and Start again's buttons at the touch size. */
  variant?: 'desktop' | 'phone'
}

export function NothingRunning({ on, total, variant = 'desktop' }: NothingRunningProps) {
  const recent = useQuery(queries.recentLooks()).data ?? []
  const now = useNow()
  const announce = useAnnounce()
  const phone = variant === 'phone'
  const again = (look: RecentLook) => {
    startAgain(look).catch((error: unknown) => announce(failureText(`start ${look.lookName} again`, error)))
  }
  const counts = total > 0 ? `: ${on} on, ${total - on} off` : ''
  // On the phone nothing heads it: the page's "Running" goes when nothing runs.
  const Title = phone ? 'h2' : 'h3'
  return (
    <>
      <div className={cx('flex flex-col gap-2.5', !phone && 'px-1 pt-6 pb-2')}>
        <Title className={cx('font-serif leading-none', phone ? 'text-[32px]' : 'text-display-lg')}>Nothing running</Title>
        {phone ? (
          <p className="text-size-control leading-[1.45] text-text-2">Your lights are as they were{counts}.</p>
        ) : (
          <p className="text-body text-text-2">Your lights are as they were{counts}. Nothing turns on until you start a look.</p>
        )}
      </div>
      {recent.length > 0 && (
        // Phone-State-Nothing-Running sets the label and the rows 10 px apart, flush with the title.
        <section aria-labelledby="start-again" className={cx('flex flex-col', phone ? 'mt-1.5 gap-2.5' : 'mt-2 gap-2')}>
          <Title id="start-again" className={cx('label-caps text-text-3', !phone && 'px-1 pb-1')}>
            Start again
          </Title>
          <ul className={cx('flex flex-col', phone ? 'gap-2.5' : 'gap-2')}>
            {recent.map((look) => (
              <li
                key={`${look.zoneId}:${look.lookId}`}
                className="flex items-center gap-3 rounded-card border border-line bg-raised p-2"
              >
                <span
                  aria-hidden="true"
                  className={cx('block shrink-0 overflow-hidden rounded-control bg-control', phone ? 'h-10.5 w-16' : 'h-11.5 w-18')}
                />
                <span className="flex min-w-0 grow flex-col gap-0.5">
                  <span className={phone ? 'font-serif text-[19px] leading-[1.1]' : 'font-serif text-display-xs'}>{look.lookName}</span>
                  {/* F3 decision 35: Goodnight's end shows, so a line too long for the row goes on to a second. */}
                  <span className={cx('text-balance text-text-3', phone ? 'text-[11.5px]' : 'text-meta')}>
                    {look.zoneName} · {formatSpan(new Date(look.startedAt), new Date(look.stoppedAt), now)}
                  </span>
                </span>
                <button
                  type="button"
                  aria-label={`Start ${look.lookName} on ${look.zoneName} again`}
                  className={cx(
                    'inline-flex shrink-0 items-center justify-center border border-line bg-control',
                    phone ? 'size-11 rounded-tile text-text' : 'size-9 rounded-control text-text-2 touch-target hover:text-text',
                  )}
                  onClick={() => again(look)}
                >
                  <Icon name="play" size={phone ? 18 : 16} />
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  )
}
