import { useRef, useState, useLayoutEffect } from "react"
import type { BeatState } from "@/lib/types"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"

function BeatGrid({
  isPlaying,
  beatPos,
  beatPhase,
  barPhase,
}: {
  isPlaying: boolean
  beatPos: number
  beatPhase: number
  barPhase: number
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [boxSize, setBoxSize] = useState(0)
  const gap = 4 // gap-1 = 0.25rem = 4px
  const barH = 6 // h-1.5 = 0.375rem = 6px
  const barGap = 6 // gap-1.5 = 0.375rem = 6px

  useLayoutEffect(() => {
    const el = containerRef.current
    if (!el) return
    const obs = new ResizeObserver(([entry]) => {
      // available height for boxes = container height - bar height - gap between rows
      const available = entry.contentRect.height - barH - barGap
      setBoxSize(Math.max(0, Math.floor(available)))
    })
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  return (
    <div ref={containerRef} className="flex flex-col items-center justify-center gap-1.5 self-stretch py-1">
      <div className="flex gap-1">
        {[1, 2, 3, 4].map((n) => {
          const isActive = isPlaying && beatPos === n
          const fillPercent = isActive ? beatPhase * 100 : 0
          return (
            <div
              key={n}
              className="relative rounded overflow-hidden flex items-center justify-center bg-muted shrink-0"
              style={{ width: boxSize, height: boxSize }}
            >
              <div
                className="absolute top-0 bottom-0 left-0 bg-primary transition-none"
                style={{ width: `${fillPercent}%` }}
              />
              <span
                className={cn(
                  "relative z-10 text-xs font-bold",
                  isActive ? "text-primary-foreground" : "text-muted-foreground",
                )}
              >
                {n}
              </span>
            </div>
          )
        })}
      </div>
      {/* Bar progress — same total width as the 4 boxes + gaps */}
      <div
        className="relative h-1.5 rounded-full bg-muted overflow-hidden"
        style={{ width: boxSize * 4 + gap * 3 }}
      >
        <div
          className="absolute top-0 bottom-0 left-0 bg-sky-500 transition-none rounded-full"
          style={{ width: `${barPhase * 100}%` }}
        />
      </div>
    </div>
  )
}

interface TransportSectionProps {
  beat: BeatState
}

export function TransportSection({ beat }: TransportSectionProps) {
  const { bpm, beatPhase, barPhase, isPlaying, beatPos, pitchPercent, deckName } = beat

  const bpmDisplay = bpm > 0 ? bpm.toFixed(1) : "---.-"

  return (
    <div className="flex items-stretch gap-4 p-3 bg-card ring-1 ring-foreground/10 rounded-xl">
      {/* BPM — most prominent */}
      <div className="flex flex-col items-center justify-center min-w-[110px] px-3">
        <span className="text-5xl font-mono font-bold tracking-tight text-foreground leading-none">
          {bpmDisplay}
        </span>
        <span className="text-xs text-muted-foreground mt-1 uppercase tracking-widest">BPM</span>
      </div>

      <div className="w-px bg-border self-stretch" />

      {/* Beat grid — centered, square boxes sized to parent height */}
      <div className="flex-1 flex items-stretch justify-center">
        <BeatGrid
          isPlaying={isPlaying}
          beatPos={beatPos}
          beatPhase={beatPhase}
          barPhase={barPhase}
        />
      </div>

      {/* Play state */}
      <div className="flex items-center">
        <Badge
          variant={isPlaying ? "default" : "outline"}
          className={cn(
            "text-xs uppercase tracking-widest font-mono",
            isPlaying
              ? "bg-green-600 text-white border-green-600"
              : "text-muted-foreground border-muted",
          )}
        >
          {isPlaying ? "PLAY" : "STOP"}
        </Badge>
      </div>

      {/* Source info */}
      <div className="flex flex-col justify-center items-end gap-1 min-w-[80px]">
        {deckName && (
          <span className="text-xs font-mono text-muted-foreground">{deckName}</span>
        )}
        {pitchPercent !== null && (
          <span
            className={cn(
              "text-xs font-mono",
              pitchPercent > 0
                ? "text-amber-400"
                : pitchPercent < 0
                  ? "text-sky-400"
                  : "text-muted-foreground",
            )}
          >
            {pitchPercent > 0 ? "+" : ""}
            {pitchPercent.toFixed(1)}%
          </span>
        )}
      </div>
    </div>
  )
}
