// Leaving the composer (§8.2, F4 ruling 13 as amended): Close, Cancel, Esc and a Start that has gone through all end it this one way, and the
// phone's sheet will too. A composer that was stepped into (its entry carries COMPOSER_ENTRY) is stepped back out of, so the history is as it
// was before and Back from Live leaves it; replacing the entry with Live instead left Live in the history twice. A composer with no step into it,
// a deep link or a reload of one, has nowhere to step back to, and Live replaces it.
import { useCallback } from 'react'
import { useLocation, useNavigate } from 'react-router'
import { composerEntered } from './model'

export function useCloseComposer(): () => void {
  const navigate = useNavigate()
  const entered = composerEntered(useLocation().state)
  return useCallback(() => {
    if (entered) navigate(-1)
    else navigate('/live', { replace: true })
  }, [navigate, entered])
}
