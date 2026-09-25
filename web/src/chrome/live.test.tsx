import { act, screen, within } from '@testing-library/react'
import { describe, expect, it, onTestFinished, vi } from 'vitest'
import { BeatClock } from '@/api/beat'
import { decodeFrame, encodeFrame, FrameStore } from '@/api/frames'
import { frames } from '@/api/live'
import { LiveClient } from '@/api/live-client'
import { applyMessage, liveStore } from '@/api/live-store'
import { beatMessage, statsMessage } from '@/api/mocks/mock-server'
import { buildScenario } from '@/api/mocks/scenarios'
import { renderApp } from '@/test/app'
import { renders, resetRenders } from '@/test/count-renders'
import { fakeSockets } from '@/test/fake-socket'
import { attentionAbout, HERO_NOW, seedLive } from '@/test/live'
import { countAttention } from './hooks'

// Each chrome part, and the top bar around them, counts its renders.
vi.mock('./tempo-module', async (importOriginal) => {
  const { counted } = await import('@/test/count-renders')
  const real = await importOriginal<typeof import('./tempo-module')>()
  return { ...real, TempoModule: counted('tempo', real.TempoModule) }
})
vi.mock('./attention-button', async (importOriginal) => {
  const { counted } = await import('@/test/count-renders')
  const real = await importOriginal<typeof import('./attention-button')>()
  return { ...real, AttentionButton: counted('attention', real.AttentionButton) }
})
vi.mock('./connection-indicator', async (importOriginal) => {
  const { counted } = await import('@/test/count-renders')
  const real = await importOriginal<typeof import('./connection-indicator')>()
  return { ...real, ConnectionIndicator: counted('connection', real.ConnectionIndicator) }
})
vi.mock('@/shell/top-bar', async (importOriginal) => {
  const { counted } = await import('@/test/count-renders')
  const real = await importOriginal<typeof import('@/shell/top-bar')>()
  return { ...real, TopBar: counted('topBar', real.TopBar) }
})

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
    const client = new LiveClient({
      url: 'ws://test/ws',
      store: liveStore,
      frames: new FrameStore(),
      beatClock: new BeatClock(),
      openSocket: open,
    })
    client.start()
    onTestFinished(() => client.stop())
    renderApp('/next/live')

    act(() => sockets[0].drop())
    const bar = screen.getByRole('banner')
    expect(bar).toHaveTextContent('Reconnecting· try 1')
    expect(screen.getByRole('status')).toHaveTextContent(/^Reconnecting$/)
    expect(within(bar).queryByRole('button', { name: /All good|attention/ })).toBeNull()
    expect(within(bar).queryByRole('group', { name: 'Tempo' })).toBeNull()
  })

  // Review focus 3: engine M1 with no DJ sends a beat at 0 BPM, stopped, with no bar.
  it('holds the pips still when no DJ plays', () => {
    renderApp('/next/live')
    act(() => applyMessage(liveStore, beatMessage(hero, 0, 0, 1), 0))
    const tempo = within(screen.getByRole('banner')).getByRole('group', { name: 'Tempo' })
    expect(within(tempo).getByRole('button', { name: 'Pro DJ Link' })).toBeInTheDocument()
    expect(tempo).toHaveTextContent('0.0BPM')
    expect(within(tempo).queryByRole('img')).toBeNull()
    expect(tempo).not.toHaveTextContent(/bar \d/)
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
