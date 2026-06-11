import { useCallback, useEffect, useState } from "react"
import { toast } from "sonner"
import * as api from "@/lib/api-client"
import type { EffectParamSchema, Preset } from "@/lib/types"

export function useSceneEffects(sceneId: string) {
  const [schemas, setSchemas] = useState<Record<string, Record<string, EffectParamSchema>>>({})
  const [activeEffect, setActiveEffect] = useState("")
  const [activeParams, setActiveParams] = useState<Record<string, unknown>>({})
  const [presets, setPresets] = useState<Preset[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    Promise.all([api.getEffects(), api.getSceneEffect(sceneId), api.getPresets()])
      .then(([effects, active, presetList]) => {
        if (cancelled) return
        setSchemas(effects)
        setActiveEffect(active.effect_name)
        setActiveParams(active.params)
        setPresets(presetList)
      })
      .catch((e) => console.error("Failed to init scene effects:", e))
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [sceneId])

  const apply = useCallback(
    async (effectName: string, params: Record<string, unknown>) => {
      await api.setSceneEffect(sceneId, effectName, params)
      const active = await api.getSceneEffect(sceneId)
      setActiveEffect(active.effect_name)
      setActiveParams(active.params)
    },
    [sceneId],
  )

  const switchEffect = useCallback(
    async (name: string) => {
      await apply(name, {})
    },
    [apply],
  )

  const updateParam = useCallback(
    async (key: string, value: unknown) => {
      await apply(activeEffect, { [key]: value })
    },
    [apply, activeEffect],
  )

  const loadPreset = useCallback(
    async (name: string) => {
      const preset = presets.find((p) => p.name === name)
      if (!preset) return
      await apply(preset.effect_class, preset.params)
    },
    [apply, presets],
  )

  const savePreset = useCallback(async (_name: string) => {
    toast.info("Presets can only be saved from the Default deck")
  }, [])

  return { schemas, activeEffect, activeParams, presets, loading, switchEffect, updateParam, loadPreset, savePreset }
}
