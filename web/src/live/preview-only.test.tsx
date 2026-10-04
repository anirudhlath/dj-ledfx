import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { liveStore } from '@/api/live-store'
import { api, ApiError } from '@/api/rest'
import { Announcer } from '@/design/announcer'
import { LIVE_SPEC } from '@/design/live-numbers'
import { renderApp } from '@/test/app'
import { HERO_NOW, seedLive } from '@/test/live'
import { seedRest } from '@/test/rest'
import { setViewportWidth } from '@/test/viewport'
import { PreviewOnlyBanner } from './preview-only'

const frame = () => document.querySelector<HTMLElement>('[data-tape="frame"]')
const SENTENCE = 'Everything renders here. Nothing is sent to the lights.'

describe('preview only', () => {
  // §5.6: "It must be impossible to miss." State-Preview-Only.
  it('tapes the window, labels the stage and bars the panel, and the label sends the lights back', async () => {
    seedRest('preview-only')
    seedLive('preview-only')
    const send = vi.spyOn(api, 'setPreviewOnly').mockResolvedValue({ engine: { preview_only: false } })
    renderApp('/next/live')
    expect(frame()).not.toBeNull()
    expect(frame()!.firstElementChild).toHaveStyle({ height: `${LIVE_SPEC.tape.framePx}px` })
    expect(document.querySelector('[data-tape="bar"]')).toHaveStyle({ height: `${LIVE_SPEC.tape.panelBarPx}px` })
    expect(within(screen.getByRole('complementary', { name: 'Running' })).getByText(/on screen only/)).toBeInTheDocument()
    const label = screen.getByText(SENTENCE).closest('div')!.parentElement!
    // State-Preview-Only.html sizes it content-box: 48 high. The stage's tools and sun readout start under it.
    expect(label).toHaveClass('h-12')
    expect(label.parentElement!.style.getPropertyValue('--stage-top-shift')).toBe('66px')
    await userEvent.click(within(label).getByRole('button', { name: 'Send to lights again' }))
    expect(send).toHaveBeenCalledWith(false)
    // The server's transport push turns it off: everything goes.
    act(() => liveStore.setState({ previewOnly: false }))
    expect(frame()).toBeNull()
    expect(document.querySelector('[data-tape="bar"]')).toBeNull()
    expect(screen.queryByText(SENTENCE)).toBeNull()
  })

  // Review Focus 1: the switch shows the server's state, so a refused change never moves it.
  it('holds the switch while the change is on its way, and says why it was refused', async () => {
    seedLive('hero')
    let refuse!: (error: unknown) => void
    vi.spyOn(api, 'setPreviewOnly').mockReturnValue(new Promise((_, reject) => (refuse = reject)))
    renderApp('/next/devices')
    const toggle = within(screen.getByRole('banner')).getByRole('switch', { name: 'Preview only' })
    await userEvent.click(toggle)
    expect(toggle).toBeDisabled()
    await act(async () => refuse(new ApiError(409, 'A backup is being restored.', '/api/config')))
    expect(toggle).toBeEnabled()
    expect(toggle).toHaveAttribute('aria-checked', 'false')
    expect(screen.getByText("Couldn't turn preview only on. A backup is being restored.")).toBeInTheDocument()
  })

  // Phone-State-Preview-Only: a thinner frame, and the context line says so.
  it('tapes the phone thinner, and says so under the title', () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(HERO_NOW)
    setViewportWidth(390)
    seedRest('preview-only')
    seedLive('preview-only')
    renderApp('/next/live')
    expect(frame()!.firstElementChild).toHaveStyle({ height: `${LIVE_SPEC.tape.phoneFramePx}px` })
    expect(within(screen.getByRole('banner')).getByText('Wed 19:14 · on screen only')).toBeInTheDocument()
  })

  // Phone-State-Preview-Only's banner; Task 18 puts it under the phone's stage.
  it("the phone's banner turns preview only off", async () => {
    seedLive('preview-only')
    const send = vi.spyOn(api, 'setPreviewOnly').mockResolvedValue({ engine: { preview_only: false } })
    render(
      <Announcer news="">
        <PreviewOnlyBanner />
      </Announcer>,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Turn off preview only' }))
    expect(send).toHaveBeenCalledWith(false)
  })
})
