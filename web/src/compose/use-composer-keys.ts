// §8.2: "Keyboard: `L` opens the composer from Live; arrows move through tiles; Enter starts; Esc cancels."
// The page's two (F4 ruling 12): L, unless it's typed into a field or comes with Ctrl, Alt or Meta (the
// browser's), and Esc anywhere on the page while the composer is open. Whatever takes an Esc first keeps
// it: an open list or popover closes (Base UI stops the key there), and a search clears.
import { useEffect } from 'react'
import { useNavigate } from 'react-router'
import { composerPath } from './model'

const typing = (target: EventTarget | null) =>
  target instanceof HTMLElement && (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName))

/** L opens the composer while it's closed, and Esc closes it while it's open. */
export function useComposerKeys(composing: boolean): void {
  const navigate = useNavigate()
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return
      if (composing && event.key === 'Escape') {
        event.preventDefault()
        navigate('/live', { replace: true })
      } else if (!composing && event.key.toLowerCase() === 'l' && !event.ctrlKey && !event.altKey && !event.metaKey && !typing(event.target)) {
        event.preventDefault()
        navigate(composerPath(null))
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [composing, navigate])
}
