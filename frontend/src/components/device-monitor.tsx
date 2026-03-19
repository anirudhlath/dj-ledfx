import { useEffect, useRef } from "react"
import type { Device, FrameData } from "@/lib/types"
import { cn } from "@/lib/utils"
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"

interface DeviceMonitorProps {
  devices: Device[]
  frameData: Map<string, FrameData>
}

const MAX_LED_PREVIEW = 40

// green = perfect, yellow = warning, red = bad
function fpsColor(fps: number) {
  if (fps >= 50) return "text-green-400"
  if (fps >= 25) return "text-yellow-400"
  return fps > 0 ? "text-red-400" : "text-muted-foreground/50"
}

function latencyColor(ms: number) {
  if (ms <= 0) return "text-muted-foreground/50"
  if (ms <= 30) return "text-green-400"
  if (ms <= 80) return "text-yellow-400"
  return "text-red-400"
}

function deliveryColor(pct: number) {
  if (pct >= 99) return "text-green-400"
  if (pct >= 90) return "text-yellow-400"
  return "text-red-400"
}

function dropColor(pct: number) {
  if (pct === 0) return "text-green-400"
  if (pct < 5) return "text-yellow-400"
  return "text-red-400"
}

function LedPreview({ frame, ledCount }: { frame: FrameData | undefined; ledCount: number }) {
  if (!frame || frame.rgb.length === 0) {
    return (
      <div className="h-3 rounded bg-muted/40" />
    )
  }

  // Use device's actual led_count, not frame size (frame may be padded to global max)
  const totalLeds = Math.min(ledCount, Math.floor(frame.rgb.length / 3))

  // Single LED (point light) — show one solid color block
  if (totalLeds <= 1) {
    const r = frame.rgb[0]
    const g = frame.rgb[1]
    const b = frame.rgb[2]
    return (
      <div
        className="h-3 rounded"
        style={{ backgroundColor: `rgb(${r},${g},${b})` }}
      />
    )
  }

  // Multiple LEDs (segments/strip) — render as discrete segments with gaps
  const previewCount = Math.min(totalLeds, MAX_LED_PREVIEW)
  const step = totalLeds / previewCount

  return (
    <div className="flex gap-px h-3">
      {Array.from({ length: previewCount }).map((_, i) => {
        const idx = Math.floor(i * step) * 3
        const r = frame.rgb[idx]
        const g = frame.rgb[idx + 1]
        const b = frame.rgb[idx + 2]
        return (
          <div
            key={i}
            className="flex-1 rounded-sm"
            style={{ backgroundColor: `rgb(${r},${g},${b})` }}
          />
        )
      })}
    </div>
  )
}

function DropIndicator({ dropped }: { dropped: number }) {
  const prevDropped = useRef(dropped)
  const lastDropTime = useRef(0)
  const elRef = useRef<HTMLSpanElement>(null)
  const rafRef = useRef(0)

  // Start rAF fade only when new drops detected, stop when fade completes
  useEffect(() => {
    if (dropped > prevDropped.current) {
      lastDropTime.current = performance.now()
      cancelAnimationFrame(rafRef.current)
      const tick = () => {
        const el = elRef.current
        if (!el) return
        const elapsed = performance.now() - lastDropTime.current
        const brightness = Math.max(0, 1 - elapsed / 800)
        el.style.opacity = `${0.15 + brightness * 0.85}`
        el.style.boxShadow = brightness > 0.01
          ? `0 0 ${4 + brightness * 4}px rgba(239,68,68,${brightness * 0.8})`
          : "none"
        if (brightness > 0.01) {
          rafRef.current = requestAnimationFrame(tick)
        }
      }
      rafRef.current = requestAnimationFrame(tick)
    }
    prevDropped.current = dropped
  }, [dropped])

  useEffect(() => () => cancelAnimationFrame(rafRef.current), [])

  return (
    <span
      ref={elRef}
      className="size-1.5 rounded-full shrink-0 bg-red-500"
      style={{ opacity: 0.15 }}
    />
  )
}

interface DeviceStats {
  dropPct: number
  avgFps: number
  avgLatency: number
  avgDropPct: number
  avgBacklog: number
}

function useDeviceStats(fps: number, latency: number, dropped: number): DeviceStats {
  const prevRef = useRef({ dropped, time: performance.now() })
  const dropPctRef = useRef(0)
  const accumRef = useRef({ fps: 0, latency: 0, dropPct: 0, backlog: 0, samples: 0 })

  const now = performance.now()
  const dt = (now - prevRef.current.time) / 1000
  if (dt >= 0.5) {
    const delta = dropped - prevRef.current.dropped
    const dropsPerSec = delta > 0 ? delta / dt : 0
    const total = fps + dropsPerSec
    dropPctRef.current = total > 0 ? (dropsPerSec / total) * 100 : 0
    prevRef.current = { dropped, time: now }

    // Accumulate for session averages
    if (fps > 0 || latency > 0) {
      const a = accumRef.current
      a.fps += fps
      a.latency += latency
      a.dropPct += dropPctRef.current
      a.backlog += dropped
      a.samples += 1
    }
  }

  const a = accumRef.current
  const n = Math.max(a.samples, 1)

  return {
    dropPct: dropPctRef.current,
    avgFps: a.fps / n,
    avgLatency: a.latency / n,
    avgDropPct: a.dropPct / n,
    avgBacklog: a.backlog / n,
  }
}

function DeviceCard({ device, frame }: { device: Device; frame: FrameData | undefined }) {
  const { name, device_type, led_count, send_fps, effective_latency_ms, frames_dropped, connected } = device
  const stats = useDeviceStats(send_fps, effective_latency_ms, frames_dropped)

  // Delivery = inverse of drop rate (both computed from windowed deltas)
  const deliveryPct = 100 - stats.dropPct

  return (
    <div className="flex flex-col bg-card border border-border rounded-lg shrink-0 min-w-[200px] overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border/50">
        <span
          className={cn(
            "size-2 rounded-full shrink-0",
            connected ? "bg-green-500" : "bg-red-500/60",
          )}
        />
          <span className="text-xs font-medium text-foreground truncate" title={name}>
            {name}
          </span>
          <div className="ml-auto flex items-center gap-1.5 shrink-0">
            <DropIndicator dropped={frames_dropped} />
            <span className="text-[10px] text-muted-foreground/50">
              {device_type}
            </span>
          </div>
        </div>

        {/* LED preview */}
        <div className="px-3 py-2">
          <LedPreview frame={frame} ledCount={led_count} />
        </div>

        {/* Stats — single grid so columns align across all rows */}
        <div className="grid grid-cols-[auto_1fr_auto] gap-x-3 gap-y-px border-t border-border/50 px-3 py-1.5 text-[11px] font-mono tabular-nums">
          <StatLabel tooltip="Frames sent per second. Session avg from 0.5s samples.">FPS</StatLabel>
          <span className={`text-center ${fpsColor(send_fps)}`}>{send_fps > 0 ? `${Math.round(send_fps)}` : "--"}</span>
          <span className="text-right text-muted-foreground/30">{Math.round(stats.avgFps)}</span>

          <StatLabel tooltip="Effective device latency (network + processing). Session avg from 0.5s samples.">Latency</StatLabel>
          <span className={`text-center ${latencyColor(effective_latency_ms)}`}>{effective_latency_ms > 0 ? `${Math.round(effective_latency_ms)}ms` : "--"}</span>
          <span className="text-right text-muted-foreground/30">{Math.round(stats.avgLatency)}ms</span>

          <StatLabel tooltip="Delivery ratio — % of frames produced by the engine that were actually sent to the device. Low values are normal for slow devices (WiFi) since the depth-1 slot overwrites unsent frames.">Delivery</StatLabel>
          <span className={`text-center ${deliveryColor(deliveryPct)}`}>{deliveryPct.toFixed(0)}%</span>
          <span className="text-right text-muted-foreground/30">{(100 - stats.avgDropPct).toFixed(0)}%</span>

          <StatLabel tooltip="Frames dropped over last 0.5s as %. Avg is mean over session.">Drop</StatLabel>
          <span className={`text-center ${dropColor(stats.dropPct)}`}>{stats.dropPct > 0 ? `${stats.dropPct.toFixed(1)}%` : "0%"}</span>
          <span className="text-right text-muted-foreground/30">{stats.avgDropPct.toFixed(1)}%</span>
        </div>
      </div>
  )
}

function StatLabel({ children, tooltip }: { children: string; tooltip: string }) {
  return (
    <Tooltip>
      <TooltipTrigger className="text-left text-[10px] text-muted-foreground/50 uppercase tracking-wider cursor-help">
        {children}
      </TooltipTrigger>
      <TooltipContent side="right" className="max-w-[200px] text-xs">
        {tooltip}
      </TooltipContent>
    </Tooltip>
  )
}

export function DeviceMonitor({ devices, frameData }: DeviceMonitorProps) {
  if (devices.length === 0) {
    return (
      <div className="flex items-center justify-center h-16 border border-dashed border-border rounded-lg">
        <p className="text-xs text-muted-foreground">No devices connected</p>
      </div>
    )
  }

  return (
    <div className="border border-border rounded-lg">
      <div className="px-3 py-1.5 border-b border-border flex items-center gap-2">
        <span className="text-[10px] uppercase tracking-widest text-muted-foreground font-semibold">
          Devices
        </span>
        <span className="text-[10px] text-muted-foreground">
          {devices.filter((d) => d.connected).length}/{devices.length} online
        </span>
      </div>
      <TooltipProvider>
        <ScrollArea className="w-full">
          <div className="flex gap-2 p-2">
            {devices.map((device) => (
              <DeviceCard
                key={device.name}
                device={device}
                frame={frameData.get(device.name)}
              />
            ))}
          </div>
          <ScrollBar orientation="horizontal" />
        </ScrollArea>
      </TooltipProvider>
    </div>
  )
}
