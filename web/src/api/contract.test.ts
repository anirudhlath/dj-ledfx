import { describe, expectTypeOf, it } from 'vitest'
import type { components, paths } from './generated/schema'
import type {
  ApiPath, Deck, Furniture, Home, InputKind, InputState, Light, LightShape, LightStatus, Location, PendingPath,
  PendingSchema, Room, RunningZone, TempoLock, TempoSource,
} from './contract'

describe('the contract', () => {
  // When the backend starts serving one of these, this fails tsc -b: swap the hand-written type
  // for the generated one in contract.ts (plan Task 15, Step 3).
  it('has no pending type the backend already serves', () => {
    expectTypeOf<Extract<PendingSchema, keyof components['schemas']>>().toEqualTypeOf<never>()
    expectTypeOf<Extract<PendingPath, keyof paths>>().toEqualTypeOf<never>()
  })

  it("carries §12.2's unions from the generated types", () => {
    expectTypeOf<RunningZone['state']>().toEqualTypeOf<'running' | 'slow' | 'crashed' | 'waiting' | 'transition'>()
    expectTypeOf<LightStatus>().toEqualTypeOf<
      'streaming' | 'own-effect' | 'streamed-copy' | 'offline' | 'switched-off' | 'reconnecting' | 'idle'
    >()
    expectTypeOf<InputKind>().toEqualTypeOf<'tempo' | 'music' | 'home-assistant' | 'sun'>()
    expectTypeOf<ApiPath>().toExtend<string>()
  })

  // I4: the names F1 wrote by hand for engine M2 are the ones M2's schema serves.
  it("serves engine M2's types and paths under F1's names", () => {
    expectTypeOf<
      | 'Placement' | 'PlacementIn' | 'PreviewStarted' | 'PreviewUpdate' | 'HomeSettings' | 'AnchorIn' | 'AnchorUpdate'
      | 'SubZoneIn' | 'SubZoneUpdate' | 'Box2' | 'Location' | 'Outdoor' | 'PointShape' | 'RecentLook'
    >().toExtend<keyof components['schemas']>()
    expectTypeOf<
      | '/api/home' | '/api/home/subzones/{sub_zone_id}' | '/api/lights/{light_id}/placement' | '/api/preview/{preview_id}'
      | '/api/running/recent'
    >().toExtend<keyof paths>()
  })

  // Engine M3 serves the tempo clock under F1's names, shaped as §12.4 shapes them.
  it("serves engine M3's types and paths under F1's names", () => {
    expectTypeOf<
      | 'Deck' | 'Inputs' | 'TempoInput' | 'InternalTempo' | 'ProDjLinkInput' | 'DjSet' | 'TempoRequest' | 'TapRequest'
      | 'NudgeRequest'
    >().toExtend<keyof components['schemas']>()
    expectTypeOf<'/api/inputs' | '/api/inputs/tempo' | '/api/inputs/tempo/tap' | '/api/inputs/tempo/nudge'>().toExtend<
      keyof paths
    >()
    expectTypeOf<Deck>().toEqualTypeOf<{
      number: number
      player: string
      state: 'empty' | 'cued' | 'playing'
      bpm: number | null
      pitch_percent: number
      master: boolean
    }>()
    expectTypeOf<TempoSource>().toEqualTypeOf<'prodjlink' | 'music' | 'internal'>()
    expectTypeOf<TempoLock>().toEqualTypeOf<'auto' | 'prodjlink' | 'music' | 'internal'>()
    expectTypeOf<InputState>().toEqualTypeOf<'connected' | 'stale' | 'disconnected' | 'idle'>()
  })

  // I1: engine M2 serves the home's size and which rooms hold lights.
  it("carries the home's size and each room's hasLights", () => {
    expectTypeOf<Home['size']>().toEqualTypeOf<{ eastWest: number; northSouth: number }>()
    expectTypeOf<Room['hasLights']>().toEqualTypeOf<boolean>()
  })

  // I3: engine M2 serves a home with no location and furniture drawn by polygon.
  it('leaves out what engine M2 may leave out of the home', () => {
    expectTypeOf<Home['location']>().toEqualTypeOf<Location | null | undefined>()
    expectTypeOf<Furniture['box']>().toEqualTypeOf<[number, number, number, number] | null | undefined>()
  })

  it("types a light's shape as §12.2 does", () => {
    expectTypeOf<Light['shape']>().toEqualTypeOf<LightShape | null | undefined>()
  })
})
