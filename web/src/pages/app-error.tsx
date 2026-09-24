import { documentTitle } from '@/app/page-meta'
import { Button } from '@/design/button'
import { EmptyState } from './empty-state'

function Message({ heading }: { heading: 'h1' | 'h2' }) {
  return (
    <EmptyState
      as={heading}
      title="Something broke"
      action={
        <Button variant="outline" icon="refresh" onClick={() => window.location.reload()}>
          Reload
        </Button>
      }
    >
      This screen hit an error. Your looks keep running on the server.
    </EmptyState>
  )
}

/**
 * A page threw, or a lazy page failed to load after a deploy: calm copy and Reload instead of
 * React Router's developer screen. It fills <main> under the page's own title, and the chrome
 * stays, so the rest of the app is still a click away.
 */
export function AppError() {
  return <Message heading="h2" />
}

/** AppShell itself threw, so there's no chrome: the error is the whole page, with its own landmark. */
export function RootError() {
  return (
    <main className="h-dvh">
      <title>{documentTitle('Something broke')}</title>
      <Message heading="h1" />
    </main>
  )
}
