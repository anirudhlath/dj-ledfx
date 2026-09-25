// The app's start: the mocks first where they're wanted (decision 11), then the data layer and the
// router. main.tsx calls it once.
import { QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router'
import { startDataLayer } from '@/api/live'
import { queryClient } from '@/api/queries'
import { MocksFailed } from '@/pages/mocks-failed'
import { routerBasename } from './router'
import { routes } from './routes'

export async function boot(container: HTMLElement): Promise<Root> {
  const root = createRoot(container)
  try {
    await startMocksIfAsked()
  } catch (error) {
    root.render(
      <StrictMode>
        <MocksFailed reason={error instanceof Error ? error.message : String(error)} />
      </StrictMode>,
    )
    return root
  }
  startDataLayer()
  const router = createBrowserRouter(routes, { basename: routerBasename(import.meta.env.BASE_URL) })
  root.render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </StrictMode>,
  )
  return root
}

/**
 * Decision 11: the mocks load in dev (with ?scenario=) and in the mock build only. A production
 * build folds this condition to false and drops the import, MSW with it (scripts/check-dist.ts).
 */
async function startMocksIfAsked(): Promise<void> {
  if (import.meta.env.DEV || import.meta.env.MODE === 'mock') {
    const { mockChoice } = await import('@/api/mocks/choice')
    const choice = mockChoice(window.location.search, { mockBuild: import.meta.env.MODE === 'mock' })
    if (choice !== null) {
      const { startMocks } = await import('@/api/mocks/browser')
      await startMocks(choice)
    }
  }
}
