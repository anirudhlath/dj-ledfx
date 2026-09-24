import { Button } from '@/design/button'

/** The root error boundary: calm copy instead of React Router's developer screen. */
export function AppError() {
  return (
    <div className="grid h-dvh place-items-center p-6">
      <title>Something broke · dj-ledfx</title>
      <div className="flex max-w-sm flex-col items-center gap-3 text-center">
        <h1 className="font-serif text-display-lg">Something broke</h1>
        <p className="text-body text-text-2">This screen hit an error. Your looks keep running on the server.</p>
        <Button variant="outline" icon="refresh" onClick={() => window.location.reload()}>
          Reload
        </Button>
      </div>
    </div>
  )
}
