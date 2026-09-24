import { useState } from 'react'
import type { Connection } from './state'

/**
 * What the status region says about the link: nothing at first, "Reconnecting" when it drops,
 * "Live again" when it's back. The attempt count is noise; it stays out.
 */
export function useConnectionNews(status: Connection['status']): string {
  const [dropped, setDropped] = useState(status === 'reconnecting')
  if (status === 'reconnecting' && !dropped) setDropped(true)
  if (status === 'reconnecting') return 'Reconnecting'
  return dropped ? 'Live again' : ''
}
