import type { BeatState } from "@/lib/types"
import { ProgressTrack, ProgressIndicator, Progress } from "@/components/ui/progress"
import { Badge } from "@/components/ui/badge"

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

      {/* Beat indicators + phase bars */}
      <div className="flex flex-col justify-center gap-2 flex-1 min-w-0">
        {/* Beat position indicators */}
        <div className="flex items-center gap-2">
          {[1, 2, 3, 4].map((n) => {
            const isActive = isPlaying && beatPos === n
            return (
              <div
                key={n}
                className={[
                  "h-6 w-6 rounded flex items-center justify-center text-xs font-bold transition-all duration-75",
                  isActive
                    ? "bg-primary text-primary-foreground shadow-[0_0_8px_hsl(var(--primary)/0.6)]"
                    : "bg-muted text-muted-foreground",
                ].join(" ")}
              >
                {n}
              </div>
            )
          })}
          <div className="flex-1" />
          <Badge
            variant={isPlaying ? "default" : "outline"}
            className={[
              "text-xs uppercase tracking-widest font-mono",
              isPlaying
                ? "bg-green-600 text-white border-green-600"
                : "text-muted-foreground border-muted",
            ].join(" ")}
          >
            {isPlaying ? "PLAY" : "STOP"}
          </Badge>
        </div>

        {/* Phase progress bars */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-muted-foreground w-7 uppercase tracking-wider">Beat</span>
            <Progress value={beatPhase * 100} className="flex-1">
              <ProgressTrack className="h-2">
                <ProgressIndicator className="transition-none" />
              </ProgressTrack>
            </Progress>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-muted-foreground w-7 uppercase tracking-wider">Bar</span>
            <Progress value={barPhase * 100} className="flex-1">
              <ProgressTrack className="h-2">
                <ProgressIndicator className="transition-none bg-sky-500" />
              </ProgressTrack>
            </Progress>
          </div>
        </div>
      </div>

      {/* Source info */}
      <div className="flex flex-col justify-center items-end gap-1 min-w-[80px]">
        {deckName && (
          <span className="text-xs font-mono text-muted-foreground">{deckName}</span>
        )}
        {pitchPercent !== null && (
          <span
            className={[
              "text-xs font-mono",
              pitchPercent > 0
                ? "text-amber-400"
                : pitchPercent < 0
                  ? "text-sky-400"
                  : "text-muted-foreground",
            ].join(" ")}
          >
            {pitchPercent > 0 ? "+" : ""}
            {pitchPercent.toFixed(1)}%
          </span>
        )}
      </div>
    </div>
  )
}
