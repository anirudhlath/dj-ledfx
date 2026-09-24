import { useLocation } from 'react-router'
import { ButtonLink } from '@/design/button'

/** Unknown paths stay inside the shell, with a way back to Live. */
export function NotFound() {
  const { pathname } = useLocation()
  return (
    <div className="grid h-full place-items-center p-6">
      <div className="flex max-w-sm flex-col items-center gap-3 text-center">
        <p className="font-serif text-display-lg">Nothing here</p>
        <p className="text-body text-text-2">
          There's no page at <span className="num text-text">{pathname}</span>.
        </p>
        <ButtonLink to="/live" variant="outline" icon="live">
          Go to Live
        </ButtonLink>
      </div>
    </div>
  )
}
