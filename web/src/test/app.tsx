import { render } from '@testing-library/react'
import { createMemoryRouter, RouterProvider, type RouteObject } from 'react-router'
import { routerBasename } from '@/app/router'
import { routes } from '@/app/routes'

/** Renders the app's routes (or `routeList`) at `path`, under /next as main.tsx serves them. */
export function renderApp(path: string, routeList: RouteObject[] = routes) {
  // Vite's base, as main.tsx gets it. Vitest reports '/' for import.meta.env.BASE_URL, so it's literal.
  const router = createMemoryRouter(routeList, { basename: routerBasename('/next/'), initialEntries: [path] })
  render(<RouterProvider router={router} />)
  return router
}
