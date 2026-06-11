import { useMemo, useState } from "react"
import { useBeat } from "@/hooks/use-beat"
import { useEffects } from "@/hooks/use-effects"
import { useSceneEffects } from "@/hooks/use-scene-effects"
import { useDevices } from "@/hooks/use-devices"
import { useScene } from "@/hooks/use-scene"
import { useScenes } from "@/hooks/use-scenes"
import { useTransport } from "@/hooks/use-transport"
import { TransportSection } from "@/components/transport-section"
import { EffectDeck } from "@/components/effect-deck"
import type { EffectDeckProps } from "@/components/effect-deck"
import { DeviceMonitor } from "@/components/device-monitor"
import SceneViewport from "@/components/scene/scene-viewport"
import DeviceMesh from "@/components/scene/device-mesh"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { EffectParamSchema, Preset } from "@/lib/types"

const GLOBAL_TAB = "__global__"

function SceneEffectDeck({
  sceneId,
  schemas,
  presets,
}: {
  sceneId: string
  schemas: Record<string, Record<string, EffectParamSchema>>
  presets: Preset[]
}) {
  const sceneEffects = useSceneEffects(sceneId, schemas, presets)
  return <EffectDeck {...(sceneEffects as EffectDeckProps)} />
}

export default function LivePage() {
  const beat = useBeat()
  const effects = useEffects()
  const { devices, frameData } = useDevices()
  const { transportState, setTransportState } = useTransport()
  const { scenes } = useScenes(devices)

  const activeScenes = useMemo(
    () => scenes.filter((s) => s.is_active),
    [scenes],
  )

  // "__global__" is the global/default-pipeline deck; it cannot collide with a
  // scene id (scene ids are UUIDs or the TOML-migrated "default").
  const [selectedTab, setSelectedTab] = useState(GLOBAL_TAB)
  const currentTab = activeScenes.some((s) => s.id === selectedTab) ? selectedTab : GLOBAL_TAB

  const { scene } = useScene(currentTab === GLOBAL_TAB ? null : currentTab)
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
                <TabsTrigger value={GLOBAL_TAB}>Global</TabsTrigger>
                {activeScenes.map((s) => (
                  <TabsTrigger key={s.id} value={s.id}>
                    {s.name}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
          )}

          <div className="flex-1 min-h-0">
            {currentTab === GLOBAL_TAB ? (
              <EffectDeck {...effects} />
            ) : (
              <SceneEffectDeck
                key={currentTab}
                sceneId={currentTab}
                schemas={effects.schemas}
                presets={effects.presets}
              />
            )}
          </div>
        </div>
      </div>

      {/* Device monitor strip */}
      <DeviceMonitor devices={devices} frameData={frameData} />
    </div>
  )
}
