import { useCallback, useEffect, useState } from "react"
import type { TransportState } from "@/lib/types"
import { apiClient } from "@/lib/api-client"
import { wsClient } from "@/lib/ws-client"

export function useTransport() {
  const [state, setState] = useState<TransportState>("stopped")

  useEffect(() => {
    apiClient.getTransport().then((res) => setState(res.state)).catch(() => {})
    const unsub = wsClient.onTransport(setState)
    return unsub
  }, [])

  const setTransportState = useCallback(async (newState: TransportState) => {
    setState(newState)
    try {
      const res = await apiClient.setTransport(newState)
      setState(res.state)
    } catch {
      const res = await apiClient.getTransport()
      setState(res.state)
    }
  }, [])

  return { transportState: state, setTransportState }
}
