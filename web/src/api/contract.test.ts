import { describe, expectTypeOf, it } from 'vitest'
import type { components, paths } from './generated/schema'
import type {
  ApiPath, Furniture, Home, InputKind, Light, LightShape, LightStatus, Location, PendingPath, PendingSchema, RunningZone,
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

  // I4: each pending type carries engine M2's name, so the swap fails on the name, not later.
  it("names the pending types and paths as engine M2's schema does", () => {
    expectTypeOf<
      | 'Placement' | 'PlacementIn' | 'PreviewStarted' | 'PreviewUpdate' | 'HomeSettings' | 'AnchorIn' | 'AnchorUpdate'
      | 'SubZoneIn' | 'SubZoneUpdate' | 'Box2' | 'Location' | 'Outdoor' | 'PointShape'
    >().toExtend<PendingSchema>()
    expectTypeOf<'/api/home/subzones/{sub_zone_id}'>().toExtend<PendingPath>()
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
