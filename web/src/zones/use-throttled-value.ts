// A value the owner drags, like a zone's brightness (§11.3): shown at once, sent at most once each
// SEND_EVERY_MS, and the last value always sent (F3 decision 9). Once its last send settles, the control
// shows the server's value again, which the action has already put in the store (F3 decision 8). A send
// that fails drops what's queued and puts the server's value back (Review Focus 1). So does the link
// dropping, and nothing still queued is sent after it (Review Focus 3). The queue lives in a ref that only
// the handlers and an effect touch.
import { useEffect, useRef, useState } from 'react'

/** F3 decision 9: engineering, not a design value. */
export const SEND_EVERY_MS = 100

export interface ThrottleOptions {
  /** The server's value. */
  server: number
  send: (value: number) => Promise<void>
  onFail: (error: unknown) => void
  /** False while the link is down: nothing is sent, and the control shows the server's value. */
  enabled: boolean
}

export interface Throttled {
  /** What the control shows: the owner's value until its last send settles, else the server's. */
  value: number
  change: (value: number) => void
}

interface Queue {
  /** The latest value, waiting for the window to end; null when there's none. */
  waiting: number | null
  timer: ReturnType<typeof setTimeout> | null
  /** Sends not yet settled. */
  sending: number
}

function drop(queue: Queue): void {
  if (queue.timer !== null) clearTimeout(queue.timer)
  queue.timer = null
  queue.waiting = null
}

export function useThrottledValue({ server, send, onFail, enabled }: ThrottleOptions): Throttled {
  const [owned, setOwned] = useState<number | null>(null)
  const [wasEnabled, setWasEnabled] = useState(enabled)
  if (enabled !== wasEnabled) {
    // React's way to adjust state to a prop: with the link down, the control shows the server's value.
    setWasEnabled(enabled)
    if (!enabled) setOwned(null)
  }
  const queue = useRef<Queue>({ waiting: null, timer: null, sending: 0 })
  // The link dropped, or the control went away: nothing still queued is sent.
  useEffect(() => {
    const current = queue.current
    if (!enabled) drop(current)
    return () => drop(current)
  }, [enabled])

  const fire = (current: Queue, value: number) => {
    current.sending += 1
    send(value).then(
      () => {
        current.sending -= 1
        if (current.sending === 0 && current.timer === null) setOwned(null)
      },
      (error: unknown) => {
        current.sending -= 1
        drop(current)
        setOwned(null)
        onFail(error)
      },
    )
  }

  const change = (value: number) => {
    if (!enabled) return
    setOwned(value)
    const current = queue.current
    if (current.timer !== null) {
      current.waiting = value
      return
    }
    fire(current, value)
    const windowEnds = () => {
      current.timer = null
      const next = current.waiting
      if (next === null) {
        if (current.sending === 0) setOwned(null)
        return
      }
      current.waiting = null
      fire(current, next)
      current.timer = setTimeout(windowEnds, SEND_EVERY_MS)
    }
    current.timer = setTimeout(windowEnds, SEND_EVERY_MS)
  }

  return { value: owned ?? server, change }
}
