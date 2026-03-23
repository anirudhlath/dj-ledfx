import { useCallback, useEffect, useRef, useState } from "react"
import type { TransportState } from "@/lib/types"
import { getTransport, setTransport } from "@/lib/api-client"
import { wsClient } from "@/lib/ws-client"

export function useTransport() {
  const [state, setState] = useState<TransportState>("stopped")
  const lastState = useRef(state)

  useEffect(() => {
    getTransport().then((res) => {
      setState(res.state)
      lastState.current = res.state
    }).catch(() => {})

    const onTransport = (msg: Record<string, unknown>) => {
      if (typeof msg.state === "string") {
        const s = msg.state as TransportState
        if (s !== lastState.current) {
          lastState.current = s
          setState(s)
        }
      }
    }

    const onStatus = (msg: Record<string, unknown>) => {
      if (typeof msg.transport === "string") {
        const s = msg.transport as TransportState
        if (s !== lastState.current) {
          lastState.current = s
          setState(s)
        }
      }
    }

    const unsub1 = wsClient.on("transport", onTransport)
    const unsub2 = wsClient.on("status", onStatus)
    return () => { unsub1(); unsub2() }
  }, [])

  const setTransportState = useCallback(async (newState: TransportState) => {
    setState(newState)
    lastState.current = newState
    try {
      const res = await setTransport(newState)
      setState(res.state)
      lastState.current = res.state
    } catch {
      try {
        const res = await getTransport()
        setState(res.state)
        lastState.current = res.state
      } catch {
        // Server unreachable — revert to stopped
        setState("stopped")
        lastState.current = "stopped"
      }
    }
  }, [])

  return { transportState: state, setTransportState }
}
