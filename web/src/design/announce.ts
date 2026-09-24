import { createContext, useContext } from 'react'

/** Says a message through the page's status region. Outside an Announcer it says nothing. */
export const AnnounceContext = createContext<(message: string) => void>(() => {})

export function useAnnounce(): (message: string) => void {
  return useContext(AnnounceContext)
}
