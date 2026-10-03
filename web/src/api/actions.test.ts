import { describe, expect, it, vi } from 'vitest'
import { seedLive } from '@/test/live'
import { failureText, setBrightness, setTempoLock, startAgain, tapTempo } from './actions'
import { liveStore } from './live-store'
import { queries, queryClient } from './queries'
import { api, ApiError } from './rest'

const zone = (id: string) => liveStore.getState().running!.zones.find((candidate) => candidate.zoneId === id)!

describe('actions', () => {
  // F3 decision 8: the control shows the server's answer without waiting for the push.
  it('puts the zone the server answers with in the store at once', async () => {
    seedLive()
    vi.spyOn(api, 'setBrightness').mockResolvedValue({ ...zone('living'), brightness: 0.4 })
    await setBrightness('living', 0.4)
    expect(api.setBrightness).toHaveBeenCalledWith('living', 0.4)
    expect(zone('living').brightness).toBe(0.4)
  })

  it('locks the tempo, and keeps the tempo the server answers with', async () => {
    seedLive()
    const tempo = { ...liveStore.getState().inputs!.tempo, lock: 'internal' as const }
    vi.spyOn(api, 'setTempo').mockResolvedValue(tempo)
    await setTempoLock('internal')
    expect(api.setTempo).toHaveBeenCalledWith({ lock: 'internal' })
    expect(liveStore.getState().inputs!.tempo).toEqual(tempo)
  })

  // F3 decision 5: epoch seconds, as engine M3's TapRequest says.
  it('taps over REST, with the time in epoch seconds, while there is no link', async () => {
    vi.useFakeTimers({ now: new Date('2026-09-23T19:14:00-05:00') })
    seedLive()
    vi.spyOn(api, 'tap').mockResolvedValue(liveStore.getState().inputs!.tempo)
    await tapTempo()
    expect(api.tap).toHaveBeenCalledWith(Date.now() / 1000)
  })

  it('reads "Start again" afresh after starting a look from it', async () => {
    vi.spyOn(api, 'start').mockResolvedValue({ zoneId: 'living', lookId: 'fireflies' } as never)
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries')
    await startAgain({ zoneId: 'living', lookId: 'fireflies' })
    expect(api.start).toHaveBeenCalledWith('living', { lookId: 'fireflies' })
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queries.recentLooks().queryKey })
  })

  // Review Focus 1.
  it("says what failed, in the server's words, or that it didn't answer", () => {
    expect(failureText('turn off Living room', new ApiError(409, 'Living room is not running', '/api/zones/living/off'))).toBe(
      "Couldn't turn off Living room. Living room is not running",
    )
    expect(failureText('turn off Living room', new ApiError(0, 'Failed to fetch', '/api/zones/living/off'))).toBe(
      "Couldn't turn off Living room. The server didn't answer.",
    )
    expect(failureText('tap the tempo', new Error('The tempo is locked to Pro DJ Link: choose Auto or Internal to set it here'))).toBe(
      "Couldn't tap the tempo. The tempo is locked to Pro DJ Link: choose Auto or Internal to set it here",
    )
  })
})
