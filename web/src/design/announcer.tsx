import { useCallback, useState, type ReactNode } from 'react'
import { AnnounceContext } from './announce'

export interface AnnouncerProps {
  /** Standing news, such as the connection's: said again whenever it changes. */
  news: string
  children?: ReactNode
}

/**
 * The page's one polite status region. A screen reader reads changes inside a live region, but
 * often not a region that arrives with its text, so this one is always there. It says `news` when
 * that changes and whatever `useAnnounce()` hands it in between; the latest message wins.
 */
export function Announcer({ news, children }: AnnouncerProps) {
  const [message, setMessage] = useState(news)
  const [heard, setHeard] = useState(news)
  if (news !== heard) {
    setHeard(news)
    setMessage(news)
  }
  const announce = useCallback((text: string) => setMessage(text), [])
  return (
    <AnnounceContext value={announce}>
      {children}
      <span role="status" className="sr-only">
        {message}
      </span>
    </AnnounceContext>
  )
}
