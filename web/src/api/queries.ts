// REST reads through TanStack Query (spec §3.3). The socket pushes what changes (running, lights,
// attention), so what REST loads stays fresh until a reconnect, when resync() fetches it all again
// (§9.4, "Resync everything on reconnect").
import { QueryClient, queryOptions } from '@tanstack/react-query'
import type { Id } from './contract'
import { api } from './rest'

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { staleTime: Infinity, retry: 1, refetchOnWindowFocus: false } },
  })
}

/** The app's query client. */
export const queryClient = createQueryClient()

export const queries = {
  looks: () => queryOptions({ queryKey: ['looks'], queryFn: api.looks }),
  look: (id: Id) => queryOptions({ queryKey: ['looks', id], queryFn: () => api.look(id) }),
  zones: () => queryOptions({ queryKey: ['zones'], queryFn: api.zones }),
  lights: () => queryOptions({ queryKey: ['lights'], queryFn: api.lights }),
  home: () => queryOptions({ queryKey: ['home'], queryFn: api.home }),
  inputs: () => queryOptions({ queryKey: ['inputs'], queryFn: api.inputs }),
  signals: () => queryOptions({ queryKey: ['signals'], queryFn: api.signals }),
}

/** After a reconnect: every query goes stale, and the ones on screen fetch again. */
export function resync(client: QueryClient): Promise<void> {
  return client.invalidateQueries()
}
