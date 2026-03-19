import { useState, useEffect, useCallback } from "react"
import type { SceneData } from "@/lib/types"
import {
  getScene,
  updateSceneDevice,
  deleteSceneDevice,
  updateSceneMapping,
} from "@/lib/api-client"

export function useScene() {
  const [scene, setScene] = useState<SceneData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const data = await getScene()
      setScene(data)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load scene")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const movePlacement = useCallback(
    async (deviceId: string, position: [number, number, number]) => {
      try {
        await updateSceneDevice(deviceId, { position })
        await refresh()
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to update placement")
      }
    },
    [refresh]
  )

  const removePlacement = useCallback(
    async (deviceId: string) => {
      try {
        await deleteSceneDevice(deviceId)
        await refresh()
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to remove placement")
      }
    },
    [refresh]
  )

  const changeMapping = useCallback(
    async (type: "linear" | "radial", params: Record<string, unknown>) => {
      try {
        // Optimistically update mapping so handle positions don't jump
        setScene((prev) =>
          prev ? { ...prev, mapping: { type, params } } : prev
        )
        await updateSceneMapping(type, params)
        await refresh()
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to update mapping")
      }
    },
    [refresh],
  )

  const addPlacement = useCallback(
    async (deviceId: string, ledCount?: number) => {
      try {
        await updateSceneDevice(deviceId, {
          position: [0, 0, 0],
          led_count: ledCount ?? 1,
        })
        await refresh()
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to add placement")
      }
    },
    [refresh]
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
