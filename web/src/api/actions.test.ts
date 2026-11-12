import { describe, expect, it, vi } from 'vitest'
import { seedLive } from '@/test/live'
import { seedRest } from '@/test/rest'
import { failureText, setBrightness, setStarred, setTempoLock, startAgain, startLook, tapTempo } from './actions'
import type { Look } from './contract'
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

  // F4 ruling 13: Live shows the started look before the push comes.
  it('puts a started look in the store as the newest, without the lights it took', async () => {
    seedLive()
    const home = zone('home')
    const taken = home.lights.slice(0, 2)
    vi.spyOn(api, 'start').mockResolvedValue({
      ...zone('living'),
      lookId: 'embers',
      takeOvers: [{ zoneId: 'home', zoneName: 'home', lookName: home.lookName, lights: taken, stopped: false }],
    })
    await startLook('living', 'embers', { kind: 'dissolve', durationS: 3 })
    expect(api.start).toHaveBeenCalledWith('living', { lookId: 'embers', transition: { kind: 'dissolve', durationS: 3 } })
    const zones = liveStore.getState().running!.zones
    expect(zones.map((candidate) => candidate.zoneId)).toEqual(['home', 'office', 'living'])
    expect(zone('living').lookId).toBe('embers')
    expect(zone('home').lights).toEqual(home.lights.filter((id) => !taken.includes(id)))
  })

  it('stops a zone in the store when a start takes all its lights', async () => {
    seedLive()
    const office = zone('office')
    vi.spyOn(api, 'start').mockResolvedValue({
      ...office,
      zoneId: 'bedroom',
      lookId: 'embers',
      takeOvers: [{ zoneId: 'office', zoneName: 'office', lookName: office.lookName, lights: office.lights, stopped: true }],
    })
    await startLook('bedroom', 'embers', { kind: 'cut', durationS: 0 })
    expect(liveStore.getState().running!.zones.map((candidate) => candidate.zoneId)).toEqual(['home', 'living', 'bedroom'])
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

/** A promise settled by hand, for an answer the test holds back. */
function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((done, fail) => {
    resolve = done
    reject = fail
  })
  return { promise, resolve, reject }
}

const cached = (id: string): Look => queryClient.getQueryData(queries.looks().queryKey)!.find((look) => look.id === id)!

// §8.4, F5 ruling 16, and the plan's Review Focus 3: a star shows at once, and the latest choice for a look wins.
describe('setStarred', () => {
  // One of the library's looks that Looks.png leaves unstarred.
  const ID = 'sunset'

  it("shows the star at once, then keeps the server's look", async () => {
    seedRest('library')
    const before = cached(ID)
    expect(before.starred).toBe(false)
    const answer = deferred<Look>()
    vi.spyOn(api, 'setStarred').mockReturnValue(answer.promise)
    const done = setStarred(ID, true)
    expect(api.setStarred).toHaveBeenCalledWith(ID, true)
    expect(cached(ID).starred).toBe(true)
    // What the server answers is what the cache keeps, not the choice it sent: a field the server changed comes with it.
    const served = { ...before, starred: true, description: 'as the server has it' }
    answer.resolve(served)
    await done
    expect(cached(ID)).toEqual(served)
  })

  it('lets the latest choice win when two answers come back out of order', async () => {
    seedRest('library')
    const before = cached(ID)
    const first = deferred<Look>()
    const second = deferred<Look>()
    vi.spyOn(api, 'setStarred').mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
    const star = setStarred(ID, true)
    const unstar = setStarred(ID, false)
    expect(cached(ID).starred).toBe(false)
    second.resolve({ ...before, starred: false })
    await unstar
    first.resolve({ ...before, starred: true })
    await star
    expect(cached(ID).starred).toBe(false)
  })

  it('puts the look back when the latest choice fails, and rejects with the ApiError', async () => {
    seedRest('library')
    const before = cached(ID)
    const answer = deferred<Look>()
    vi.spyOn(api, 'setStarred').mockReturnValue(answer.promise)
    const done = setStarred(ID, true)
    expect(cached(ID).starred).toBe(true)
    const error = new ApiError(500, 'Internal Server Error', `/api/looks/${ID}/starred`)
    answer.reject(error)
    await expect(done).rejects.toBe(error)
    expect(cached(ID)).toEqual(before)
  })

  it("doesn't put back over a later choice when an earlier one fails", async () => {
    seedRest('library')
    const before = cached(ID)
    const first = deferred<Look>()
    const second = deferred<Look>()
    vi.spyOn(api, 'setStarred').mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
    const star = setStarred(ID, true)
    const unstar = setStarred(ID, false)
    const error = new ApiError(500, 'Internal Server Error', `/api/looks/${ID}/starred`)
    first.reject(error)
    await expect(star).rejects.toBe(error)
    // The earlier choice failed, and the cache still shows the later one, which hasn't been answered.
    expect(cached(ID).starred).toBe(false)
    second.resolve({ ...before, starred: false })
    await unstar
    expect(cached(ID).starred).toBe(false)
  })

  // The put-back is the server's look, not the screen's: an earlier choice's star was only ever shown, never confirmed.
  it('puts back the look as it was before both when two choices in a row fail', async () => {
    seedRest('library')
    const before = cached(ID)
    const first = deferred<Look>()
    const second = deferred<Look>()
    vi.spyOn(api, 'setStarred').mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
    const star = setStarred(ID, true)
    const unstar = setStarred(ID, false)
    first.reject(new ApiError(0, 'Failed to fetch', `/api/looks/${ID}/starred`))
    await expect(star).rejects.toBeInstanceOf(ApiError)
    second.reject(new ApiError(0, 'Failed to fetch', `/api/looks/${ID}/starred`))
    await expect(unstar).rejects.toBeInstanceOf(ApiError)
    expect(cached(ID)).toEqual(before)
  })

  it('puts back what an earlier choice was answered with when the latest one fails', async () => {
    seedRest('library')
    const first = deferred<Look>()
    const second = deferred<Look>()
    vi.spyOn(api, 'setStarred').mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
    const star = setStarred(ID, true)
    const unstar = setStarred(ID, false)
    const served = { ...cached(ID), starred: true, description: 'as the server has it' }
    first.resolve(served)
    await star
    second.reject(new ApiError(500, 'Internal Server Error', `/api/looks/${ID}/starred`))
    await expect(unstar).rejects.toBeInstanceOf(ApiError)
    expect(cached(ID)).toEqual(served)
  })

  // F5 plan, Review Focus 3: the latest choice failed and was put back while an earlier one was still out, so the earlier answer is the
  // server's word, and the card shows it. Otherwise it ends unstarred over a server that has the star, under "Couldn't unstar".
  it("shows an earlier choice's answer that comes after the latest choice failed and was put back", async () => {
    seedRest('library')
    const before = cached(ID)
    const first = deferred<Look>()
    const second = deferred<Look>()
    vi.spyOn(api, 'setStarred').mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
    const star = setStarred(ID, true)
    const unstar = setStarred(ID, false)
    second.reject(new ApiError(0, 'Failed to fetch', `/api/looks/${ID}/starred`))
    await expect(unstar).rejects.toBeInstanceOf(ApiError)
    expect(cached(ID)).toEqual(before)
    first.resolve({ ...before, starred: true })
    await star
    expect(cached(ID).starred).toBe(true)
  })

  it("doesn't show an earlier choice's answer over a newer choice, even after an earlier put-back", async () => {
    seedRest('library')
    const before = cached(ID)
    const first = deferred<Look>()
    const second = deferred<Look>()
    const third = deferred<Look>()
    vi.spyOn(api, 'setStarred').mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise).mockReturnValueOnce(third.promise)
    const star = setStarred(ID, true)
    const unstar = setStarred(ID, false)
    second.reject(new ApiError(0, 'Failed to fetch', `/api/looks/${ID}/starred`))
    await expect(unstar).rejects.toBeInstanceOf(ApiError)
    // A new choice is on screen again, and it is the latest.
    const again = setStarred(ID, false)
    expect(cached(ID).starred).toBe(false)
    first.resolve({ ...before, starred: true })
    await star
    expect(cached(ID).starred).toBe(false)
    third.resolve({ ...before, starred: false })
    await again
    expect(cached(ID).starred).toBe(false)
  })

  // F5 final review, issue 2: a refetch that lands while the star is out brings the look's other fields, and a failed star is not a
  // reason to lose them.
  it("puts back only the star when a refetch changed the look while the request was out", async () => {
    seedRest('library')
    const before = cached(ID)
    const answer = deferred<Look>()
    vi.spyOn(api, 'setStarred').mockReturnValue(answer.promise)
    const done = setStarred(ID, true)
    // The refetch's look, as the server holds it: renamed, and not starred, as the request has not been answered.
    const refetched = { ...before, name: 'Renamed elsewhere', starred: false }
    queryClient.setQueryData(queries.looks().queryKey, (looks) => looks?.map((look) => (look.id === ID ? refetched : look)))
    answer.reject(new ApiError(500, 'Internal Server Error', `/api/looks/${ID}/starred`))
    await expect(done).rejects.toBeInstanceOf(ApiError)
    expect(cached(ID)).toEqual(refetched)
    expect(cached(ID).name).toBe('Renamed elsewhere')
    expect(cached(ID).starred).toBe(false)
  })

  it("puts back only the star in the look's own entry too", async () => {
    seedRest('library')
    const before = cached(ID)
    queryClient.setQueryData(queries.look(ID).queryKey, before)
    const answer = deferred<Look>()
    vi.spyOn(api, 'setStarred').mockReturnValue(answer.promise)
    const done = setStarred(ID, true)
    const refetched = { ...before, name: 'Renamed elsewhere', starred: false }
    queryClient.setQueryData(queries.look(ID).queryKey, refetched)
    answer.reject(new ApiError(500, 'Internal Server Error', `/api/looks/${ID}/starred`))
    await expect(done).rejects.toBeInstanceOf(ApiError)
    expect(queryClient.getQueryData(queries.look(ID).queryKey)).toEqual(refetched)
    expect(cached(ID)).toEqual(before)
  })

  it("lets an earlier answer's other fields land while a later choice is out, and keeps that choice's star", async () => {
    seedRest('library')
    const before = cached(ID)
    const first = deferred<Look>()
    const second = deferred<Look>()
    vi.spyOn(api, 'setStarred').mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
    const star = setStarred(ID, true)
    const unstar = setStarred(ID, false)
    first.resolve({ ...before, starred: true, description: 'as the server has it' })
    await star
    expect(cached(ID).description).toBe('as the server has it')
    expect(cached(ID).starred).toBe(false)
    second.resolve({ ...before, starred: false, description: 'as the server has it' })
    await unstar
    expect(cached(ID).starred).toBe(false)
  })

  // The order TanStack asks for an optimistic write: end the fetches first. A refetch asked for before the choice answers with the star as it
  // was, and would show it over the choice until the request is answered.
  describe('the fetches already on their way', () => {
    const detail = (id: string) => queryClient.getQueryData(queries.look(id).queryKey)
    const fetching = (queryKey: readonly unknown[]) => queryClient.isFetching({ queryKey, exact: true })

    it("ends the list's refetch, so its answer can't land over the star", async () => {
      seedRest('library')
      const before = cached(ID)
      const fetched = deferred<Look[]>()
      vi.spyOn(api, 'looks').mockReturnValue(fetched.promise)
      const refetch = queryClient.fetchQuery({ ...queries.looks(), staleTime: 0 })
      expect(fetching(queries.looks().queryKey)).toBe(1)
      const answer = deferred<Look>()
      vi.spyOn(api, 'setStarred').mockReturnValue(answer.promise)
      const done = setStarred(ID, true)
      expect(fetching(queries.looks().queryKey)).toBe(0)
      fetched.resolve(queryClient.getQueryData(queries.looks().queryKey)!.map((look) => (look.id === ID ? { ...before, starred: false } : look)))
      await refetch.catch(() => undefined)
      expect(cached(ID).starred).toBe(true)
      answer.resolve({ ...before, starred: true })
      await done
      expect(cached(ID).starred).toBe(true)
    })

    it("ends the look's own refetch too, and no other look's", async () => {
      seedRest('library')
      const before = cached(ID)
      const rain = cached('rain')
      queryClient.setQueryData(queries.look(ID).queryKey, before)
      queryClient.setQueryData(queries.look('rain').queryKey, rain)
      const own = deferred<Look>()
      const other = deferred<Look>()
      vi.spyOn(api, 'look').mockReturnValueOnce(own.promise).mockReturnValueOnce(other.promise)
      const refetch = queryClient.fetchQuery({ ...queries.look(ID), staleTime: 0 })
      const rainRefetch = queryClient.fetchQuery({ ...queries.look('rain'), staleTime: 0 })
      const answer = deferred<Look>()
      vi.spyOn(api, 'setStarred').mockReturnValue(answer.promise)
      const done = setStarred(ID, true)
      expect(fetching(queries.look(ID).queryKey)).toBe(0)
      expect(fetching(queries.look('rain').queryKey)).toBe(1)
      own.resolve({ ...before, starred: false })
      await refetch.catch(() => undefined)
      expect(detail(ID)?.starred).toBe(true)
      other.resolve({ ...rain, description: 'rain, refetched' })
      await rainRefetch
      expect(detail('rain')?.description).toBe('rain, refetched')
      answer.resolve({ ...before, starred: true })
      await done
    })

    it("leaves a fetch to finish where the cache holds nothing to write the star to", async () => {
      seedRest('library')
      const before = cached(ID)
      const fetched = deferred<Look>()
      vi.spyOn(api, 'look').mockReturnValue(fetched.promise)
      const first = queryClient.fetchQuery(queries.look(ID))
      const answer = deferred<Look>()
      vi.spyOn(api, 'setStarred').mockReturnValue(answer.promise)
      const done = setStarred(ID, true)
      expect(fetching(queries.look(ID).queryKey)).toBe(1)
      fetched.resolve(before)
      await first
      expect(detail(ID)).toEqual(before)
      answer.resolve({ ...before, starred: true })
      await done
    })
  })

  it("keeps each look's choices apart", async () => {
    seedRest('library')
    const other = deferred<Look>()
    const answer = deferred<Look>()
    vi.spyOn(api, 'setStarred').mockReturnValueOnce(other.promise).mockReturnValueOnce(answer.promise)
    const first = setStarred('rain', true)
    const second = setStarred(ID, true)
    other.resolve({ ...cached('rain'), starred: true, description: 'rain, as served' })
    await first
    // A later request for another look doesn't make the first one's answer stale.
    expect(cached('rain').description).toBe('rain, as served')
    answer.resolve({ ...cached(ID), starred: true })
    await second
    expect(cached(ID).starred).toBe(true)
  })

  // The look's own entry (`queries.look(id)`, keyed ['looks', id]) is the editor's to read; a star written on the list shows there too.
  describe("a look's own cache entry", () => {
    const detail = (id: string) => queryClient.getQueryData(queries.look(id).queryKey)

    it('shows the star at once, and keeps the look the server answers with', async () => {
      seedRest('library')
      const before = cached(ID)
      queryClient.setQueryData(queries.look(ID).queryKey, before)
      const answer = deferred<Look>()
      vi.spyOn(api, 'setStarred').mockReturnValue(answer.promise)
      const done = setStarred(ID, true)
      expect(detail(ID)).toEqual({ ...before, starred: true })
      const served = { ...before, starred: true, description: 'as the server has it' }
      answer.resolve(served)
      await done
      expect(detail(ID)).toEqual(served)
      expect(cached(ID)).toEqual(served)
    })

    it('puts the look back when the latest choice fails', async () => {
      seedRest('library')
      const before = cached(ID)
      queryClient.setQueryData(queries.look(ID).queryKey, before)
      const answer = deferred<Look>()
      vi.spyOn(api, 'setStarred').mockReturnValue(answer.promise)
      const done = setStarred(ID, true)
      expect(detail(ID)?.starred).toBe(true)
      answer.reject(new ApiError(500, 'Internal Server Error', `/api/looks/${ID}/starred`))
      await expect(done).rejects.toBeInstanceOf(ApiError)
      expect(detail(ID)).toEqual(before)
      expect(cached(ID)).toEqual(before)
    })

    it('puts each cache back from its own look when the two differ', async () => {
      seedRest('library')
      const listed = cached(ID)
      const own = { ...listed, description: 'as the editor read it' }
      queryClient.setQueryData(queries.look(ID).queryKey, own)
      const answer = deferred<Look>()
      vi.spyOn(api, 'setStarred').mockReturnValue(answer.promise)
      const done = setStarred(ID, true)
      expect(cached(ID)).toEqual({ ...listed, starred: true })
      expect(detail(ID)).toEqual({ ...own, starred: true })
      answer.reject(new ApiError(500, 'Internal Server Error', `/api/looks/${ID}/starred`))
      await expect(done).rejects.toBeInstanceOf(ApiError)
      expect(cached(ID)).toEqual(listed)
      expect(detail(ID)).toEqual(own)
    })

    it('leaves the entries of other looks alone, and makes none for a look nobody has read', async () => {
      seedRest('library')
      const other = cached('rain')
      queryClient.setQueryData(queries.look('rain').queryKey, other)
      vi.spyOn(api, 'setStarred').mockResolvedValue({ ...cached(ID), starred: true })
      await setStarred(ID, true)
      expect(detail('rain')).toEqual(other)
      expect(detail(ID)).toBeUndefined()
      expect(queryClient.getQueryCache().find({ queryKey: queries.look(ID).queryKey })).toBeUndefined()
    })

    it("puts back the look it held when the list hasn't been read", async () => {
      seedRest('library')
      const before = cached(ID)
      queryClient.removeQueries({ queryKey: queries.looks().queryKey, exact: true })
      queryClient.setQueryData(queries.look(ID).queryKey, before)
      const answer = deferred<Look>()
      vi.spyOn(api, 'setStarred').mockReturnValue(answer.promise)
      const done = setStarred(ID, true)
      expect(detail(ID)?.starred).toBe(true)
      answer.reject(new ApiError(500, 'Internal Server Error', `/api/looks/${ID}/starred`))
      await expect(done).rejects.toBeInstanceOf(ApiError)
      expect(detail(ID)).toEqual(before)
      expect(queryClient.getQueryData(queries.looks().queryKey)).toBeUndefined()
    })
  })

  it('shows nothing, and still sends the choice, while the looks are not in the cache', async () => {
    vi.spyOn(api, 'setStarred').mockResolvedValue({ id: ID, starred: true } as Look)
    await setStarred(ID, true)
    expect(api.setStarred).toHaveBeenCalledWith(ID, true)
    expect(queryClient.getQueryData(queries.looks().queryKey)).toBeUndefined()
  })
})
