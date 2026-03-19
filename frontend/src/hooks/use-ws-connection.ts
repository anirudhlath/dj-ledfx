import { useEffect, useState } from "react"
import { wsClient } from "@/lib/ws-client"

export function useWsConnection() {
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    wsClient.connect()
    wsClient.subscribeBeat(30)
    wsClient.subscribeFrames(30)

    const unsub = wsClient.onConnectionChange(setConnected)

    return () => {
      unsub()
      wsClient.disconnect()
    }
  }, [])

  return connected
}
