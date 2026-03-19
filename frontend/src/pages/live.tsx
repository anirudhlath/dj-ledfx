import { useBeat } from "@/hooks/use-beat"
import { useEffects } from "@/hooks/use-effects"
import { useDevices } from "@/hooks/use-devices"
import { useScene } from "@/hooks/use-scene"
import { TransportSection } from "@/components/transport-section"
import { EffectDeck } from "@/components/effect-deck"
import { DeviceMonitor } from "@/components/device-monitor"
import SceneViewport from "@/components/scene/scene-viewport"
import DeviceMesh from "@/components/scene/device-mesh"

export default function LivePage() {
  const beat = useBeat()
  const effects = useEffects()
  const { devices, frameData } = useDevices()
  const { scene } = useScene()

  const placements = scene?.placements ?? []

  return (
    <div className="flex flex-col gap-3 h-full">
      {/* Transport */}
      <TransportSection beat={beat} />

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

        {/* Effect deck */}
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
