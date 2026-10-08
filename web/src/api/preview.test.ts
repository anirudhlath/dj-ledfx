import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fakeSockets } from '@/test/fake-socket'
import { HERO_NOW, pushFrame, restOn, startMockDataLayer } from '@/test/live'
import { startLook } from './actions'
import type { PreviewStarted } from './contract'
import { FrameStore } from './frames'
import { frames, previewSession, startDataLayer } from './live'
import type { LiveClient } from './live-client'
import { PreviewSession } from './preview'
import { api, ApiError } from './rest'

const CUT = { kind: 'cut', durationS: 0 } as const

/** A request held open until the test answers it. */
function held<T>() {
  let resolve: (value: T) => void = () => {}
  let reject: (error: unknown) => void = () => {}
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

const started = (previewId: string): PreviewStarted => ({ previewId, lights: [] })

/** A session over its own frame store and a client that records what it subscribes to. */
function session() {
  const store = new FrameStore()
  const subscribeFrames = vi.fn()
  const preview = new PreviewSession({ frames: store, client: () => ({ subscribeFrames }) as unknown as LiveClient })
  return { preview, store, subscribeFrames }
}

describe('the preview', () => {
  beforeEach(() => {
    vi.spyOn(api, 'stopPreview').mockResolvedValue(undefined)
  })

  // §13.1 F4's exit check: "lights unchanged until Start (mock asserts)".
  it('draws the look on the preview stream and leaves the lights alone until Start', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(HERO_NOW)
    vi.mocked(api.stopPreview).mockRestore()
    const server = startMockDataLayer()
    restOn(server)
    await vi.advanceTimersByTimeAsync(1100)
    const running = structuredClone(server.state.running)
    const lights = structuredClone(server.state.lights)
    const living = server.state.zones.find((zone) => zone.id === 'living')!

    previewSession.show('living', 'embers')
    await vi.advanceTimersByTimeAsync(500)
    expect(previewSession.snapshot()).toMatchObject({ status: 'on', zoneId: 'living', lookId: 'embers', showing: 'living' })
    expect(previewSession.snapshot().lights!.map((light) => light.id)).toEqual(living.lights)
    for (const id of living.lights) expect(frames.get(id, 'preview')).toBeDefined()
    expect(server.state.running).toEqual(running)
    expect(server.state.lights).toEqual(lights)

    await startLook('living', 'embers', CUT)
    expect(server.state.running.find((zone) => zone.zoneId === 'living')?.lookId).toBe('embers')
  })

  it('asks for one preview at a time, and the last choice wins', async () => {
    const { preview } = session()
    const first = held<PreviewStarted>()
    const ask = vi.spyOn(api, 'startPreview').mockReturnValueOnce(first.promise).mockResolvedValueOnce(started('p2'))
    preview.show('living', 'embers')
    preview.show('living', 'aurora')
    preview.show('kitchen', 'lava')
    expect(ask).toHaveBeenCalledTimes(1)
    expect(preview.snapshot()).toMatchObject({ status: 'starting', zoneId: 'kitchen', lookId: 'lava' })

    first.resolve(started('p1'))
    await vi.waitFor(() => expect(preview.snapshot().status).toBe('on'))
    expect(ask).toHaveBeenCalledTimes(2)
    expect(ask).toHaveBeenLastCalledWith({ zoneId: 'kitchen', lookId: 'lava' })
    expect(preview.snapshot()).toMatchObject({ zoneId: 'kitchen', lookId: 'lava', showing: 'kitchen' })
  })

  it('watches the preview stream only while a preview is open', async () => {
    const { preview, subscribeFrames } = session()
    vi.spyOn(api, 'startPreview').mockResolvedValue(started('p1'))
    preview.show('living', 'embers')
    expect(subscribeFrames).toHaveBeenLastCalledWith(['live', 'preview'])
    await vi.waitFor(() => expect(preview.snapshot().status).toBe('on'))
    preview.show('living', 'aurora')
    await vi.waitFor(() => expect(preview.snapshot()).toMatchObject({ status: 'on', lookId: 'aurora' }))
    expect(subscribeFrames).toHaveBeenCalledTimes(1)
    preview.stop()
    expect(subscribeFrames).toHaveBeenLastCalledWith(['live'])
    expect(api.stopPreview).toHaveBeenCalledWith('p1')
  })

  it("ends the server's preview when stopped, even one still on its way", async () => {
    const { preview } = session()
    const first = held<PreviewStarted>()
    vi.spyOn(api, 'startPreview').mockReturnValueOnce(first.promise)
    preview.show('living', 'embers')
    preview.stop()
    expect(preview.snapshot().status).toBe('idle')
    first.resolve(started('p1'))
    await vi.waitFor(() => expect(api.stopPreview).toHaveBeenCalledWith('p1'))
    expect(preview.snapshot().status).toBe('idle')
  })

  it('previews the same look again after a stop', async () => {
    const { preview } = session()
    const ask = vi.spyOn(api, 'startPreview').mockResolvedValue(started('p1'))
    preview.show('living', 'embers')
    await vi.waitFor(() => expect(preview.snapshot().status).toBe('on'))
    preview.stop()
    preview.show('living', 'embers')
    await vi.waitFor(() => expect(preview.snapshot().status).toBe('on'))
    expect(ask).toHaveBeenCalledTimes(2)
  })

  // F4 ruling 3: the engine refuses a whole-home look until M6.
  it("says why the server refused, ends the preview before, and doesn't ask again", async () => {
    const { preview, store } = session()
    const refused = new ApiError(400, 'Home looks (whole-home scope) arrive in M6', '/api/preview')
    const ask = vi.spyOn(api, 'startPreview').mockResolvedValueOnce(started('p1')).mockRejectedValueOnce(refused)
    preview.show('home', 'embers')
    await vi.waitFor(() => expect(preview.snapshot().status).toBe('on'))
    pushFrame('a-light', 1, [1, 2, 3], { store, stream: 'preview' })

    preview.show('home', 'wisp')
    await vi.waitFor(() => expect(preview.snapshot().status).toBe('failed'))
    expect(preview.snapshot()).toMatchObject({ zoneId: 'home', lookId: 'wisp', error: refused, showing: null, lights: null })
    expect(api.stopPreview).toHaveBeenCalledWith('p1')
    expect(store.preview.size).toBe(0)

    preview.show('home', 'wisp')
    expect(ask).toHaveBeenCalledTimes(2)
  })

  it("keeps drawing a zone's preview while the next look on it starts, and drops it for another zone", async () => {
    const { preview, store } = session()
    const second = held<PreviewStarted>()
    vi.spyOn(api, 'startPreview').mockResolvedValueOnce(started('p1')).mockReturnValueOnce(second.promise)
    preview.show('living', 'embers')
    await vi.waitFor(() => expect(preview.snapshot().status).toBe('on'))
    pushFrame('a-light', 1, [1, 2, 3], { store, stream: 'preview' })

    preview.show('living', 'aurora')
    expect(preview.snapshot()).toMatchObject({ status: 'starting', showing: 'living' })
    expect(store.preview.size).toBe(1)

    preview.show('kitchen', 'aurora')
    expect(preview.snapshot()).toMatchObject({ status: 'starting', showing: null })
    expect(store.preview.size).toBe(0)
    second.resolve(started('p2'))
  })

  // Review focus 4: the engine ends a preview nobody watched for 10 s, and a restarted server holds none.
  it('asks for the preview again when the link comes back', async () => {
    vi.useFakeTimers()
    const { sockets, open } = fakeSockets()
    const latest = () => sockets[sockets.length - 1]
    const welcome = () => {
      latest().open()
      latest().say({ channel: 'transport', state: 'playing' })
      latest().say({ channel: 'ack', id: latest().idOf('subscribe_frames'), action: 'subscribe_frames', protocol: 2, fps: 60 })
    }
    startDataLayer({ openSocket: open, url: 'ws://test/ws' })
    welcome()
    const ask = vi.spyOn(api, 'startPreview').mockResolvedValueOnce(started('p1')).mockResolvedValueOnce(started('p2'))
    previewSession.show('living', 'embers')
    await vi.waitFor(() => expect(previewSession.snapshot().status).toBe('on'))

    latest().drop()
    await vi.advanceTimersByTimeAsync(1000)
    welcome()
    await vi.waitFor(() => expect(ask).toHaveBeenCalledTimes(2))
    expect(ask).toHaveBeenLastCalledWith({ zoneId: 'living', lookId: 'embers' })
    expect(previewSession.snapshot()).toMatchObject({ status: 'on', zoneId: 'living', showing: 'living' })
    // The new socket watches the preview stream too.
    expect(latest().sent.findLast((command) => command.action === 'subscribe_frames')).toMatchObject({ streams: ['live', 'preview'] })

    // With no preview wanted, a reconnect asks for none.
    previewSession.stop()
    latest().drop()
    await vi.advanceTimersByTimeAsync(1000)
    welcome()
    await Promise.resolve()
    expect(ask).toHaveBeenCalledTimes(2)
  })

  it('drops an answer to a request made before a reset', async () => {
    const { preview } = session()
    const first = held<PreviewStarted>()
    vi.spyOn(api, 'startPreview').mockReturnValueOnce(first.promise)
    preview.show('living', 'embers')
    preview.reset()
    first.resolve(started('p1'))
    await Promise.resolve()
    await Promise.resolve()
    expect(preview.snapshot().status).toBe('idle')
  })

  // Review focus 1: the stage shows the last choice, never the answer to one it replaced.
  it("waits for the last choice's own answer, not the answer to one it replaced", async () => {
    const { preview } = session()
    const first = held<PreviewStarted>()
    const second = held<PreviewStarted>()
    const ask = vi.spyOn(api, 'startPreview').mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
    preview.show('living', 'embers')
    preview.show('kitchen', 'lava')

    first.resolve(started('p1'))
    await vi.waitFor(() => expect(ask).toHaveBeenCalledTimes(2))
    expect(preview.snapshot()).toMatchObject({ status: 'starting', zoneId: 'kitchen', lookId: 'lava', lights: null, showing: null })

    const plan = [{ id: 'a-light', mode: 'streaming' as const, effect: null }]
    second.resolve({ previewId: 'p2', lights: plan })
    await vi.waitFor(() => expect(preview.snapshot().status).toBe('on'))
    expect(preview.snapshot()).toMatchObject({ zoneId: 'kitchen', lookId: 'lava', lights: plan, showing: 'kitchen' })
  })

  // Review focus 1: nor does the refusal of a replaced choice show, or end the watching that the next choice's preview needs.
  it('neither says nor acts on the refusal of a choice it replaced', async () => {
    const { preview, subscribeFrames } = session()
    const first = held<PreviewStarted>()
    const second = held<PreviewStarted>()
    const ask = vi.spyOn(api, 'startPreview').mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
    preview.show('home', 'wisp')
    preview.show('living', 'embers')

    first.reject(new ApiError(400, 'Home looks (whole-home scope) arrive in M6', '/api/preview'))
    await vi.waitFor(() => expect(ask).toHaveBeenCalledTimes(2))
    expect(preview.snapshot()).toMatchObject({ status: 'starting', zoneId: 'living', lookId: 'embers', error: null })
    expect(subscribeFrames).toHaveBeenLastCalledWith(['live', 'preview'])

    second.resolve(started('p2'))
    await vi.waitFor(() => expect(preview.snapshot().status).toBe('on'))
    expect(preview.snapshot()).toMatchObject({ zoneId: 'living', lookId: 'embers', error: null })
  })

  // Review focus 1: a reset leaves nothing on its way to answer, even when the same look is chosen again after it.
  it.each(['answer', 'refusal'])('drops the %s to a request made before a reset, even when the same choice is made again', async (kind) => {
    const { preview } = session()
    const first = held<PreviewStarted>()
    const second = held<PreviewStarted>()
    const ask = vi.spyOn(api, 'startPreview').mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
    preview.show('living', 'embers')
    preview.reset()
    preview.show('living', 'embers')
    expect(ask).toHaveBeenCalledTimes(2)

    if (kind === 'answer') first.resolve(started('p1'))
    else first.reject(new ApiError(400, 'Home looks (whole-home scope) arrive in M6', '/api/preview'))
    await new Promise<void>((resolve) => setTimeout(resolve, 0))
    expect(preview.snapshot()).toMatchObject({ status: 'starting', error: null })

    second.resolve(started('p2'))
    await vi.waitFor(() => expect(preview.snapshot().status).toBe('on'))
  })

  // Review focus 4: a choice that failed while the link was down stops the preview stream's watching; asked for again, it's watched again.
  it('watches the preview stream again when a choice that failed is asked for after the link comes back', async () => {
    const { preview, subscribeFrames } = session()
    const ask = vi
      .spyOn(api, 'startPreview')
      .mockRejectedValueOnce(new ApiError(0, 'Failed to fetch', '/api/preview'))
      .mockResolvedValueOnce(started('p1'))
    preview.show('living', 'embers')
    await vi.waitFor(() => expect(preview.snapshot().status).toBe('failed'))
    expect(subscribeFrames).toHaveBeenLastCalledWith(['live'])

    preview.resume()
    expect(subscribeFrames).toHaveBeenLastCalledWith(['live', 'preview'])
    await vi.waitFor(() => expect(preview.snapshot().status).toBe('on'))
    expect(ask).toHaveBeenCalledTimes(2)
    expect(preview.snapshot()).toMatchObject({ zoneId: 'living', lookId: 'embers', showing: 'living' })
  })

  // Review focus 4: and with no preview wanted, a reconnect neither asks for one nor watches its stream.
  it('asks for nothing and watches nothing when the link comes back with no preview wanted', () => {
    const { preview, subscribeFrames } = session()
    const ask = vi.spyOn(api, 'startPreview')
    preview.resume()
    expect(ask).not.toHaveBeenCalled()
    expect(subscribeFrames).not.toHaveBeenCalled()
  })

  // Review focus 4: a deep link opens the composer before the link has ever been up, and the first connect resumes it too.
  it('asks for a preview that failed before the link was ever up when the link first comes up', async () => {
    const { sockets, open } = fakeSockets()
    startDataLayer({ openSocket: open, url: 'ws://test/ws' })
    const ask = vi
      .spyOn(api, 'startPreview')
      .mockRejectedValueOnce(new ApiError(0, 'Failed to fetch', '/api/preview'))
      .mockResolvedValueOnce(started('p1'))
    previewSession.show('living', 'embers')
    await vi.waitFor(() => expect(previewSession.snapshot().status).toBe('failed'))

    sockets[0].open()
    sockets[0].say({ channel: 'transport', state: 'playing' })
    await vi.waitFor(() => expect(previewSession.snapshot().status).toBe('on'))
    expect(ask).toHaveBeenCalledTimes(2)
    expect(ask).toHaveBeenLastCalledWith({ zoneId: 'living', lookId: 'embers' })
    expect(previewSession.snapshot()).toMatchObject({ zoneId: 'living', lookId: 'embers', showing: 'living' })
    // The socket subscribed to the live stream alone as it opened, and watches the preview's once the link is up.
    expect(sockets[0].sent.filter((command) => command.action === 'subscribe_frames')).toMatchObject([
      { streams: ['live'] },
      { streams: ['live', 'preview'] },
    ])
  })
})
