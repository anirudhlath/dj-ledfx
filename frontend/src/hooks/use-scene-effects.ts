import { useCallback, useEffect, useRef, useState } from "react"
import { toast } from "sonner"
import * as api from "@/lib/api-client"
import type { EffectParamSchema, Preset } from "@/lib/types"

export function useSceneEffects(
  sceneId: string,
  schemas: Record<string, Record<string, EffectParamSchema>>,
  presets: Preset[],
) {
  const [activeEffect, setActiveEffect] = useState("")
  const [activeParams, setActiveParams] = useState<Record<string, unknown>>({})
  const [loading, setLoading] = useState(true)

  const activeEffectRef = useRef("")
  const activeParamsRef = useRef<Record<string, unknown>>({})
  const seqRef = useRef(0)

  const commitActive = useCallback((effect: string, params: Record<string, unknown>) => {
    activeEffectRef.current = effect
    activeParamsRef.current = params
    setActiveEffect(effect)
    setActiveParams(params)
  }, [])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    api
      .getSceneEffect(sceneId)
      .then((active) => {
        if (cancelled) return
        commitActive(active.effect_name, active.params)
      })
      .catch((e) => console.error("Failed to init scene effects:", e))
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [sceneId, commitActive])

  const apply = useCallback(
    async (effectName: string, params: Record<string, unknown>) => {
      const seq = ++seqRef.current
      try {
        const response = await api.setSceneEffect(sceneId, effectName, params)
        if (seq !== seqRef.current) return // a newer apply superseded this one
        commitActive(response.effect_name, response.params)
      } catch (e) {
        toast.error(e instanceof Error ? e.message : "Failed to update effect")
      }
    },
    [sceneId, commitActive],
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

  return { schemas, activeEffect, activeParams, presets, loading, switchEffect, updateParam, loadPreset }
}
