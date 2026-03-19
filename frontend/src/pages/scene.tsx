import { useRef, useState, useCallback } from "react"
import { toast } from "sonner"
import * as THREE from "three"
import { useScene } from "@/hooks/use-scene"
import { useDevices } from "@/hooks/use-devices"
import SceneViewport from "@/components/scene/scene-viewport"
import DeviceMesh from "@/components/scene/device-mesh"
import DeviceListPanel from "@/components/scene/device-list-panel"
import PropertiesPanel from "@/components/scene/properties-panel"
import SceneToolbar from "@/components/scene/scene-toolbar"
import MappingPreview from "@/components/scene/mapping-preview"
import type { Placement } from "@/lib/types"

export default function ScenePage() {
  const { scene, loading, movePlacement, removePlacement, changeMapping, addPlacement } = useScene()
  const { devices, frameData } = useDevices()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [transformMode, setTransformMode] = useState<"translate" | "rotate">("translate")
  const [cameraPreset, setCameraPreset] = useState<string | null>(null)
  const [snapEnabled, setSnapEnabled] = useState(false)
  const [snapIncrement, setSnapIncrement] = useState(0.5)

  const deviceRefs = useRef<Map<string, THREE.Group>>(new Map())
  const transformTarget = selectedId ? deviceRefs.current.get(selectedId) ?? null : null

  const selectedPlacement: Placement | null =
    scene?.placements.find((p) => p.device_id === selectedId) ?? null

  const selectedDevice = devices.find((d) => d.name === selectedId) ?? null

  const handlePositionChange = useCallback(
    async (deviceId: string, position: [number, number, number]) => {
      await movePlacement(deviceId, position)
      toast.success(`Moved ${deviceId}`)
    },
    [movePlacement]
  )

  const handleRemove = useCallback(
    async (deviceId: string) => {
      await removePlacement(deviceId)
      setSelectedId(null)
      toast.success(`Removed ${deviceId}`)
    },
    [removePlacement]
  )

  const handleMappingChange = useCallback(
    async (type: string) => {
      await changeMapping(type, {})
      toast.success(`Mapping set to ${type}`)
    },
    [changeMapping]
  )

  const handleTransformEnd = useCallback(
    async (position: [number, number, number]) => {
      if (selectedId) {
        await movePlacement(selectedId, position)
      }
    },
    [selectedId, movePlacement]
  )

  const handleAddDevice = useCallback(
    async (deviceName: string, ledCount: number) => {
      await addPlacement(deviceName, ledCount)
      setSelectedId(deviceName)
      toast.success(`Added ${deviceName} to scene`)
    },
    [addPlacement]
  )

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-muted-foreground">Loading scene...</p>
      </div>
    )
  }

  const placements = scene?.placements ?? []
  const mappingType = scene?.mapping?.type ?? "linear"

  return (
    <div className="flex flex-col h-full gap-0">
      <SceneToolbar
        transformMode={transformMode}
        onTransformModeChange={setTransformMode}
        mappingType={mappingType}
        onMappingTypeChange={handleMappingChange}
        onCameraPreset={setCameraPreset}
        snapEnabled={snapEnabled}
        onSnapToggle={setSnapEnabled}
        snapIncrement={snapIncrement}
        onSnapIncrementChange={setSnapIncrement}
      />

      <div className="flex-1 flex gap-2 min-h-0 p-2">
        <div className="w-52 shrink-0">
          <DeviceListPanel
            placements={placements}
            allDevices={devices}
            selectedDeviceId={selectedId}
            onSelectDevice={setSelectedId}
            onAddDevice={handleAddDevice}
          />
        </div>

        <div className="flex-1 min-w-0 rounded-lg border border-border overflow-hidden">
          <SceneViewport
            onPointerMissed={() => setSelectedId(null)}
            transformTarget={transformTarget}
            transformMode={transformMode}
            onTransformEnd={handleTransformEnd}
            cameraPreset={cameraPreset}
            snapEnabled={snapEnabled}
            snapIncrement={snapIncrement}
          >
            {placements.map((p) => (
              <DeviceMesh
                ref={(el) => {
                  if (el) deviceRefs.current.set(p.device_id, el)
                  else deviceRefs.current.delete(p.device_id)
                }}
                key={p.device_id}
                deviceId={p.device_id}
                position={p.position}
                geometry={p.geometry}
                ledCount={p.led_count}
                frameData={frameData.get(p.device_id) ?? null}
                selected={selectedId === p.device_id}
                onClick={(e) => {
                  e.stopPropagation()
                  setSelectedId(p.device_id)
                }}
              />
            ))}
          </SceneViewport>
        </div>

        <div className="w-56 shrink-0">
          <PropertiesPanel
            placement={selectedPlacement}
            deviceInfo={selectedDevice}
            onPositionChange={handlePositionChange}
            onRemove={handleRemove}
          />
        </div>
      </div>

      <MappingPreview
        placements={placements}
        frameData={frameData}
        selectedDeviceId={selectedId}
        onSelectDevice={setSelectedId}
      />
    </div>
  )
}
