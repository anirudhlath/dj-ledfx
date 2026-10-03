// §9.4 Reconnecting: "Stage frozen (7.6), cards at 45% opacity and inert, a centred card: 'Lost the live
// link to homeserver. Your looks keep running on the server. This is the last frame, from 19:14:32.
// Controls come back when the link does.' + Try now." The phone's card sits under its stage with the
// render's shorter words (Phone-State-Reconnecting). Try now retries at once (§9.4's backoff otherwise).
import { useId } from 'react'
import { retryLink } from '@/api/actions'
import { useReconnecting, useServerName } from '@/chrome/hooks'
import { Button } from '@/design/button'
import { Icon } from '@/design/icon'
import { formatTimeWithSeconds } from '@/lib/format'
import { StageCard } from './stage-card'

export function ReconnectingCard({ variant }: { variant: 'desktop' | 'phone' }) {
  const link = useReconnecting()
  const server = useServerName()
  const title = useId()
  if (link === null) return null
  const at = link.lastHeard === null ? null : formatTimeWithSeconds(new Date(link.lastHeard))
  const tries = `Reconnecting · try ${link.attempt}`

  if (variant === 'phone') {
    return (
      <section aria-labelledby={title} className="flex flex-col gap-2 rounded-panel border border-line-strong bg-raised p-4">
        <span className="flex items-center gap-2 text-meta font-bold tracking-[0.06em] text-signal uppercase">
          <Icon name="reconnect" size={16} />
          {tries}
        </span>
        <h2 id={title} className="font-serif text-[24px] leading-[1.1]">
          Lost the live link
        </h2>
        <p className="text-size-control leading-[1.45] text-text-2">
          Your looks keep running on {server}.{at === null ? '' : ` Last frame ${at}.`}
        </p>
        {/* Phone-State-Reconnecting draws this lg button's words at 14 px, below lg's own size. */}
        <Button size="lg" icon="refresh" className="w-full text-[14px]!" onClick={retryLink}>
          Try now
        </Button>
      </section>
    )
  }

  return (
    <StageCard labelledBy={title} className="w-100 gap-3 p-5.5">
      <span className="flex items-center gap-2.5 text-size-control font-bold tracking-[0.06em] text-signal uppercase">
        <Icon name="reconnect" size={18} />
        {tries}
      </span>
      <h2 id={title} className="font-serif text-display-md leading-[1.1]">
        Lost the live link to {server}
      </h2>
      <p className="text-body text-text-2">
        Your looks keep running on the server.{at === null ? '' : ` This is the last frame, from ${at}.`} Controls come back when
        the link does.
      </p>
      <div className="flex gap-2.5">
        <Button icon="refresh" onClick={retryLink}>
          Try now
        </Button>
      </div>
    </StageCard>
  )
}
