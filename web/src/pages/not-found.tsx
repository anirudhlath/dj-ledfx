import { useLocation } from 'react-router'
import { ButtonLink } from '@/design/button'
import { EmptyState } from './empty-state'

/** Unknown paths stay inside the shell, with a way back to Live. */
export function NotFound() {
  const { pathname } = useLocation()
  return (
    <EmptyState
      title="Nothing here"
      action={
        <ButtonLink to="/live" variant="outline" icon="live">
          Go to Live
        </ButtonLink>
      }
    >
      There's no page at <span className="num text-text">{pathname}</span>.
    </EmptyState>
  )
}
