import { useCallback, useEffect, useState } from "react"
import * as api from "@/lib/api-client"
import type { EffectParamSchema, Preset } from "@/lib/types"

export function useEffects() {
  const [schemas, setSchemas] = useState<
    Record<string, Record<string, EffectParamSchema>>
  >({})
  const [activeEffect, setActiveEffect] = useState("")
  const [activeParams, setActiveParams] = useState<Record<string, unknown>>({})
  const [presets, setPresets] = useState<Preset[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([api.getEffects(), api.getActiveEffect(), api.getPresets()])
      .then(([effects, active, presetList]) => {
        setSchemas(effects)
        setActiveEffect(active.effect)
        setActiveParams(active.params)
        setPresets(presetList)
      })
      .catch((e) => console.error("Failed to init effects:", e))
      .finally(() => setLoading(false))
  }, [])

  const switchEffect = useCallback(
    async (name: string, params?: Record<string, unknown>) => {
      const result = await api.setActiveEffect({ effect: name, params })
      setActiveEffect(result.effect)
      setActiveParams(result.params)
    },
    []
  )

  const updateParam = useCallback(async (key: string, value: unknown) => {
    const result = await api.setActiveEffect({ params: { [key]: value } })
    setActiveParams(result.params)
  }, [])

  const loadPreset = useCallback(async (name: string) => {
    const result = await api.loadPreset(name)
    setActiveEffect(result.effect)
    setActiveParams(result.params)
  }, [])

  const savePreset = useCallback(async (name: string) => {
    await api.savePreset(name)
    setPresets(await api.getPresets())
  }, [])

  const removePreset = useCallback(async (name: string) => {
    await api.deletePreset(name)
    setPresets(await api.getPresets())
  }, [])

  return {
    schemas,
    activeEffect,
    activeParams,
    presets,
    loading,
    switchEffect,
    updateParam,
    loadPreset,
    savePreset,
    removePreset,
  }
}
