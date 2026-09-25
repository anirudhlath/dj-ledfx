import { describe, expectTypeOf, it } from 'vitest'
import type { components, paths } from './generated/schema'
import type { ApiPath, InputKind, Light, LightShape, LightStatus, PendingPath, PendingSchema, RunningZone } from './contract'

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

  it("types a light's shape as §12.2 does", () => {
    expectTypeOf<Light['shape']>().toEqualTypeOf<LightShape | null | undefined>()
  })
})
