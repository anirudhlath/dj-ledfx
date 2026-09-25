import { act, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { decodeFrame, encodeFrame } from '@/api/frames'
import { frames, startDataLayer } from '@/api/live'
import { applyMessage, liveStore } from '@/api/live-store'
import { beatMessage, statsMessage } from '@/api/mocks/mock-server'
import { buildScenario } from '@/api/mocks/scenarios'
import { renderApp } from '@/test/app'
import { renders, resetRenders } from '@/test/count-renders'
import { fakeSockets } from '@/test/fake-socket'
import { attentionAbout, HERO_NOW, seedLive } from '@/test/live'
import { setViewportWidth } from '@/test/viewport'
import { countAttention } from './hooks'

// Each chrome part, and the top bar around them, counts its renders.
const { countedExport } = await vi.hoisted(() => import('@/test/count-renders'))
vi.mock('./tempo-module', countedExport('tempo', 'TempoModule'))
vi.mock('./attention-button', countedExport('attention', 'AttentionButton'))
vi.mock('./connection-indicator', countedExport('connection', 'ConnectionIndicator'))
vi.mock('@/shell/top-bar', countedExport('topBar', 'TopBar'))

const hero = buildScenario('hero', HERO_NOW)

describe('the chrome on the live store', () => {
  // F0 review: the chrome reads the stores a slice at a time, "so a beat doesn't re-render all of the chrome".
  it('redraws only the part whose slice changed', () => {
    seedLive()
    renderApp('/next/live')
    resetRenders()

    // A beat message inside the same beat changes nothing the chrome shows.
    act(() => applyMessage(liveStore, beatMessage(hero, 0.1, 0, 2), 0))
    expect(renders).toEqual({})

    // The next beat moves the pips: the tempo module alone redraws, not the bar around it.
    act(() => applyMessage(liveStore, beatMessage(hero, 0.5, 0, 2), 0))
    expect(renders).toEqual({ tempo: 1 })
    expect(screen.getByRole('img', { name: 'Beat 3 of 4' })).toBeInTheDocument()

    // Nothing needs attention any more: the attention button alone redraws, to All good.
    resetRenders()
    act(() => applyMessage(liveStore, { channel: 'attention', items: [] }, 0))
    expect(renders).toEqual({ attention: 1 })
    expect(screen.getByRole('button', { name: 'All good' })).toBeInTheDocument()

    // The devices' stats, and a second of frames for every light, redraw nothing.
    resetRenders()
    act(() => {
      applyMessage(liveStore, statsMessage(hero, 2), 0)
      for (let seq = 1; seq <= 60; seq++) {
        for (const light of hero.lights) {
          decodeFrame(encodeFrame(2, light.id, seq, new Uint8Array(light.leds * 3)), 2, frames, seq / 60)
        }
      }
    })
    expect(renders).toEqual({})
  })

  // Part 3 (E5): the phone header shows the link only while it isn't live.
  it("redraws nothing on the phone when the live frame rate changes", () => {
    setViewportWidth(390)
    seedLive()
    renderApp('/next/live')
    resetRenders()
    act(() => liveStore.setState({ connection: { status: 'live', fps: 42 } }))
    expect(renders).toEqual({})
  })

  // Review focus 2, and F0 review: never "All good" before the server's first data.
  it('shows no tempo, no All good and no Live before the server speaks', () => {
    renderApp('/next/live')
    const bar = screen.getByRole('banner')
    expect(within(bar).queryByRole('group', { name: 'Tempo' })).toBeNull()
    expect(within(bar).queryByRole('button', { name: /All good|attention/ })).toBeNull()
    // The title is the banner's only "Live".
    expect(within(bar).getAllByText('Live')).toEqual([within(bar).getByRole('heading', { level: 1 })])
    expect(screen.queryByText(', needs attention')).toBeNull()

    act(() => seedLive())
    expect(within(bar).getByRole('group', { name: 'Tempo' })).toHaveTextContent('121.8')
    expect(within(bar).getByRole('button', { name: '1 needs attention' })).toBeInTheDocument()
    expect(bar).toHaveTextContent('Live60 fps')
  })

  // Review focus 2: the server is down when the page loads.
  it('says Reconnecting, not All good, when the server is down from the start', () => {
    const { sockets, open } = fakeSockets()
    startDataLayer({ openSocket: open, url: 'ws://test/ws' })
    renderApp('/next/live')

    act(() => sockets[0].drop())
    const bar = screen.getByRole('banner')
    expect(bar).toHaveTextContent('Reconnecting· try 1')
    expect(screen.getByRole('status')).toHaveTextContent(/^Reconnecting$/)
    expect(within(bar).queryByRole('button', { name: /All good|attention/ })).toBeNull()
    expect(within(bar).queryByRole('group', { name: 'Tempo' })).toBeNull()
  })

  // Review focus 3: engine M1 with no DJ sends a beat at 0 BPM, stopped, with no bar. D2: that's
  // §9.3's Idle, "No DJ" in a quiet chip, not "Pro DJ Link 0.0".
  it('says No DJ, with no BPM and the pips still, when no DJ plays', () => {
    renderApp('/next/live')
    act(() => applyMessage(liveStore, beatMessage(hero, 0, 0, 1), 0))
    const tempo = within(screen.getByRole('banner')).getByRole('group', { name: 'Tempo' })
    expect(within(tempo).getByRole('button', { name: 'No DJ' })).toHaveClass('text-text-3')
    expect(tempo).not.toHaveTextContent(/Pro DJ Link|0\.0|BPM/)
    expect(within(tempo).queryByRole('img')).toBeNull()
    expect(tempo).not.toHaveTextContent(/bar/)
    expect(within(tempo).getByRole('button', { name: 'Tap' })).toBeInTheDocument()
  })

  // D3: preview only is the server's (its transport), not the fixture's.
  it("shows the server's preview only, and nothing before the server says", () => {
    renderApp('/next/live')
    const bar = screen.getByRole('banner')
    expect(within(bar).queryByRole('switch', { name: 'Preview only' })).toBeNull()
    act(() => applyMessage(liveStore, { channel: 'transport', state: 'simulating' }, 0))
    expect(within(bar).getByRole('switch', { name: 'Preview only' })).toBeChecked()
    act(() => applyMessage(liveStore, { channel: 'transport', state: 'playing' }, 0))
    expect(within(bar).getByRole('switch', { name: 'Preview only' })).not.toBeChecked()
  })
})

describe('countAttention', () => {
  it('counts every item, and the lights and the inputs apart', () => {
    const items = [
      attentionAbout('light', 'rope'),
      attentionAbout('zone', 'kitchen'),
      attentionAbout('input', 'music'),
      attentionAbout('light', 'tube'),
    ]
    expect(countAttention(items)).toEqual({ total: 4, lights: 2, inputs: 1 })
    expect(countAttention([])).toEqual({ total: 0, lights: 0, inputs: 0 })
  })
})
