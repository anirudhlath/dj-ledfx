import { useState } from "react"
import { useBeat } from "@/hooks/use-beat"
import { useEffects } from "@/hooks/use-effects"
import { useSceneEffects } from "@/hooks/use-scene-effects"
import { useDevices } from "@/hooks/use-devices"
import { useScene } from "@/hooks/use-scene"
import { useScenes } from "@/hooks/use-scenes"
import { useTransport } from "@/hooks/use-transport"
import { TransportSection } from "@/components/transport-section"
import { EffectDeck } from "@/components/effect-deck"
import { DeviceMonitor } from "@/components/device-monitor"
import SceneViewport from "@/components/scene/scene-viewport"
import DeviceMesh from "@/components/scene/device-mesh"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"

function SceneEffectDeck({ sceneId }: { sceneId: string }) {
  const sceneEffects = useSceneEffects(sceneId)
  return (
    <EffectDeck
      schemas={sceneEffects.schemas}
      activeEffect={sceneEffects.activeEffect}
      activeParams={sceneEffects.activeParams}
      presets={sceneEffects.presets}
      loading={sceneEffects.loading}
      switchEffect={sceneEffects.switchEffect}
      updateParam={sceneEffects.updateParam}
      loadPreset={sceneEffects.loadPreset}
      savePreset={sceneEffects.savePreset}
    />
  )
}

export default function LivePage() {
  const beat = useBeat()
  const effects = useEffects()
  const { devices, frameData } = useDevices()
  const { transportState, setTransportState } = useTransport()
  const { scenes } = useScenes(devices)

  const activeScenes = scenes.filter((s) => s.is_active && s.id !== "default")

  const [selectedTab, setSelectedTab] = useState("default")
  const currentTab = activeScenes.some((s) => s.id === selectedTab) ? selectedTab : "default"

  const { scene } = useScene(currentTab === "default" ? null : currentTab)
  const placements = scene?.placements ?? []

  return (
    <div className="flex flex-col gap-3 h-full">
      {/* Transport */}
      <TransportSection beat={beat} transportState={transportState} onTransportChange={setTransportState} />

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

        {/* Effect deck column */}
        <div className="w-80 shrink-0 flex flex-col gap-2 min-h-0">
          {activeScenes.length > 0 && (
            <Tabs value={currentTab} onValueChange={setSelectedTab}>
              <TabsList className="w-full">
                <TabsTrigger value="default">Default</TabsTrigger>
                {activeScenes.map((s) => (
                  <TabsTrigger key={s.id} value={s.id}>
                    {s.name}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
          )}

          <div className="flex-1 min-h-0">
            {currentTab === "default" ? (
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
            ) : (
              <SceneEffectDeck key={currentTab} sceneId={currentTab} />
            )}
          </div>
        </div>
      </div>

      {/* Device monitor strip */}
      <DeviceMonitor devices={devices} frameData={frameData} />
    </div>
  )
}
