import { useState, useEffect, useCallback } from "react"
import { toast } from "sonner"
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
    setScene(null)
    refresh()
  }, [refresh])

  // Rebuild the running pipeline after editing an active scene (placements and
  // mapping are read only at activation).
  const reapply = useCallback(async () => {
    if (sceneId === null || !isActive) return
    await api.deactivateScene(sceneId)
    await api.activateScene(sceneId)
    toast.info("Scene re-applied")
  }, [sceneId, isActive])

  const movePlacement = useCallback(
    async (deviceId: string, position: [number, number, number]) => {
      try {
        if (sceneId === null) {
          await api.updateSceneDevice(deviceId, { position })
        } else {
          await api.updateScenePlacement(sceneId, deviceId, { position })
          await reapply()
        }
        await refresh()
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to update placement")
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
        await refresh()
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to remove placement")
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
        await refresh()
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to update mapping")
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
        await refresh()
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to add placement")
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
