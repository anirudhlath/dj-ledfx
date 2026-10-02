import { QueryClientProvider } from '@tanstack/react-query'
import { render, type RenderOptions } from '@testing-library/react'
import { createMemoryRouter, RouterProvider, type RouteObject } from 'react-router'
import { queryClient } from '@/api/queries'
import { routerBasename } from '@/app/router'
import { routes as appRoutes } from '@/app/routes'

interface RenderAppOptions {
  /** The app's routes unless given. */
  routes?: RouteObject[]
  /** Wraps the router, as a React Profiler does. */
  wrapper?: RenderOptions['wrapper']
}

/** Renders the app's routes at `path`, under /next as app/boot.tsx serves them. */
export function renderApp(path: string, { routes = appRoutes, wrapper }: RenderAppOptions = {}) {
  // Vite's base, as boot gets it. Vitest reports '/' for import.meta.env.BASE_URL, so it's literal.
  const router = createMemoryRouter(routes, { basename: routerBasename('/next/'), initialEntries: [path] })
  // The app's query client, as app/boot.tsx provides it; the shared setup clears it after each test.
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
    { wrapper },
  )
  return router
}
