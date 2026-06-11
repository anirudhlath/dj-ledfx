import { useState, useEffect, useCallback } from "react"
import type { SceneData } from "@/lib/types"
import * as api from "@/lib/api-client"

export function useScene(sceneId: string | null = null) {
  const [scene, setScene] = useState<SceneData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isActive, setIsActive] = useState(false)

  const refresh = useCallback(async () => {
    try {
      if (sceneId === null) {
        setScene(await api.getScene())
        setIsActive(false)
      } else {
        const detail = await api.getSceneDetail(sceneId)
        setScene(detail)
        setIsActive(detail.is_active)
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
    setIsActive(false)
    refresh()
  }, [refresh])

  // Rebuild the running pipeline after editing an active scene (placements and
  // mapping are read only at activation). Activation state is re-checked
  // server-side because it can change from outside this hook.
  const reapply = useCallback(async () => {
    if (sceneId === null) return
    const detail = await api.getSceneDetail(sceneId)
    setIsActive(detail.is_active)
    if (!detail.is_active) return
    await api.deactivateScene(sceneId)
    await api.activateScene(sceneId)
  }, [sceneId])

  const movePlacement = useCallback(
    async (deviceId: string, position: [number, number, number]) => {
      try {
        if (sceneId === null) {
          await api.updateSceneDevice(deviceId, { position })
        } else {
          await api.updateScenePlacement(sceneId, deviceId, { position })
          await reapply()
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to update placement")
      } finally {
        await refresh()
      }
    },
    [sceneId, reapply, refresh],
  )

  const removePlacement = useCallback(
    async (deviceId: string) => {
      try {
        if (sceneId === null) {
          await api.deleteSceneDevice(deviceId)
        } else {
          await api.deleteScenePlacement(sceneId, deviceId)
          await reapply()
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to remove placement")
      } finally {
        await refresh()
      }
    },
    [sceneId, reapply, refresh],
  )

  const changeMapping = useCallback(
    async (type: "linear" | "radial", params: Record<string, unknown>) => {
      try {
        // Optimistically update mapping so handle positions don't jump
        setScene((prev) => (prev ? { ...prev, mapping: { type, params } } : prev))
        if (sceneId === null) {
          await api.updateSceneMapping(type, params)
        } else {
          await api.updateScene(sceneId, { mapping_type: type, mapping_params: params })
          await reapply()
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to update mapping")
      } finally {
        await refresh()
      }
    },
    [sceneId, reapply, refresh],
  )

  const addPlacement = useCallback(
    async (deviceId: string, ledCount?: number) => {
      try {
        const opts = {
          position: [0, 0, 0] as [number, number, number],
          led_count: ledCount ?? 1,
        }
        if (sceneId === null) {
          await api.updateSceneDevice(deviceId, opts)
        } else {
          await api.updateScenePlacement(sceneId, deviceId, opts)
          await reapply()
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to add placement")
      } finally {
        await refresh()
      }
    },
    [sceneId, reapply, refresh],
  )

  return {
    scene,
    loading,
    error,
    isActive,
    refresh,
    movePlacement,
    removePlacement,
    changeMapping,
    addPlacement,
  }
}
