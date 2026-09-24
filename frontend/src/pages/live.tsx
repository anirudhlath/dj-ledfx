import { useState } from "react"
import { useBeat } from "@/hooks/use-beat"
import { useEffects } from "@/hooks/use-effects"
import { useDevices } from "@/hooks/use-devices"
import { useScene } from "@/hooks/use-scene"
import { useZones } from "@/hooks/use-zones"
import { LookPicker } from "@/components/look-picker"
import { TempoSection } from "@/components/tempo-section"
import { EffectDeck } from "@/components/effect-deck"
import { DeviceMonitor } from "@/components/device-monitor"
import SceneViewport from "@/components/scene/scene-viewport"
import DeviceMesh from "@/components/scene/device-mesh"

export default function LivePage() {
  const beat = useBeat()
  const home = useZones()
  const [chosenZone, setChosenZone] = useState<string | null>(null)
  const zoneId = chosenZone ?? home.running[0]?.zoneId ?? home.zones[0]?.id ?? null
  const lookId = home.running.find((r) => r.zoneId === zoneId)?.lookId ?? null
  const effects = useEffects(zoneId, lookId)
  const { devices, frameData } = useDevices()
  const { scene } = useScene()

  const placements = scene?.placements ?? []

  return (
    <div className="flex flex-col gap-3 h-full">
      {/* Put a look on a zone */}
      <LookPicker
        zones={home.zones}
        looks={home.looks}
        running={home.running}
        previewOnly={home.previewOnly}
        zoneId={zoneId}
        onZoneChange={setChosenZone}
        onStart={home.start}
        onOff={home.off}
        onPreviewOnlyChange={home.setPreviewOnly}
      />

      {/* Tempo */}
      <TempoSection beat={beat} />

      {/* Middle: Scene preview + Effect deck */}
      <div className="flex gap-3 flex-1 min-h-0">
        {/* Live 3D scene preview */}
        <div className="flex-1 min-w-0 min-h-0 rounded-lg border border-border overflow-hidden">
          <SceneViewport>
            {placements.map((p) => (
              <DeviceMesh
                key={p.device_id}
                position={p.position}
                geometry={p.geometry}
                ledCount={p.led_count}
                frameData={frameData.get(p.device_id) ?? null}
              />
            ))}
          </SceneViewport>
        </div>

        {/* Effect deck: the chosen zone's classic effect */}
        <div className="w-80 shrink-0 min-h-0">
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
      </div>

      {/* Device monitor strip */}
      <DeviceMonitor devices={devices} frameData={frameData} />
    </div>
  )
}
