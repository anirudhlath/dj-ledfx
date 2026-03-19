import { useCallback, useEffect, useRef, useState } from "react"
import * as api from "@/lib/api-client"
import { wsClient } from "@/lib/ws-client"
import type { Device, DeviceGroup, FrameData } from "@/lib/types"

export function useDevices() {
  const [devices, setDevices] = useState<Device[]>([])
  const [groups, setGroups] = useState<Record<string, DeviceGroup>>({})
  const [frameData, setFrameData] = useState<Map<string, FrameData>>(new Map())
  const [loading, setLoading] = useState(true)
  const devicesRef = useRef(devices)
  devicesRef.current = devices

  useEffect(() => {
    Promise.all([api.getDevices(), api.getGroups()])
      .then(([deviceList, groupMap]) => {
        setDevices(deviceList)
        setGroups(groupMap)
      })
      .catch((e) => console.error("Failed to init devices:", e))
      .finally(() => setLoading(false))
  }, [])

  // Subscribe to device stats from WS
  useEffect(() => {
    const unsub = wsClient.on("stats", (msg) => {
      const stats = msg.devices as Array<{
        name: string
        fps: number
        latency_ms: number
        frames_dropped: number
        connected: boolean
      }>
      if (!stats) return

      setDevices((prev) =>
        prev.map((d) => {
          const s = stats.find((x) => x.name === d.name)
          return s
            ? {
                ...d,
                send_fps: s.fps,
                effective_latency_ms: s.latency_ms,
                frames_dropped: s.frames_dropped,
                connected: s.connected,
              }
            : d
        })
      )
    })
    return unsub
  }, [])

  // Subscribe to binary frame data from WS
  useEffect(() => {
    const unsub = wsClient.onFrame((frame) => {
      setFrameData((prev) => {
        const next = new Map(prev)
        next.set(frame.deviceName, frame)
        return next
      })
    })
    return unsub
  }, [])

  const discover = useCallback(async () => {
    const result = await api.discoverDevices()
    setDevices(await api.getDevices())
    return result.discovered
  }, [])

  const identify = useCallback(async (name: string) => {
    await api.identifyDevice(name)
  }, [])

  const addGroup = useCallback(async (name: string, color: string) => {
    await api.createGroup(name, color)
    setGroups(await api.getGroups())
  }, [])

  const removeGroup = useCallback(async (name: string) => {
    await api.deleteGroup(name)
    setGroups(await api.getGroups())
  }, [])

  const assignGroup = useCallback(async (deviceName: string, groupName: string) => {
    await api.assignDeviceGroup(deviceName, groupName)
    setDevices(await api.getDevices())
  }, [])

  return {
    devices,
    groups,
    frameData,
    loading,
    discover,
    identify,
    addGroup,
    removeGroup,
    assignGroup,
  }
}
