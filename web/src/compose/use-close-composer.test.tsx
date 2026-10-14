// What composer.test.tsx can't show: its memory history steps back the moment it is asked, so a second exit there always finds the
// location moved. Here every step back asked of the router is held, as a browser's lands later, and the asks are what's counted.
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import { composerLink } from './model'
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
      <button onClick={() => setAnother(false)}>Unmount another</button>
      {another && <Probe name="Close" />}
    </>
  )
}

/** Every step back asked of `router` is held, as a browser's lands later. Returns how many have been asked. */
function holdStepsBack(router: ReturnType<typeof createMemoryRouter>) {
  const navigate = router.navigate.bind(router)
  let asked = 0
  vi.spyOn(router, 'navigate').mockImplementation((to, options) => {
    if (!Object.is(to, -1)) return navigate(to, options)
    asked += 1
    return Promise.resolve()
  })
  return () => asked
}

/** Live, then a step into the composer, as the app gets there. The guard is the module's and outlives a test: a mount on Live drops it. */
async function openComposer() {
  const router = createMemoryRouter([{ path: '*', element: <Host /> }], { initialEntries: ['/live'] })
  const stepsBack = holdStepsBack(router)
  render(<RouterProvider router={router} />)
  const { to, state } = composerLink()
  await act(() => router.navigate(to, { state }))
  return { router, stepsBack }
}

/** A page that opens straight onto the composer, as a step back lands on it: its entry carries the marker. */
function openOnComposer() {
  const { to, state } = composerLink()
  const router = createMemoryRouter([{ path: '*', element: <Host /> }], { initialEntries: [{ pathname: to, state }] })
  const stepsBack = holdStepsBack(router)
  render(<RouterProvider router={router} />)
  return { router, stepsBack }
}

const click = (name: string) => act(async () => void fireEvent.click(screen.getByRole('button', { name })))

describe('useCloseComposer, before the step back has landed', () => {
  it('steps back once for an exit and for no other until the location has left the composer', async () => {
    const { router, stepsBack } = await openComposer()
    await click('Esc')
    await click('Esc')
    expect(stepsBack()).toBe(1)
    // The step back lands on Live and the composer is entered again (composer.test.tsx steps forward into it): the next exit is a new one.
    const { to, state } = composerLink()
    await act(() => router.navigate('/live'))
    await act(() => router.navigate(to, { state }))
    await click('Esc')
    expect(stepsBack()).toBe(2)
  })

  it('is not undone by a look chosen in the panel, which replaces the entry, or by a close from before it', async () => {
    const { router, stepsBack } = await openComposer()
    await click('Esc')
    // The choice gives the entry a key of its own and leaves its route as it was; the first render's close has the old key.
    const { to, state } = composerLink(null, 'embers')
    await act(() => router.navigate(to, { replace: true, state }))
    await click('Esc')
    await click("Esc, first render's")
    expect(stepsBack()).toBe(1)
  })

  it('is not undone by an instance that mounts while the exit is on its way', async () => {
    const { stepsBack } = await openComposer()
    await click('Esc')
    await click('Mount another')
    await click('Close')
    expect(stepsBack()).toBe(1)
  })

  it('is free again to an instance that mounts on Live once every instance has gone with an exit on its way', async () => {
    const first = await openComposer()
    await click('Esc')
    expect(first.stepsBack()).toBe(1)
    cleanup()
    const { stepsBack } = await openComposer()
    await click('Esc')
    expect(stepsBack()).toBe(1)
  })

  // Esc, then a rail click off Live (no instance is left to see the route change), then the step back landing on the composer: its
  // instances mount on the composer's route, which frees nothing, so the last instance going has to.
  it('is free again to an instance that mounts on the composer itself once every instance has gone with an exit on its way', async () => {
    const first = await openComposer()
    await click('Esc')
    expect(first.stepsBack()).toBe(1)
    cleanup()
    const { stepsBack } = openOnComposer()
    await click('Esc')
    expect(stepsBack()).toBe(1)
  })

  it('is not freed by an instance that goes while another stays', async () => {
    const { stepsBack } = await openComposer()
    await click('Mount another')
    await click('Esc')
    await click('Unmount another')
    await click('Esc')
    expect(stepsBack()).toBe(1)
  })
})
