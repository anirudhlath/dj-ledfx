import { useBeat } from "@/hooks/use-beat"
import { useEffects } from "@/hooks/use-effects"
import { useDevices } from "@/hooks/use-devices"
import { TransportSection } from "@/components/transport-section"
import { EffectDeck } from "@/components/effect-deck"
import { DeviceMonitor } from "@/components/device-monitor"
import { Card, CardContent } from "@/components/ui/card"

export default function LivePage() {
  const beat = useBeat()
  const effects = useEffects()
  const { devices, frameData } = useDevices()

  return (
    <div className="flex flex-col gap-3 h-full">
      {/* Transport */}
      <TransportSection beat={beat} />

      {/* Middle: Effect deck + Scene preview */}
      <div className="flex gap-3 flex-1 min-h-0">
        {/* Effect deck — takes up most space */}
        <div className="flex-1 min-w-0 min-h-0">
          <EffectDeck
            schemas={effects.schemas}
            activeEffect={effects.activeEffect}
            activeParams={effects.activeParams}
            presets={effects.presets}
            loading={effects.loading}
            switchEffect={effects.switchEffect}
            updateParam={effects.updateParam}
            loadPreset={effects.loadPreset}
            savePreset={effects.savePreset}
          />
        </div>

        {/* Scene preview placeholder */}
        <div className="w-56 shrink-0">
          <Card className="h-full">
            <CardContent className="flex flex-col items-center justify-center h-full text-center px-4">
              <span className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                Scene Editor
              </span>
              <span className="mt-1 text-[10px] text-muted-foreground/60 uppercase tracking-wider">
                Phase 2
              </span>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Device monitor strip */}
      <DeviceMonitor devices={devices} frameData={frameData} />
    </div>
  )
}
