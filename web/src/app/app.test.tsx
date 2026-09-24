import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useEffect } from 'react'
import { createMemoryRouter, RouterProvider, type RouteObject } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { setViewportWidth } from '@/test/viewport'
import { routerBasename } from './router'
import { routes } from './routes'

/** The real routes, with one test-only page beside the real pages. */
function withPage(page: RouteObject): RouteObject[] {
  const add = (list: RouteObject[]): RouteObject[] =>
    list.some((route) => route.path === '*')
      ? [page, ...list]
      : list.map((route) => (route.children ? { ...route, children: add(route.children) } : route))
  return add(routes)
}

function Broken(): never {
  throw new Error('boom')
}

function renderApp(path: string, routeList: RouteObject[] = routes) {
  // Vite's base, as main.tsx gets it. Vitest reports '/' for import.meta.env.BASE_URL, so it's literal.
  const router = createMemoryRouter(routeList, { basename: routerBasename('/next/'), initialEntries: [path] })
  render(<RouterProvider router={router} />)
  return router
}

// The hero moment; the shared setup puts the real clock back after each test.
beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(2026, 8, 23, 19, 14))
})

describe('routes', () => {
  // Review focus: /next without a trailing slash lands on Live, like /next/.
  it.each(['/next', '/next/'])('%s redirects to Live', async (path) => {
    const router = renderApp(path)
    expect(await screen.findByRole('heading', { level: 1, name: 'Live' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/next/live')
    expect(document.title).toBe('Live · dj-ledfx')
  })

  // Review focus: a reloaded deep link renders its page.
  it('opens a deep link directly', async () => {
    renderApp('/next/looks/fireflies')
    expect(await screen.findByRole('heading', { level: 1, name: 'Looks' })).toBeInTheDocument()
    expect(screen.getByText('Look editor')).toBeInTheDocument()
  })

  // Review focus: a mistyped path stays in the shell with a way back.
  it('shows a calm not-found page inside the shell', async () => {
    const router = renderApp('/next/lookz')
    expect(await screen.findByText('Nothing here')).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Main' })).toBeInTheDocument()
    expect(screen.getByText('/lookz')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('link', { name: 'Go to Live' }))
    expect(router.state.location.pathname).toBe('/next/live')
  })

  // Review focus: a page that throws gets a calm error with Reload, and the chrome stays, so the
  // rest of the app is still a click away.
  it('shows its own error page inside the shell when a page throws', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    renderApp('/next/broken', withPage({ path: 'broken', element: <Broken /> }))
    const heading = await screen.findByRole('heading', { name: 'Something broke' })
    expect(screen.getByRole('button', { name: 'Reload' })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Main' })).toBeInTheDocument()
    expect(screen.getByRole('main')).toContainElement(heading)
  })

  // The test above mutes console.error; every later test must get it back.
  it('leaves console.error unmocked for the tests after it', () => {
    expect(vi.isMockFunction(console.error)).toBe(false)
  })

  it('shows a whole-page error, with its own landmark, when the shell itself throws', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    renderApp('/next/live', [{ ...routes[0], element: <Broken /> }])
    const main = await screen.findByRole('main')
    expect(within(main).getByRole('heading', { level: 1, name: 'Something broke' })).toBeInTheDocument()
    expect(within(main).getByRole('button', { name: 'Reload' })).toBeInTheDocument()
    expect(document.title).toBe('Something broke · dj-ledfx')
  })
})

// What the shell adds to the chrome's parts (shell.test.tsx): which chrome each width gets, the
// page's titles and context, and the hero's state reaching them.
describe('desktop chrome (Main.png)', () => {
  it('has the rail and the top bar, with the page title and context', async () => {
    renderApp('/next/live')
    const rail = await screen.findByRole('navigation', { name: 'Main' })
    expect(within(rail).getByRole('link', { name: 'dj-ledfx home' })).toBeInTheDocument()
    // The hero's offline light puts the dot on Devices.
    expect(within(rail).getByRole('link', { name: 'Devices, needs attention' })).toBeInTheDocument()

    const header = screen.getByRole('banner')
    expect(within(header).getByRole('heading', { level: 1 })).toHaveTextContent('Live')
    expect(header).toHaveTextContent('Wed 23 Sep · 19:14')
    expect(within(header).getByRole('group', { name: 'Tempo' })).toHaveTextContent('121.8')
  })

  it('moves the current page with navigation', async () => {
    renderApp('/next/live')
    const rail = await screen.findByRole('navigation', { name: 'Main' })
    await userEvent.click(within(rail).getByRole('link', { name: 'Map' }))
    expect(screen.getByRole('heading', { level: 1, name: 'Map' })).toBeInTheDocument()
    expect(screen.getByText('Place lights, anchors and sub-zones')).toBeInTheDocument()
    expect(within(rail).getByRole('link', { name: 'Map' })).toHaveAttribute('aria-current', 'page')
  })
})

describe('phone chrome (Phone-Live.png)', () => {
  beforeEach(() => {
    setViewportWidth(390)
  })

  it('has the header, the tempo strip on Live, and the tab bar', async () => {
    renderApp('/next/live')
    const header = await screen.findByRole('banner')
    expect(within(header).getByRole('heading', { level: 1 })).toHaveTextContent('Home')
    expect(header).toHaveTextContent('Wed 19:14 · sun sets 19:26')
    expect(within(header).getByRole('group', { name: 'Tempo' })).toBeInTheDocument()

    const tabs = screen.getByRole('navigation', { name: 'Main' })
    // The hero's offline light puts the dot on Devices.
    expect(within(tabs).getByRole('link', { name: 'Devices, needs attention' })).toBeInTheDocument()
    expect(within(tabs).getByRole('link', { name: 'Tempo' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'dj-ledfx home' })).toBeNull()
  })

  it('shows the tempo strip on Live only', async () => {
    renderApp('/next/looks')
    expect(await screen.findByRole('heading', { level: 1, name: 'Looks' })).toBeInTheDocument()
    expect(screen.queryByRole('group', { name: 'Tempo' })).toBeNull()
  })

  it('names /inputs Tempo on the phone', async () => {
    renderApp('/next/inputs')
    expect(await screen.findByRole('heading', { level: 1, name: 'Tempo' })).toBeInTheDocument()
    expect(screen.getByRole('banner')).toHaveTextContent('Wed 23 Sep · 19:14')
  })
})

// Review focus: crossing 768 px swaps the chrome in place; the page is not remounted.
it('swaps the chrome live across the breakpoint without remounting the page', async () => {
  let mounts = 0
  function Probe() {
    useEffect(() => {
      mounts += 1
    }, [])
    return <p>probe</p>
  }
  renderApp('/next/probe', withPage({ path: 'probe', element: <Probe /> }))
  expect(await screen.findByText('probe')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'dj-ledfx home' })).toBeInTheDocument()

  act(() => setViewportWidth(390))
  expect(screen.queryByRole('link', { name: 'dj-ledfx home' })).toBeNull()
  expect(within(screen.getByRole('navigation', { name: 'Main' })).getAllByRole('link')).toHaveLength(5)

  act(() => setViewportWidth(1024))
  expect(screen.getByRole('link', { name: 'dj-ledfx home' })).toBeInTheDocument()
  expect(mounts).toBe(1)
})
