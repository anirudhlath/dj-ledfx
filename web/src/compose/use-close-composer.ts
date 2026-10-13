// Leaving the composer (§8.2, F4 ruling 13 as amended): Close, Cancel, Esc and a Start that has gone through all end it this one way, and the
// phone's sheet will too. A composer that was stepped into (its entry carries COMPOSER_ENTRY) is stepped back out of, so the history is as it
// was before and Back from Live leaves it; replacing the entry with Live instead left Live in the history twice. A composer with no step into it,
// a deep link or a reload of one, has nowhere to step back to, and Live replaces it.
import { useCallback, useEffect } from 'react'
import { useLocation, useMatch, useNavigate } from 'react-router'
import { COMPOSER_ROUTE, composerEntered } from './model'

/**
 * Whether an exit has been asked for and the location has not yet left the composer's route. Every caller shares it: Esc is Live's, and
 * Cancel, Close and Start are the panel's. A browser's step back lands after the click, so a second exit asked before then (a double
 * click, Esc and then Cancel) would step back once more, out of Live; a replace was the same however often it was asked. An exit on its
 * way therefore holds every other, whichever render's close asks (a Start that answers late calls one from an earlier render). A look
 * chosen in the panel replaces the entry, a new key on the same route, and does not free it. Two things do. The location leaving the
 * route does: Live's instance is always mounted and sees /live arrive. And the last instance unmounting does, since with none left there
 * is no exit to double, and a Start that answers late goes nowhere (use-composer.ts checks that its composer is still mounted). That
 * closes Esc, then a rail click off Live (no instance is left to see the route change), then the step back landing on the composer:
 * its instances mount on the composer's route, which frees nothing, and would find the way still held.
 */
let leaving = false

/** How many instances of the hook are mounted: the last to go frees the way. */
let instances = 0

export function useCloseComposer(): () => void {
  const navigate = useNavigate()
  const { state } = useLocation()
  const entered = composerEntered(state)
  const composing = useMatch(COMPOSER_ROUTE) !== null
  useEffect(() => {
    instances += 1
    return () => {
      instances -= 1
      if (instances === 0) leaving = false
    }
  }, [])
  useEffect(() => {
    if (!composing) leaving = false
  }, [composing])
  return useCallback(() => {
    if (leaving) return
    leaving = true
    if (entered) navigate(-1)
    else navigate('/live', { replace: true })
  }, [navigate, entered])
}
