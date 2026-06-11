import { useState, useEffect, useCallback } from "react"
import { toast } from "sonner"
import type { Device, SceneListItem } from "@/lib/types"
import * as api from "@/lib/api-client"
import { ApiError } from "@/lib/api-client"

function conflictMessage(detail: unknown, devices: Device[]): string | null {
  if (
    typeof detail === "object" &&
    detail !== null &&
    (detail as { error?: string }).error === "device_conflict"
  ) {
    const ids = (detail as { conflicting_devices?: string[] }).conflicting_devices ?? []
    const names = ids.map((id) => devices.find((d) => d.stable_id === id)?.name ?? id)
    return `Device conflict: ${names.join(", ")} already in another active scene`
  }
  return null
}

export function useScenes(devices: Device[] = []) {
  const [scenes, setScenes] = useState<SceneListItem[]>([])
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      setScenes(await api.listScenes())
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to load scenes")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const create = useCallback(
    async (name: string) => {
      const scene = await api.createScene(name)
      await refresh()
      return scene
    },
    [refresh],
  )

  const rename = useCallback(
    async (sceneId: string, name: string) => {
      await api.updateScene(sceneId, { name })
      await refresh()
    },
    [refresh],
  )

  const setEffectMode = useCallback(
    async (sceneId: string, mode: "independent" | "shared") => {
      await api.updateScene(sceneId, { effect_mode: mode })
      await refresh()
    },
    [refresh],
  )

  const remove = useCallback(
    async (sceneId: string) => {
      await api.deleteScene(sceneId)
      await refresh()
    },
    [refresh],
  )

  const activate = useCallback(
    async (sceneId: string): Promise<boolean> => {
      try {
        await api.activateScene(sceneId)
        await refresh()
        return true
      } catch (e) {
        const msg =
          e instanceof ApiError
            ? (conflictMessage(e.detail, devices) ?? e.message)
            : "Failed to activate scene"
        toast.error(msg)
        return false
      }
    },
    [refresh, devices],
  )

  const deactivate = useCallback(
    async (sceneId: string) => {
      await api.deactivateScene(sceneId)
      await refresh()
    },
    [refresh],
  )

  return { scenes, loading, refresh, create, rename, remove, setEffectMode, activate, deactivate }
}
