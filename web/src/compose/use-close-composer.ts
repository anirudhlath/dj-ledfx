// Leaving the composer (§8.2, F4 ruling 13 as amended): Close, Cancel, Esc and a Start that has gone through all end it this one way, and the
// phone's sheet will too. A composer that was stepped into (its entry carries COMPOSER_ENTRY) is stepped back out of, so the history is as it
// was before and Back from Live leaves it; replacing the entry with Live instead left Live in the history twice. A composer with no step into it,
// a deep link or a reload of one, has nowhere to step back to, and Live replaces it.
import { useCallback, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router'
import { composerEntered } from './model'

/**
 * The entry whose exit has been asked for, until the location has moved off it. Every caller shares it: Esc is Live's and Cancel and Close are
 * the panel's, and a second exit before the first has left (a double click, Esc and then Cancel) would step back once more, out of Live.
 * The browser's step back comes later than the click, and a replace was the same however often it was asked. Any exit on its way holds the
 * rest, whatever entry the caller was rendered for: a look chosen in the panel replaces the entry and gives it a new key, and a Start that
 * answers late still holds a close from before.
 */
let leavingFrom: string | null = null

export function useCloseComposer(): () => void {
  const navigate = useNavigate()
  const { key, state } = useLocation()
  const entered = composerEntered(state)
  // The location moved: that exit is done, and the entry can be left again (stepped forward into, it is the same entry).
  useEffect(() => {
    if (leavingFrom !== key) leavingFrom = null
  }, [key])
  return useCallback(() => {
    if (leavingFrom !== null) return
    leavingFrom = key
    if (entered) navigate(-1)
    else navigate('/live', { replace: true })
  }, [navigate, entered, key])
}
