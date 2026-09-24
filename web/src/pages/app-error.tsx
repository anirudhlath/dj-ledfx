import { Button } from '@/design/button'

function Message({ heading: Heading }: { heading: 'h1' | 'h2' }) {
  return (
    <div className="grid h-full place-items-center p-6">
      <div className="flex max-w-sm flex-col items-center gap-3 text-center">
        <Heading className="font-serif text-display-lg">Something broke</Heading>
        <p className="text-body text-text-2">This screen hit an error. Your looks keep running on the server.</p>
        <Button variant="outline" icon="refresh" onClick={() => window.location.reload()}>
          Reload
        </Button>
      </div>
    </div>
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
      <title>Something broke · dj-ledfx</title>
      <Message heading="h1" />
    </main>
  )
}
