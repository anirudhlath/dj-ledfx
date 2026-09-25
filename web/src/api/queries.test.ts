import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createQueryClient, queries, resync } from './queries'

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
