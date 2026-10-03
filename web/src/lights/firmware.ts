// A light's firmware state in words (§9.1): the effect it runs itself, or streams a copy of, as the engine
// names it in `ownEffect` ("LIFX Flame"), and the groups State-Firmware's breakdown draws (F3 decision 20).
// The stage's tooltip, the card's note, the breakdown and the phone's Zone detail all say it from here.
import type { Light } from '@/api/contract'
import type { LightState } from '@/stage/show'

/** The protocols a firmware effect's name can start with ("LIFX Flame"). */
const PROTOCOLS: readonly string[] = ['LIFX', 'Govee', 'OpenRGB'] satisfies readonly Light['protocol'][]

/** An effect's own word, its protocol's dropped: "LIFX Flame" → "Flame" (§9.1's "Govee has no Flame"). */
export function effectWord(effect: string): string {
  const [first, ...rest] = effect.split(' ')
  return PROTOCOLS.includes(first) && rest.length > 0 ? rest.join(' ') : effect
}

/** A light that runs its own effect, or gets a streamed copy of one: the breakdown lists it (F3 decision 20). */
export const runsFirmware = (state: LightState): boolean => state.status === 'own-effect' || state.status === 'streamed-copy'

/** What a breakdown row says beside a light's name: "LIFX Flame", or "Streamed copy of Flame". */
export function firmwareWords(state: LightState): string {
  const effect = state.ownEffect
  if (state.status === 'streamed-copy') return effect === null ? 'Streamed copy' : `Streamed copy of ${effectWord(effect)}`
  return effect ?? 'Own effect'
}

/** Four or more lights on one effect fold into one line (F3 decision 20; State-Firmware's eleven bulbs). */
export const FOLD_AT = 4

export interface FirmwareLight {
  light: Light
  state: LightState
}

export interface FirmwareGroup<T extends FirmwareLight = FirmwareLight> {
  status: 'own-effect' | 'streamed-copy'
  /** "Own effect", or a folded effect's own head, "Own effect · waveform". */
  title: string
  /** In the zone's order. */
  lights: T[]
  /** A folded group's one line, "11 lights · LIFX waveform"; null when each light has its row. */
  folded: string | null
}

const TITLE = { 'own-effect': 'Own effect', 'streamed-copy': 'Streamed copy' } as const

/** The zone's lights that run their own effect, then those that get a copy; other lights aren't in it. */
export function firmwareGroups<T extends FirmwareLight>(lights: readonly T[]): FirmwareGroup<T>[] {
  return (['own-effect', 'streamed-copy'] as const).flatMap((status) => {
    const these = lights.filter(({ state }) => state.status === status)
    const byEffect = new Map<string, T[]>()
    for (const each of these) {
      const effect = each.state.ownEffect
      if (effect !== null) byEffect.set(effect, [...(byEffect.get(effect) ?? []), each])
    }
    const folds = [...byEffect.entries()].filter(([, group]) => group.length >= FOLD_AT)
    const folded = new Set(folds.flatMap(([, group]) => group))
    const rows = these.filter((each) => !folded.has(each))
    return [
      ...(rows.length > 0 ? [{ status, title: TITLE[status], lights: rows, folded: null }] : []),
      ...folds.map(([effect, group]) => ({
        status,
        title: `${TITLE[status]} · ${effectWord(effect)}`,
        lights: group,
        folded: `${group.length} lights · ${firmwareWords(group[0].state)}`,
      })),
    ]
  })
}
