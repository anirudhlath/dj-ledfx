import { useCallback, useEffect, useRef, useState } from "react"
import { toast } from "sonner"
import * as api from "@/lib/api-client"
import type { EffectParamSchema, Preset } from "@/lib/types"

export function useSceneEffects(sceneId: string) {
  const [schemas, setSchemas] = useState<Record<string, Record<string, EffectParamSchema>>>({})
  const [activeEffect, setActiveEffect] = useState("")
  const [activeParams, setActiveParams] = useState<Record<string, unknown>>({})
  const [presets, setPresets] = useState<Preset[]>([])
  const [loading, setLoading] = useState(true)

  const activeEffectRef = useRef("")
  const activeParamsRef = useRef<Record<string, unknown>>({})
  const seqRef = useRef(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    Promise.all([api.getEffects(), api.getSceneEffect(sceneId), api.getPresets()])
      .then(([effects, active, presetList]) => {
        if (cancelled) return
        setSchemas(effects)
        setActiveEffect(active.effect_name)
        setActiveParams(active.params)
        activeEffectRef.current = active.effect_name
        activeParamsRef.current = active.params
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
      const seq = ++seqRef.current
      try {
        await api.setSceneEffect(sceneId, effectName, params)
        const active = await api.getSceneEffect(sceneId)
        if (seq !== seqRef.current) return // a newer apply superseded this one
        activeEffectRef.current = active.effect_name
        activeParamsRef.current = active.params
        setActiveEffect(active.effect_name)
        setActiveParams(active.params)
      } catch (e) {
        toast.error(e instanceof Error ? e.message : "Failed to update effect")
      }
    },
    [sceneId],
  )

  const switchEffect = useCallback((name: string) => apply(name, {}), [apply])

  const updateParam = useCallback(
    (key: string, value: unknown) => {
      // Optimistically merge so rapid slider drags accumulate on the latest ref state
      const merged = { ...activeParamsRef.current, [key]: value }
      activeParamsRef.current = merged
      setActiveParams(merged)
      return apply(activeEffectRef.current, merged)
    },
    [apply],
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
