// What Live's controls do (§11.3, §11.5, §5.6, §9.4). Each calls the server. Where the server answers
// with the new state, the action puts it in the live store at once, so a control shows it without
// waiting for the push (F3 decision 8). A failure rejects; components say it with failureText()
// through useAnnounce() (Review Focus 1). Components call these, never `api` or the socket (§12).
import type { Id, RecentLook, RunningZone, TempoInput, TempoLock } from './contract'
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

/** What a failed action says (Review Focus 1): the action, then the server's reason, or that it didn't answer. */
export function failureText(action: string, error: unknown): string {
  if (error instanceof ApiError) return `Couldn't ${action}. ${error.status === 0 ? "The server didn't answer." : error.detail}`
  return `Couldn't ${action}. ${error instanceof Error ? error.message : String(error)}`
}
