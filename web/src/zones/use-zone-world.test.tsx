import { QueryClientProvider } from '@tanstack/react-query'
import { renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'
import { queryClient } from '@/api/queries'
import { HERO_NOW, seedLive } from '@/test/live'
import { seedRest } from '@/test/rest'
import { useZoneWorld } from './use-zone-world'
import { zoneView } from './zone-view'

const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>

describe('useZoneWorld', () => {
  it("builds the cards' world from REST and the live store", () => {
    const state = seedRest('hero')
    seedLive('hero')
    const { result } = renderHook(() => useZoneWorld(), { wrapper })
    const office = state.running.find((zone) => zone.zoneId === 'office')!
    expect(zoneView(office, result.current, HERO_NOW)).toMatchObject({ name: 'Office desk', context: "on the music's beat" })
    expect(result.current.looks.get('homesunset')?.modifiers?.evening).toBe(true)
    expect(result.current.states.get('rope')).toMatchObject({ status: 'offline', ownEffect: null })
  })
})
