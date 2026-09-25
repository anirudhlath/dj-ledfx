import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api, apiPath } from './rest'

const fetchMock = vi.fn<typeof fetch>()

function answer(status: number, body?: unknown) {
  fetchMock.mockResolvedValueOnce(
    new Response(body === undefined ? null : JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
}

beforeEach(() => {
  fetchMock.mockReset()
  // A new Response each time: a body can be read only once.
  fetchMock.mockImplementation(async () => new Response('{}', { status: 200 }))
  vi.stubGlobal('fetch', fetchMock)
})

function sent() {
  const [url, init] = fetchMock.mock.calls[0] as [URL, RequestInit]
  return { url, method: init.method, body: init.body === undefined ? undefined : JSON.parse(String(init.body)) }
}

const CALLS: { name: string; run: () => Promise<unknown>; method: string; path: string; body?: unknown }[] = [
  { name: 'looks', run: () => api.looks(), method: 'GET', path: '/api/looks' },
  { name: 'look', run: () => api.look('fireflies'), method: 'GET', path: '/api/looks/fireflies' },
  { name: 'setStarred', run: () => api.setStarred('fireflies', true), method: 'PUT', path: '/api/looks/fireflies/starred', body: { starred: true } },
  { name: 'zones', run: () => api.zones(), method: 'GET', path: '/api/zones' },
  { name: 'running', run: () => api.running(), method: 'GET', path: '/api/running' },
  { name: 'start', run: () => api.start('living', { lookId: 'embers' }), method: 'POST', path: '/api/zones/living/start', body: { lookId: 'embers' } },
  { name: 'setBrightness', run: () => api.setBrightness('living', 0.7), method: 'PUT', path: '/api/zones/living/brightness', body: { value: 0.7 } },
  { name: 'off', run: () => api.off('living'), method: 'POST', path: '/api/zones/living/off' },
  { name: 'restart', run: () => api.restart('kitchen'), method: 'POST', path: '/api/zones/kitchen/restart' },
  { name: 'stopAll', run: () => api.stopAll(), method: 'POST', path: '/api/running/stop-all' },
  { name: 'lights', run: () => api.lights(), method: 'GET', path: '/api/lights' },
  { name: 'attention', run: () => api.attention(), method: 'GET', path: '/api/attention' },
  { name: 'setPreviewOnly', run: () => api.setPreviewOnly(true), method: 'PUT', path: '/api/config', body: { engine: { preview_only: true } } },
  { name: 'home', run: () => api.home(), method: 'GET', path: '/api/home' },
  { name: 'addAnchor', run: () => api.addAnchor({ name: 'Lamp', position: [1, 2, 0.5] }), method: 'POST', path: '/api/home/anchors', body: { name: 'Lamp', position: [1, 2, 0.5] } },
  { name: 'deleteSubZone', run: () => api.deleteSubZone('office'), method: 'DELETE', path: '/api/home/subzones/office' },
  {
    name: 'setPlacement',
    run: () => api.setPlacement('rope', { shape: { kind: 'point', position: [1, 2, 0] } }),
    method: 'PUT',
    path: '/api/lights/rope/placement',
    body: { shape: { kind: 'point', position: [1, 2, 0] } },
  },
  { name: 'confirmPlacement', run: () => api.confirmPlacement('rope'), method: 'POST', path: '/api/lights/rope/placement/confirm' },
  { name: 'guessPlacements', run: () => api.guessPlacements(), method: 'POST', path: '/api/lights/placement/guess' },
  { name: 'startPreview', run: () => api.startPreview({ zoneId: 'living', lookId: 'embers' }), method: 'POST', path: '/api/preview', body: { zoneId: 'living', lookId: 'embers' } },
  { name: 'stopPreview', run: () => api.stopPreview('preview-1'), method: 'DELETE', path: '/api/preview/preview-1' },
  { name: 'recentLooks', run: () => api.recentLooks(), method: 'GET', path: '/api/running/recent' },
  { name: 'inputs', run: () => api.inputs(), method: 'GET', path: '/api/inputs' },
  { name: 'signals', run: () => api.signals(), method: 'GET', path: '/api/signals' },
]

describe('api', () => {
  it.each(CALLS)('$name calls $method $path', async ({ run, method, path, body }) => {
    await run()
    expect(sent()).toMatchObject({ method, body })
    expect(sent().url.pathname).toBe(path)
  })

  it("sends absolute URLs on the page's own origin", async () => {
    await api.looks()
    expect(sent().url.origin).toBe(window.location.origin)
  })

  it('encodes path parameters', async () => {
    await api.look('a b/c')
    expect(sent().url.pathname).toBe('/api/looks/a%20b%2Fc')
  })

  it('returns the parsed body, and undefined for a 204', async () => {
    answer(200, [{ id: 'fireflies' }])
    expect(await api.looks()).toEqual([{ id: 'fireflies' }])
    answer(204)
    expect(await api.off('living')).toBeUndefined()
  })

  it("turns FastAPI's detail into an ApiError", async () => {
    answer(409, { detail: "Built-in looks can't be changed" })
    await expect(api.updateLook('fireflies', {} as never)).rejects.toMatchObject({
      name: 'ApiError',
      status: 409,
      detail: "Built-in looks can't be changed",
      path: '/api/looks/fireflies',
    })
  })

  it("joins a 422's problems into one detail", async () => {
    answer(422, { detail: [{ msg: 'Field required' }, { msg: 'Input should be a valid number' }] })
    await expect(api.setBrightness('living', Number.NaN)).rejects.toMatchObject({
      status: 422,
      detail: 'Field required; Input should be a valid number',
    })
  })

  it('falls back to the status text when the error body is not JSON', async () => {
    fetchMock.mockResolvedValueOnce(new Response('<html>', { status: 502, statusText: 'Bad Gateway' }))
    await expect(api.running()).rejects.toMatchObject({ status: 502, detail: 'Bad Gateway' })
  })

  it('reports no answer as status 0', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('fetch failed'))
    const error = await api.running().catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 0, detail: 'fetch failed' })
  })
})

describe('apiPath', () => {
  it('fills in every parameter', () => {
    expect(apiPath('/api/zones/{zone_id}/start', { zone_id: 'living' })).toBe('/api/zones/living/start')
  })

  it('throws when a parameter is missing', () => {
    expect(() => apiPath('/api/zones/{zone_id}/start')).toThrow('/api/zones/{zone_id}/start needs {zone_id}')
  })
})
