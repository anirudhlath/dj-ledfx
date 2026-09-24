import { render, within } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router'

/** Renders `ui` as if the app were at /next{path}. */
export function renderAt(path: string, ui: ReactNode) {
  return render(
    <MemoryRouter basename="/next" initialEntries={[`/next${path}`]}>
      {ui}
    </MemoryRouter>,
  )
}

/** The text of each link in a navigation, in order. */
export function linkNames(nav: HTMLElement) {
  return within(nav)
    .getAllByRole('link')
    .map((link) => link.textContent)
}
