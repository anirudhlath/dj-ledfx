// What the zone cards read: the zones, the looks and the lights from REST, and from the live store each
// light's state, whose beat the clock follows, what runs and the attention feed, a slice at a time. A beat
// message changes none of these slices unless its source changes, so the beat redraws no card.
import { useQuery } from '@tanstack/react-query'
import { useMemo } from 'react'
import type { RunningZone } from '@/api/contract'
import { useLive } from '@/api/live-store'
import { queries } from '@/api/queries'
import { zoneWorld, type ZoneWorld } from './zone-view'

const NOTHING_RUNS: readonly RunningZone[] = []

export function useZoneWorld(): ZoneWorld {
  const zones = useQuery(queries.zones()).data
  const looks = useQuery(queries.looks()).data
  const lights = useQuery(queries.lights()).data
  const updates = useLive((state) => state.lights)
  const beatSource = useLive((state) => state.beat?.source ?? null)
  const running = useLive((state) => state.running?.zones ?? NOTHING_RUNS)
  const attention = useLive((state) => state.attention)
  return useMemo(
    () => zoneWorld({ zones, looks, lights, updates, beatSource, running, attention }),
    [zones, looks, lights, updates, beatSource, running, attention],
  )
}
