// REST reads through TanStack Query (spec §3.3). The socket pushes what runs and the lights' status
// (running, lights, attention, transport), and nothing else: looks, zones and the home map can change
// from another device (a group made on the phone, a star added), so they go stale after a minute and
// refetch when the window regains focus. The socket's snapshots also send REST back for zones and
// lights it names that REST doesn't know (refetchOnNews), and a reconnect refetches everything
// (§9.4, "Resync everything on reconnect").
import { QueryClient, queryOptions } from '@tanstack/react-query'
import type { Id } from './contract'
import type { LiveStore } from './live-store'
import { api } from './rest'

/** How long looks, zones and the home map count as fresh. */
const CHANGES_ELSEWHERE_MS = 60_000
const changesElsewhere = { staleTime: CHANGES_ELSEWHERE_MS, refetchOnWindowFocus: true } as const

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { staleTime: Infinity, retry: 1, refetchOnWindowFocus: false } },
  })
}

/** The app's query client. */
export const queryClient = createQueryClient()

export const queries = {
  looks: () => queryOptions({ queryKey: ['looks'], queryFn: api.looks, ...changesElsewhere }),
  look: (id: Id) => queryOptions({ queryKey: ['looks', id], queryFn: () => api.look(id), ...changesElsewhere }),
  zones: () => queryOptions({ queryKey: ['zones'], queryFn: api.zones, ...changesElsewhere }),
  lights: () => queryOptions({ queryKey: ['lights'], queryFn: api.lights }),
  home: () => queryOptions({ queryKey: ['home'], queryFn: api.home, ...changesElsewhere }),
  inputs: () => queryOptions({ queryKey: ['inputs'], queryFn: api.inputs }),
  signals: () => queryOptions({ queryKey: ['signals'], queryFn: api.signals }),
}

/** After a reconnect: every query goes stale, and the ones on screen fetch again. */
export function resync(client: QueryClient): Promise<void> {
  return client.invalidateQueries()
}

/**
 * Sends REST back for what the socket names and REST doesn't know: a zone that runs but isn't in
 * the zones (a group made elsewhere), and lights added or removed (a light discovered later has no
 * name until then). Returns the unsubscribe.
 */
export function refetchOnNews(store: LiveStore, client: QueryClient): () => void {
  return store.subscribe((state, previous) => {
    if (state.running !== previous.running && state.running !== null) {
      const zones = client.getQueryData(queries.zones().queryKey)
      const known = new Set(zones?.map((zone) => zone.id))
      if (zones !== undefined && state.running.zones.some((zone) => !known.has(zone.zoneId))) {
        void client.invalidateQueries({ queryKey: queries.zones().queryKey })
      }
    }
    if (state.lights !== previous.lights && state.lights !== null) {
      const lights = client.getQueryData(queries.lights().queryKey)
      const pushed = state.lights
      if (lights !== undefined && (lights.length !== Object.keys(pushed).length || lights.some((light) => !(light.id in pushed)))) {
        void client.invalidateQueries({ queryKey: queries.lights().queryKey })
      }
    }
  })
}
