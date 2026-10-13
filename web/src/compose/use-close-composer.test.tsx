// What composer.test.tsx can't show: its memory history steps back the moment it is asked, so a second exit there always finds the
// location moved. These histories hold one entry, so a step back lands where it was, as a browser's has not yet landed, and what
// the exit asked of the router is what's counted.
import { act, fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import { COMPOSER_ENTRY } from './model'
import { useCloseComposer } from './use-close-composer'

/** An instance of the hook, with the close its first render gave it kept beside the current one (a late Start answer holds one like it). */
function Probe({ name }: { name: string }) {
  const close = useCloseComposer()
  const [first] = useState(() => close)
  return (
    <>
      <button onClick={close}>{name}</button>
      <button onClick={first}>{`${name}, first render's`}</button>
    </>
  )
}

function Host() {
  const [another, setAnother] = useState(false)
  return (
    <>
      <Probe name="Esc" />
      <button onClick={() => setAnother(true)}>Mount another</button>
      {another && <Probe name="Close" />}
    </>
  )
}

let opened = 0

/** A composer entered by a step from Live, as far as the exit can tell. Each has a key of its own: the guard is shared by the whole file. */
function openComposer() {
  const router = createMemoryRouter([{ path: '*', element: <Host /> }], {
    initialEntries: [{ pathname: '/live/put', state: COMPOSER_ENTRY, key: `composer-${opened++}` }],
  })
  const navigate = vi.spyOn(router, 'navigate')
  render(<RouterProvider router={router} />)
  return { router, stepsBack: () => navigate.mock.calls.filter(([to]) => Object.is(to, -1)).length }
}

const click = (name: string) => act(async () => void fireEvent.click(screen.getByRole('button', { name })))

describe('useCloseComposer, before the step back has landed', () => {
  it('steps back once for an exit and for no other until the location moves', async () => {
    const { router, stepsBack } = openComposer()
    await click('Esc')
    await click('Esc')
    expect(stepsBack()).toBe(1)
    // The location moved on (here to another composer, as composer.test.tsx steps back and forward): the next exit is a new one.
    await act(() => router.navigate('/live/put?zone=x', { state: COMPOSER_ENTRY }))
    await click('Esc')
    expect(stepsBack()).toBe(2)
  })

  it('is not undone by an instance that mounts while the exit is on its way', async () => {
    const { stepsBack } = openComposer()
    await click('Esc')
    await click('Mount another')
    await click('Close')
    expect(stepsBack()).toBe(1)
  })

  it('is kept by a close from an earlier render of the entry, as a Start that answers late holds', async () => {
    const { router, stepsBack } = openComposer()
    // A look chosen in the panel replaces the entry: the location has a key of its own and the first render's close has the old one.
    await act(() => router.navigate('/live/put?look=x', { replace: true, state: COMPOSER_ENTRY }))
    await click('Esc')
    await click("Esc, first render's")
    expect(stepsBack()).toBe(1)
  })
})
