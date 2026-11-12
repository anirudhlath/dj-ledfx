// What Live's controls do (§11.3, §11.5, §5.6, §9.4). Each calls the server. Where the server answers
// with the new state, the action puts it in the live store at once, so a control shows it without
// waiting for the push (F3 decision 8). A failure rejects; components say it with failureText()
// through useAnnounce() (Review Focus 1). Components call these, never `api` or the socket (§12).
import type { Id, Look, RecentLook, RunningZone, StartResponse, TempoInput, TempoLock, Transition } from './contract'
import { liveClient } from './live'
import { liveStore } from './live-store'
import { queries, queryClient } from './queries'
import { api, ApiError } from './rest'

/** The zone the server answered with, in place of the one the store holds. */
function storeZone(zone: RunningZone): void {
  liveStore.setState(({ running }) =>
    running === null ? {} : { running: { ...running, zones: running.zones.map((old) => (old.zoneId === zone.zoneId ? zone : old)) } },
  )
}

/**
 * A start's answer in the store (F4 ruling 13): the zone, replaced or added as the newest, and the
 * lights it took gone from the zones it took them from; a zone left with none stops, as on the server.
 */
function storeStarted({ takeOvers, ...zone }: StartResponse): void {
  const taken = new Set((takeOvers ?? []).flatMap((takeOver) => takeOver.lights))
  liveStore.setState(({ running }) => {
    if (running === null) return {}
    const others = running.zones
      .filter((other) => other.zoneId !== zone.zoneId)
      .map((other) => (other.lights.some((id) => taken.has(id)) ? { ...other, lights: other.lights.filter((id) => !taken.has(id)) } : other))
      .filter((other) => other.lights.length > 0)
    return { running: { ...running, zones: [...others, zone] } }
  })
}

/** The tempo the server answered with, in the inputs the store holds. */
function storeTempo(tempo: TempoInput): void {
  liveStore.setState(({ inputs }) => (inputs === null ? {} : { inputs: { ...inputs, tempo } }))
}

/** §11.3: a running zone's brightness, 0–1. */
export async function setBrightness(zoneId: Id, value: number): Promise<void> {
  storeZone(await api.setBrightness(zoneId, value))
}

/** §11.3 Off: the zone's lights go back to how they were. The `running` push removes its card. */
export async function turnOff(zoneId: Id): Promise<void> {
  await api.off(zoneId)
}

/** §9.2: a crashed zone starts its look again. */
export async function restartZone(zoneId: Id): Promise<void> {
  storeZone(await api.restart(zoneId))
}

/** §11.3 "Stop all does this for every zone after a confirm." The confirm is the caller's. */
export async function stopAll(): Promise<void> {
  await api.stopAll()
}

/** §8.2 Start: the look on the zone, with the transition chosen. Live shows it before the push comes. */
export async function startLook(zoneId: Id, lookId: Id, transition: Transition): Promise<void> {
  storeStarted(await api.start(zoneId, { lookId, transition }))
}

/** §9.4 "Start again": one tap plays a recent look on its zone, and the list is read afresh. */
export async function startAgain(recent: Pick<RecentLook, 'zoneId' | 'lookId'>): Promise<void> {
  await api.start(recent.zoneId, { lookId: recent.lookId })
  await queryClient.invalidateQueries({ queryKey: queries.recentLooks().queryKey })
}

/** §5.6: preview only, which the server keeps. Its `transport` push moves the switch. */
export async function setPreviewOnly(on: boolean): Promise<void> {
  await api.setPreviewOnly(on)
}

/** §11.5: lock a source; "auto" also ends a hold (CLAUDE.md, Key Design Decisions). */
export async function setTempoLock(lock: TempoLock): Promise<void> {
  storeTempo(await api.setTempo({ lock }))
}

/** §6.2 TAP: over the socket while it's open, else REST (F3 decision 5). */
export async function tapTempo(): Promise<void> {
  const clientTime = Date.now() / 1000
  const sent = liveClient()?.tap(clientTime) ?? null
  if (sent !== null) return sent
  storeTempo(await api.tap(clientTime))
}

/** §9.4 No lights placed: spread the unplaced lights round their rooms, unconfirmed (F3 decision 21). */
export async function guessPlacements(): Promise<void> {
  await api.guessPlacements()
  await queryClient.invalidateQueries({ queryKey: queries.lights().queryKey })
}

/** §9.4 First run's "Find new lights": how many the scan found, read defensively (the schema leaves it untyped). */
export async function findLights(): Promise<number> {
  const { discovered } = await api.scanDevices()
  await queryClient.invalidateQueries({ queryKey: queries.lights().queryKey })
  return Array.isArray(discovered) ? discovered.length : typeof discovered === 'number' ? discovered : 0
}

/** §9.4's "Try now": retry the link at once. */
export function retryLink(): void {
  liveClient()?.retryNow()
}

/** A look's star as each cache holds it: the library's list and the look's own entry (the editor's); undefined where a cache doesn't hold it. */
interface Stars {
  listed: boolean | undefined
  own: boolean | undefined
}

/**
 * A look's star requests: how many have been made (the latest wins), how many wait for an answer, the star a failure puts back in each
 * cache, which is the server's (the star as that cache held it before the first request now waiting, or what an earlier answer has served
 * since), and whether the latest request failed and its put-back is what the caches show: an earlier request's answer after that is the
 * server's word, and lands. Only the star is kept: a cache may have taken other fields from a refetch since, and a put-back leaves those.
 */
interface StarRequests {
  made: number
  waiting: number
  settled: Stars
  putBack: boolean
}

/** The looks with a request waiting for its answer; an entry goes when the last of them settles. */
const starRequests = new Map<Id, StarRequests>()

/**
 * A look in the `looks` cache, replaced by what `change` makes of it; a cache nobody has read has nothing to change, and is left alone.
 * The look's own entry is `changeOwnLook`'s: an updater that answers undefined makes no entry.
 */
function changeListedLook(lookId: Id, change: (look: Look) => Look): void {
  queryClient.setQueryData(queries.looks().queryKey, (looks) => looks?.map((look) => (look.id === lookId ? change(look) : look)))
}

/** A look's own `['looks', id]` entry (the editor's), replaced by what `change` makes of it, if anybody has read it. */
function changeOwnLook(lookId: Id, change: (look: Look) => Look): void {
  queryClient.setQueryData(queries.look(lookId).queryKey, (look) => look && change(look))
}

/** A look in each cache, replaced by what `change` makes of it. */
function changeCachedLook(lookId: Id, change: (look: Look) => Look): void {
  changeListedLook(lookId, change)
  changeOwnLook(lookId, change)
}

/** The look's star as each cache holds it now. */
const cachedStars = (lookId: Id): Stars => ({
  listed: queryClient.getQueryData(queries.looks().queryKey)?.find((look) => look.id === lookId)?.starred,
  own: queryClient.getQueryData(queries.look(lookId).queryKey)?.starred,
})

/**
 * Ends the fetches of the caches a star is about to be written to, as TanStack asks of an optimistic write: a refetch asked for before
 * the choice would land after it with the star as it was, and a cancelled one is put back to the state it started from, so this comes
 * before the write. A cache that holds nothing is left to finish: no choice is written over it, and a cancel would leave it empty.
 */
function cancelFetchesOf(lookId: Id): void {
  for (const { queryKey } of [queries.looks(), queries.look(lookId)]) {
    if (queryClient.getQueryData(queryKey) !== undefined) void queryClient.cancelQueries({ queryKey, exact: true })
  }
}

/**
 * §8.4's star, F5 ruling 16: the card shows the choice at once, then the server's look. The latest choice for a look wins: an earlier
 * request's answer never overwrites a later choice's star (the rest of that look lands), and neither does its failure. The latest
 * request's failure puts back the server's star, not an earlier choice's that was only ever shown, onto the look each cache holds now (so
 * what a refetch brought meanwhile stays), and rejects for the card to say aloud; an earlier request that is answered after that put-back
 * shows its answer, since the server holds it.
 */
export async function setStarred(lookId: Id, starred: boolean): Promise<void> {
  const requests = starRequests.get(lookId) ?? { made: 0, waiting: 0, settled: { listed: undefined, own: undefined }, putBack: false }
  starRequests.set(lookId, requests)
  const request = ++requests.made
  requests.putBack = false
  cancelFetchesOf(lookId)
  if (requests.waiting === 0) requests.settled = cachedStars(lookId)
  requests.waiting++
  changeCachedLook(lookId, (look) => ({ ...look, starred }))
  try {
    const served = await api.setStarred(lookId, starred)
    requests.settled = { listed: served.starred, own: served.starred }
    // The latest answer, or one after the latest failed and was put back, is the look. An earlier one is the server's word on all but the
    // star, which the latest choice still shows.
    if (request === requests.made || requests.putBack) changeCachedLook(lookId, () => served)
    else changeCachedLook(lookId, (look) => ({ ...served, starred: look.starred }))
  } catch (error) {
    const { settled } = requests
    if (request === requests.made && (settled.listed !== undefined || settled.own !== undefined)) {
      // Each cache gets back the star it held, which need not be the other's.
      changeListedLook(lookId, (look) => (settled.listed === undefined ? look : { ...look, starred: settled.listed }))
      changeOwnLook(lookId, (look) => (settled.own === undefined ? look : { ...look, starred: settled.own }))
      requests.putBack = true
    }
    throw error
  } finally {
    if (--requests.waiting === 0) starRequests.delete(lookId)
  }
}

/** What a failed action says (Review Focus 1): the action, then the server's reason, or that it didn't answer. */
export function failureText(action: string, error: unknown): string {
  if (error instanceof ApiError) return `Couldn't ${action}. ${error.status === 0 ? "The server didn't answer." : error.detail}`
  return `Couldn't ${action}. ${error instanceof Error ? error.message : String(error)}`
}
