import { QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router'
import { startDataLayer } from './api/live'
import { queryClient } from './api/queries'
import { routerBasename } from './app/router'
import { routes } from './app/routes'
import './styles/app.css'

async function boot(): Promise<void> {
  // Decision 11: the mocks load in dev (with ?scenario=) and in the mock build only. A production
  // build folds this condition to false and drops the import, MSW with it (scripts/check-dist.ts).
  if (import.meta.env.DEV || import.meta.env.MODE === 'mock') {
    const { mockChoice } = await import('./api/mocks/choice')
    const choice = mockChoice(window.location.search, { mockBuild: import.meta.env.MODE === 'mock' })
    if (choice !== null) {
      const { startMocks } = await import('./api/mocks/browser')
      await startMocks(choice)
    }
  }
  startDataLayer()
  const router = createBrowserRouter(routes, { basename: routerBasename(import.meta.env.BASE_URL) })
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </StrictMode>,
  )
}

void boot()
