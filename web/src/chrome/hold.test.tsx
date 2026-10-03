import { act, fireEvent, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { TempoInput } from '@/api/contract'
import { api } from '@/api/rest'
import { renderApp } from '@/test/app'
import { HERO_NOW, startMockDataLayer } from '@/test/live'

const settle = () => act(() => vi.advanceTimersByTimeAsync(100))

async function click(element: HTMLElement) {
  fireEvent.click(element)
  await settle()
}

const tempo = () => within(screen.getByRole('banner')).getByRole('group', { name: 'Tempo' })
const popover = () => screen.getByRole('dialog', { name: 'Tempo source' })

describe('the hold (Review Focus 2)', () => {
  it('shows and announces the hold a tap starts during a DJ set, and its release', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(HERO_NOW)
    const server = startMockDataLayer({ scenario: 'dj-playing' })
    vi.spyOn(api, 'setTempo').mockImplementation(async (body) => server.handle('PUT', '/api/inputs/tempo', body).body as TempoInput)
    renderApp('/next/looks')
    await settle()
    expect(within(tempo()).getByRole('button', { name: 'Pro DJ Link' })).toBeInTheDocument()

    // A tap takes the tempo, and the page says so.
    await click(within(tempo()).getByRole('button', { name: 'Tap' }))
    expect(within(tempo()).getByRole('button', { name: 'Internal · held' })).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Tempo held on Internal')

    // Back to Auto hands it back.
    await click(within(tempo()).getByRole('button', { name: 'Internal · held' }))
    await click(within(popover()).getByRole('button', { name: 'Back to Auto' }))
    expect(within(tempo()).getByRole('button', { name: 'Pro DJ Link' })).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Tempo back to Pro DJ Link')

    // So does the DJ starting again after a pause.
    await click(within(tempo()).getByRole('button', { name: 'Tap' }))
    expect(within(tempo()).getByRole('button', { name: 'Internal · held' })).toBeInTheDocument()
    act(() => server.djStartsAgain())
    await settle()
    expect(within(tempo()).getByRole('button', { name: 'Pro DJ Link' })).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Tempo back to Pro DJ Link')

    // Under the Pro DJ Link lock TAP is disabled, as the engine would refuse it. TAP closed the popover, as
    // any press outside it does, so the source button opens it again.
    await click(within(tempo()).getByRole('button', { name: 'Pro DJ Link' }))
    await click(within(popover()).getByRole('button', { name: 'Pro DJ Link' }))
    expect(within(tempo()).getByRole('button', { name: 'Tap' })).toBeDisabled()
  })
})
