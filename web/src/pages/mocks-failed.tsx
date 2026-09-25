import { documentTitle } from '@/app/page-meta'
import { Button } from '@/design/button'
import { EmptyState } from './empty-state'

/** MSW's worker didn't register (the mock build over plain http, say): say so, not a blank page. */
export function MocksFailed({ reason }: { reason: string }) {
  return (
    <main className="h-dvh">
      <title>{documentTitle("The mocks didn't start")}</title>
      <EmptyState
        as="h1"
        title="The mocks didn't start"
        action={
          <Button variant="outline" icon="refresh" onClick={() => window.location.reload()}>
            Reload
          </Button>
        }
      >
        The mock server runs in a service worker, which didn't register: {reason} Browsers allow one only
        over https or on localhost.
      </EmptyState>
    </main>
  )
}
