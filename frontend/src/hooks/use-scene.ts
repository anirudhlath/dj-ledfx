import { useState, useEffect, useCallback } from "react"
import type { SceneData, SceneDetail } from "@/lib/types"
import * as api from "@/lib/api-client"

export function useScene(sceneId: string | null = null) {
  const [scene, setScene] = useState<SceneData | SceneDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      if (sceneId === null) {
        setScene(await api.getScene())
      } else {
        setScene(await api.getSceneDetail(sceneId))
      }
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load scene")
    } finally {
      setLoading(false)
    }
  }, [sceneId])

  useEffect(() => {
    setLoading(true)
    setError(null)
    refresh()
  }, [refresh])

  // Rebuild the running pipeline after editing an active scene (placements and
  // mapping are read only at activation). Activation state is re-checked
  // server-side because it can change from outside this hook.
  const reapply = useCallback(async () => {
    if (sceneId === null) return
    const detail = await api.getSceneDetail(sceneId)
    if (!detail.is_active) return
    await api.deactivateScene(sceneId)
    await api.activateScene(sceneId)
  }, [sceneId])

  const mutate = useCallback(
    async (errMsg: string, legacyFn: () => Promise<unknown>, dbFn: (id: string) => Promise<unknown>) => {
      try {
        if (sceneId === null) {
          await legacyFn()
        } else {
          await dbFn(sceneId)
          await reapply()
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : errMsg)
      } finally {
        await refresh()
      }
    },
    [sceneId, reapply, refresh],
  )

  const movePlacement = useCallback(
    (deviceId: string, position: [number, number, number]) =>
      mutate(
        "Failed to update placement",
        () => api.updateSceneDevice(deviceId, { position }),
        (id) => api.updateScenePlacement(id, deviceId, { position }),
      ),
    [mutate],
  )

  const removePlacement = useCallback(
    (deviceId: string) =>
      mutate(
        "Failed to remove placement",
        () => api.deleteSceneDevice(deviceId),
        (id) => api.deleteScenePlacement(id, deviceId),
      ),
    [mutate],
  )

  const changeMapping = useCallback(
    async (type: "linear" | "radial", params: Record<string, unknown>) => {
      // Optimistically update mapping so handle positions don't jump
      setScene((prev) => (prev ? { ...prev, mapping: { type, params } } : prev))
      await mutate(
        "Failed to update mapping",
        () => api.updateSceneMapping(type, params),
        (id) => api.updateScene(id, { mapping_type: type, mapping_params: params }),
      )
    },
    [mutate],
  )

  const addPlacement = useCallback(
    (deviceId: string, ledCount?: number) => {
      const opts = {
        position: [0, 0, 0] as [number, number, number],
        led_count: ledCount ?? 1,
      }
      return mutate(
        "Failed to add placement",
        () => api.updateSceneDevice(deviceId, opts),
        (id) => api.updateScenePlacement(id, deviceId, opts),
      )
    },
    [mutate],
  )

  return {
    scene,
    loading,
    error,
    refresh,
    movePlacement,
    removePlacement,
    changeMapping,
    addPlacement,
  }
}
