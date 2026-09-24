import { useCallback, useEffect, useState } from "react"
import { toast } from "sonner"
import * as api from "@/lib/api-client"
import type { LookSummary, RunningZone, Zone } from "@/lib/types"
import { wsClient } from "@/lib/ws-client"

function report(e: unknown) {
  toast.error(e instanceof Error ? e.message : String(e))
}

async function act(fn: () => Promise<unknown>): Promise<void> {
  try {
    await fn()
  } catch (e) {
    report(e)
  }
}

/** Zones, looks and what runs; the `running` and `transport` channels keep them current. */
export function useZones() {
  const [zones, setZones] = useState<Zone[]>([])
  const [looks, setLooks] = useState<LookSummary[]>([])
  const [running, setRunning] = useState<RunningZone[]>([])
  const [previewOnly, setPreviewOnlyState] = useState(false)

  useEffect(() => {
    Promise.all([api.getZones(), api.getLooks(), api.getRunning(), api.getConfig()])
      .then(([zoneList, lookList, now, config]) => {
        setZones(zoneList)
        setLooks(lookList)
        setRunning(now.zones)
        setPreviewOnlyState(config.engine.preview_only ?? false)
      })
      .catch(report)
    const offRunning = wsClient.on("running", (msg) => {
      setRunning(msg.zones as RunningZone[])
    })
    const offTransport = wsClient.on("transport", (msg) => {
      setPreviewOnlyState(msg.state === "simulating")
    })
    return () => {
      offRunning()
      offTransport()
    }
  }, [])

  // The `running` channel pushes what runs after a start or an Off.
  const start = useCallback(
    (zoneId: string, lookId: string) => act(() => api.startLook(zoneId, lookId)),
    []
  )
  const off = useCallback((zoneId: string) => act(() => api.turnOff(zoneId)), [])

  const setPreviewOnly = useCallback(async (on: boolean) => {
    try {
      const config = await api.setPreviewOnly(on)
      setPreviewOnlyState(config.engine.preview_only ?? on)
    } catch (e) {
      report(e)
    }
  }, [])

  return { zones, looks, running, previewOnly, start, off, setPreviewOnly }
}
