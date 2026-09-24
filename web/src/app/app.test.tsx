import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useEffect } from 'react'
import { createMemoryRouter, RouterProvider, type RouteObject } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AppError } from '@/pages/app-error'
import { AppShell } from '@/shell/app-shell'
import { setViewportWidth } from '@/test/viewport'
import { routes } from './routes'

/** The real shell around test-only pages. */
const inShell = (children: RouteObject[]): RouteObject[] => [{ element: <AppShell />, errorElement: <AppError />, children }]

function renderApp(path: string, routeList: RouteObject[] = routes) {
  const router = createMemoryRouter(routeList, { basename: '/next', initialEntries: [path] })
  render(<RouterProvider router={router} />)
  return router
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(2026, 8, 23, 19, 14))
})

afterEach(() => {
  vi.useRealTimers()
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

  it('shows its own error page when a screen throws', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    function Broken(): never {
      throw new Error('boom')
    }
    renderApp('/next/broken', inShell([{ path: 'broken', element: <Broken /> }]))
    expect(await screen.findByRole('heading', { name: 'Something broke' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reload' })).toBeInTheDocument()
  })
})

describe('desktop chrome (Main.png)', () => {
  it('has the rail, the page title and context, and the cluster', async () => {
    renderApp('/next/live')
    const rail = await screen.findByRole('navigation', { name: 'Main' })
    const links = within(rail).getAllByRole('link')
    expect(links.map((link) => link.textContent)).toEqual([
      '',
      'Live',
      'Looks',
      'Map',
      'Devices, needs attention',
      'Inputs',
      'Settings',
    ])
    expect(within(rail).getByRole('link', { name: 'dj-ledfx home' })).toHaveAttribute('href', '/next/live')
    expect(within(rail).getByRole('link', { name: 'Live' })).toHaveAttribute('aria-current', 'page')
    expect(rail).toHaveTextContent('dj-ledfx · homeserver')

    const header = screen.getByRole('banner')
    expect(within(header).getByRole('heading', { level: 1 })).toHaveTextContent('Live')
    expect(header).toHaveTextContent('Wed 23 Sep · 19:14')
    expect(within(header).getByRole('group', { name: 'Tempo' })).toHaveTextContent('121.8')
    expect(within(header).getByRole('switch', { name: 'Preview only' })).toBeInTheDocument()
    expect(within(header).getByRole('button', { name: '1 needs attention' })).toBeInTheDocument()
    expect(header).toHaveTextContent('Live60 fps')
  })

  it('moves the current page with navigation', async () => {
    renderApp('/next/live')
    const rail = await screen.findByRole('navigation', { name: 'Main' })
    await userEvent.click(within(rail).getByRole('link', { name: 'Map' }))
    expect(screen.getByRole('heading', { level: 1, name: 'Map' })).toBeInTheDocument()
    expect(screen.getByText('Place lights, anchors and sub-zones')).toBeInTheDocument()
    expect(within(rail).getByRole('link', { name: 'Map' })).toHaveAttribute('aria-current', 'page')
    expect(within(rail).getByRole('link', { name: 'Live' })).not.toHaveAttribute('aria-current')
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
    expect(within(header).getByRole('switch', { name: 'Preview only' })).toBeInTheDocument()
    expect(within(header).getByRole('button', { name: '1 needs attention' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Tempo' })).toBeInTheDocument()

    const tabs = screen.getByRole('navigation', { name: 'Main' })
    expect(within(tabs).getAllByRole('link').map((link) => link.textContent)).toEqual([
      'Live',
      'Looks',
      'Devices, needs attention',
      'Tempo',
      'Settings',
    ])
    expect(within(tabs).getByRole('link', { name: 'Tempo' })).toHaveAttribute('href', '/next/inputs')
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
  renderApp('/next/live', inShell([{ path: 'live', element: <Probe /> }]))
  expect(await screen.findByText('probe')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'dj-ledfx home' })).toBeInTheDocument()

  act(() => setViewportWidth(390))
  expect(screen.queryByRole('link', { name: 'dj-ledfx home' })).toBeNull()
  expect(within(screen.getByRole('navigation', { name: 'Main' })).getAllByRole('link')).toHaveLength(5)

  act(() => setViewportWidth(1024))
  expect(screen.getByRole('link', { name: 'dj-ledfx home' })).toBeInTheDocument()
  expect(mounts).toBe(1)
})
