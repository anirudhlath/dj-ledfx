import { useState } from 'react'
import { Icon } from '@/design/icon'
import type { Connection } from './state'

export interface ConnectionIndicatorProps {
  connection: Connection
  /** "bar": always shown (desktop). "header": only while reconnecting (phone). */
  variant: 'bar' | 'header'
}

const SPIN = 'animate-[reconnect-spin_1.4s_linear_infinite]'

/** §6.2 ConnectionIndicator: "● Live 60 fps" or "⟳ Reconnecting · try 3". */
export function ConnectionIndicator({ connection, variant }: ConnectionIndicatorProps) {
  return (
    <>
      <span role="status" className="sr-only">
        {useNews(connection.status)}
      </span>
      <Face connection={connection} variant={variant} />
    </>
  )
}

/**
 * What the status region says. Screen readers read changes inside a live region, but often not a
 * region that arrives with its text, so the region is always there: empty at first, "Reconnecting"
 * when the link drops, "Live again" when it's back. The attempt count is noise; it stays out.
 */
function useNews(status: Connection['status']): string {
  const [dropped, setDropped] = useState(status === 'reconnecting')
  if (status === 'reconnecting' && !dropped) setDropped(true)
  if (status === 'reconnecting') return 'Reconnecting'
  return dropped ? 'Live again' : ''
}

function Face({ connection, variant }: ConnectionIndicatorProps) {
  if (connection.status === 'live') {
    if (variant === 'header') return null
    return (
      <span className="inline-flex items-center gap-1.75 text-meta whitespace-nowrap text-text-2">
        <span aria-hidden="true" className="size-1.75 rounded-full bg-text animate-[livedot_2s_ease-in-out_infinite]" />
        Live
        <span className="num text-text-3 tablet:hidden">{connection.fps} fps</span>
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
