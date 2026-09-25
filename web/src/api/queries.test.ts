import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Light, Zone } from './contract'
import { applyMessage, createLiveStore } from './live-store'
import { createQueryClient, queries, refetchOnNews, resync } from './queries'

const fetchMock = vi.fn<typeof fetch>()

beforeEach(() => {
  fetchMock.mockReset()
  fetchMock.mockImplementation(async () => Response.json([{ id: 'fireflies' }]))
  vi.stubGlobal('fetch', fetchMock)
})

describe('queries', () => {
  it('fetch through the REST client once, and again after a resync', async () => {
    const client = createQueryClient()
    expect(await client.fetchQuery(queries.looks())).toEqual([{ id: 'fireflies' }])
    await client.fetchQuery(queries.looks())
    expect(fetchMock).toHaveBeenCalledTimes(1)
    await resync(client)
    await client.fetchQuery(queries.looks())
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('key each look apart, under the looks', () => {
    expect(queries.look('a').queryKey).not.toEqual(queries.look('b').queryKey)
    expect(queries.look('a').queryKey[0]).toBe(queries.looks().queryKey[0])
  })
})

// I6: the socket pushes what runs and the lights' status; the rest comes from REST, and must not
// stay stale for good.
describe('REST data that changes elsewhere', () => {
  it('goes stale after a while, and refetches when the window regains focus', () => {
    for (const { staleTime, refetchOnWindowFocus } of [queries.looks(), queries.zones(), queries.home()]) {
      expect(staleTime).toBeGreaterThan(0)
      expect(staleTime).toBeLessThan(Infinity)
      expect(refetchOnWindowFocus).toBe(true)
    }
  })

  it('refetches the zones when what runs names a zone it has never seen', () => {
    const store = createLiveStore()
    const client = createQueryClient()
    client.setQueryData(queries.zones().queryKey, [{ id: 'living' }] as Zone[])
    const invalidate = vi.spyOn(client, 'invalidateQueries')
    const stop = refetchOnNews(store, client)
    const running = (zoneId: string) => ({ zoneId, lookId: 'x', lookName: 'X', since: '', brightness: 1, lights: [], covers: [], state: 'running' as const })
    applyMessage(store, { channel: 'running', zones: [running('living')] }, 0)
    expect(invalidate).not.toHaveBeenCalled()
    applyMessage(store, { channel: 'running', zones: [running('living'), running('group-9')] }, 0)
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['zones'] })
    stop()
  })

  it('refetches the lights when a lights snapshot adds or removes one', () => {
    const store = createLiveStore()
    const client = createQueryClient()
    client.setQueryData(queries.lights().queryKey, [{ id: 'a' }, { id: 'b' }] as Light[])
    const invalidate = vi.spyOn(client, 'invalidateQueries')
    const stop = refetchOnNews(store, client)
    const lights = (...ids: string[]) => ids.map((id) => ({ id, status: 'idle' as const, statusSince: '' }))
    applyMessage(store, { channel: 'lights', lights: lights('b', 'a') }, 0)
    expect(invalidate).not.toHaveBeenCalled()
    applyMessage(store, { channel: 'lights', lights: lights('a', 'b', 'c') }, 0)
    expect(invalidate).toHaveBeenLastCalledWith({ queryKey: ['lights'] })
    invalidate.mockClear()
    applyMessage(store, { channel: 'lights', lights: lights('a') }, 0)
    expect(invalidate).toHaveBeenLastCalledWith({ queryKey: ['lights'] })
    stop()
  })
})
