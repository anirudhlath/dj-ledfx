import { useCallback, useEffect, useState } from "react"
import * as api from "@/lib/api-client"
import type { ActiveEffect, EffectParamSchema, Preset } from "@/lib/types"

type ZoneEffect = ActiveEffect & { zoneId: string }

/**
 * The effect deck works on one zone's classic effect. `lookId` is the look the zone
 * runs (null when it's off), so the deck reloads whenever that changes.
 */
export function useEffects(zoneId: string | null, lookId: string | null) {
  const [schemas, setSchemas] = useState<
    Record<string, Record<string, EffectParamSchema>>
  >({})
  const [active, setActive] = useState<ZoneEffect | null>(null)
  const [presets, setPresets] = useState<Preset[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([api.getEffects(), api.getPresets()])
      .then(([effects, presetList]) => {
        setSchemas(effects)
        setPresets(presetList)
      })
      .catch((e) => console.error("Failed to init effects:", e))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (zoneId === null || lookId === null) return
    let current = true
    api
      .getActiveEffect(zoneId)
      .then((effect) => {
        if (current) setActive({ zoneId, effect: effect?.effect ?? "", params: effect?.params ?? {} })
      })
      .catch((e) => console.error("Failed to load the zone's effect:", e))
    return () => {
      current = false
    }
  }, [zoneId, lookId])

  const shown = lookId !== null && active?.zoneId === zoneId ? active : null

  const switchEffect = useCallback(
    async (name: string) => {
      if (zoneId === null) return
      setActive({ zoneId, ...(await api.setActiveEffect(zoneId, { effect: name })) })
    },
    [zoneId]
  )

  const updateParam = useCallback(
    async (key: string, value: unknown) => {
      if (zoneId === null) return
      const result = await api.setActiveEffect(zoneId, { params: { [key]: value } })
      setActive({ zoneId, ...result })
    },
    [zoneId]
  )

  const loadPreset = useCallback(
    async (name: string) => {
      if (zoneId === null) return
      setActive({ zoneId, ...(await api.loadPreset(zoneId, name)) })
    },
    [zoneId]
  )

  const savePreset = useCallback(
    async (name: string) => {
      if (zoneId === null) return
      await api.savePreset(zoneId, name)
      setPresets(await api.getPresets())
    },
    [zoneId]
  )

  const removePreset = useCallback(async (name: string) => {
    await api.deletePreset(name)
    setPresets(await api.getPresets())
  }, [])

  return {
    schemas,
    activeEffect: shown?.effect ?? "",
    activeParams: shown?.params ?? {},
    presets,
    loading,
    switchEffect,
    updateParam,
    loadPreset,
    savePreset,
    removePreset,
  }
}
