import { act, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { attentionAbout } from '@/test/live'
import type { Deck, RunningZone } from './contract'
import {
  EMPTY_LIVE, applyMessage, createLiveStore, liveStore, resetLiveStore, useLive, type LiveState, type LiveStore,
} from './live-store'
import type { DeviceStat, LightStat, ServerMessage } from './ws-messages'

const ZONE: RunningZone = {
  zoneId: 'zone-a',
  lookId: 'look-a',
  lookName: 'Look A',
  since: '2026-09-23T19:05:00Z',
  brightness: 0.7,
  lights: ['a'],
  covers: ['Room A'],
  state: 'running',
}
const ITEM = attentionAbout('light', 'a')
const STAT: DeviceStat = {
  id: 'a',
  name: 'A',
  send_fps: 60,
  latency_ms: 50,
  frames_dropped: 0,
  dropped_pct: 0,
  connected: true,
  status: 'online',
}
const DECK: Deck = { number: 2, player: 'Player 2', state: 'playing', bpm: 124, pitch_percent: 1.2, master: true }

let store: LiveStore
beforeEach(() => {
  store = createLiveStore()
})

describe('applyMessage', () => {
  it('starts out knowing nothing', () => {
    expect(store.getState()).toEqual(EMPTY_LIVE)
  })

  it.each<[string, ServerMessage, Partial<LiveState>]>([
    ['running', { channel: 'running', zones: [ZONE] }, { running: { zones: [ZONE], overlays: [] } }],
    [
      'lights',
      { channel: 'lights', lights: [{ id: 'a', status: 'offline', statusSince: '2026-09-23T17:02:00Z' }] },
      { lights: { a: { id: 'a', status: 'offline', statusSince: '2026-09-23T17:02:00Z' } } },
    ],
    ['attention', { channel: 'attention', items: [ITEM] }, { attention: [ITEM] }],
    ['transport', { channel: 'transport', state: 'simulating' }, { previewOnly: true }],
    ['stats', { channel: 'stats', devices: [STAT] }, { stats: { a: STAT } }],
    ['decks', { channel: 'decks', decks: [DECK] }, { decks: [DECK] }],
    ['signals', { channel: 'signals', values: { loudness: 0.5 } }, { signals: { loudness: 0.5 } }],
  ])('stores %s', (_, message, expected) => {
    applyMessage(store, message, 0)
    expect(store.getState()).toMatchObject(expected)
  })

  // I2: engine M2 keeps `devices` per device and adds §12.4's per-light `lights`.
  it("keys the stats by light when the server sends §12.4's lights", () => {
    const light: LightStat = { id: 'rope', send_fps: 60, latency_ms: 42, dropped_pct: 0.5 }
    applyMessage(store, { channel: 'stats', devices: [STAT], lights: [light] }, 0)
    expect(store.getState().stats).toEqual({ rope: light })
  })

  it('reads transport "playing" as preview only off', () => {
    applyMessage(store, { channel: 'transport', state: 'playing' }, 0)
    expect(store.getState().previewOnly).toBe(false)
  })

  it('normalises the beat', () => {
    const v1 = {
      channel: 'beat', bpm: 120, beat_phase: 0, bar_phase: 0, is_playing: true, beat_pos: 1,
      pitch_percent: 0, deck_number: null, deck_name: null,
    } as const
    applyMessage(store, v1, 5)
    expect(store.getState().beat).toMatchObject({ bpm: 120, source: 'prodjlink', bar: null, receivedAt: 5 })
  })

  it('changes nothing for channels it does not keep', () => {
    const messages = [
      { channel: 'ack', id: 1, action: 'subscribe_beat' },
      { channel: 'error', detail: 'Unknown action: x' },
      { channel: 'status', ok: true, device_count: 1, avg_render_ms: 1, transport: 'playing' },
      { channel: 'fx' },
      { channel: 'later' },
    ] as ServerMessage[]
    for (const message of messages) applyMessage(store, message, 0)
    expect(store.getState()).toEqual(EMPTY_LIVE)
  })
})

describe('the app store', () => {
  it('resets to knowing nothing', () => {
    applyMessage(liveStore, { channel: 'attention', items: [ITEM] }, 0)
    resetLiveStore()
    expect(liveStore.getState()).toEqual(EMPTY_LIVE)
  })

  it('re-renders a reader only when its slice changes', () => {
    const rendered = vi.fn()
    function Count() {
      rendered()
      return <p>{useLive((state) => state.attention?.length ?? 'unknown')}</p>
    }
    render(<Count />)
    act(() => applyMessage(liveStore, { channel: 'transport', state: 'simulating' }, 0))
    expect(rendered).toHaveBeenCalledTimes(1)
    act(() => applyMessage(liveStore, { channel: 'attention', items: [ITEM] }, 0))
    expect(rendered).toHaveBeenCalledTimes(2)
    expect(screen.getByText('1')).toBeInTheDocument()
  })
})
