import { Icon } from '@/design/icon'
import type { Connection } from '@/api/live-store'

export interface ConnectionIndicatorProps {
  connection: Connection
  /** "bar": always shown (desktop). "header": only while reconnecting (phone). */
  variant: 'bar' | 'header'
}

const SPIN = 'animate-[spin_1.4s_linear_infinite]'

/**
 * §6.2 ConnectionIndicator: "● Live 60 fps" or "⟳ Reconnecting · try 3". It only draws; the
 * shell's one status region says the news (useConnectionNews).
 */
export function ConnectionIndicator({ connection, variant }: ConnectionIndicatorProps) {
  // Before the server's first word the link claims nothing (F0 review).
  if (connection.status === 'connecting') return null

  if (connection.status === 'live') {
    if (variant === 'header') return null
    return (
      <span className="inline-flex items-center gap-1.75 text-meta whitespace-nowrap text-text-2">
        <span aria-hidden="true" className="size-1.75 rounded-full bg-text animate-[livedot_2s_ease-in-out_infinite]" />
        Live
        {connection.fps !== null && <span className="num text-text-3 tablet:hidden">{connection.fps} fps</span>}
      </span>
    )
  }

  if (variant === 'header') {
    return (
      <span className="inline-flex h-(--touch-min) items-center rounded-pill border border-signal-line bg-signal-bg px-3 text-signal">
        <Icon name="refresh" size={15} className={SPIN} />
        <span className="sr-only">Reconnecting · try {connection.attempt}</span>
      </span>
    )
  }

  return (
    <span className="inline-flex items-center gap-1.75 text-meta font-semibold whitespace-nowrap text-signal">
      <Icon name="refresh" size={14} className={SPIN} />
      Reconnecting
      <span className="num font-normal">· try {connection.attempt}</span>
    </span>
  )
}
