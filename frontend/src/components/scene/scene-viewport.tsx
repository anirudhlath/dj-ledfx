import { Canvas, useThree } from "@react-three/fiber"
import { OrbitControls, Grid, GizmoHelper, GizmoViewport, TransformControls } from "@react-three/drei"
import { type ReactNode, Suspense, useEffect } from "react"
import * as THREE from "three"

type CameraPreset = "Perspective" | "Top" | "Front" | "Side"

interface SceneViewportProps {
  children?: ReactNode
  onPointerMissed?: () => void
  transformTarget?: THREE.Object3D | null
  transformMode?: "translate" | "rotate"
  onTransformEnd?: (position: [number, number, number]) => void
  onTransformChange?: (target: THREE.Object3D) => void
  cameraPreset?: { name: CameraPreset; key: number } | null
  snapEnabled?: boolean
  snapIncrement?: number
}

function SceneContent({
  children,
  transformTarget,
  transformMode,
  onTransformEnd,
  onTransformChange,
  cameraPreset,
  snapEnabled,
  snapIncrement,
}: Omit<SceneViewportProps, "onPointerMissed">) {
  const { camera } = useThree()

  useEffect(() => {
    if (!cameraPreset) return
    const dist = 8
    switch (cameraPreset.name) {
      case "Top":
        camera.position.set(0, dist, 0)
        break
      case "Front":
        camera.position.set(0, 0, dist)
        break
      case "Side":
        camera.position.set(dist, 0, 0)
        break
      case "Perspective":
      default:
        camera.position.set(5, 5, 5)
        break
    }
    camera.lookAt(0, 0, 0)
  }, [cameraPreset, camera])

  return (
    <>
      <ambientLight intensity={0.4} />
      <directionalLight position={[10, 10, 5]} intensity={0.8} />
      <Grid
        args={[20, 20]}
        cellSize={0.5}
        cellThickness={0.5}
        cellColor="#404040"
        sectionSize={2}
        sectionThickness={1}
        sectionColor="#606060"
        fadeDistance={30}
        infiniteGrid
      />
      <OrbitControls makeDefault />
      <GizmoHelper alignment="bottom-right" margin={[60, 60]}>
        <GizmoViewport axisColors={["#f44", "#4f4", "#44f"]} labelColor="white" />
      </GizmoHelper>
      {transformTarget && (
        <TransformControls
          object={transformTarget}
          mode={transformMode ?? "translate"}
          translationSnap={snapEnabled && snapIncrement ? snapIncrement : null}
          onChange={() => {
            if (transformTarget && onTransformChange) {
              onTransformChange(transformTarget)
            }
          }}
          onMouseUp={() => {
            if (transformTarget) {
              // Clamp one final time before reading position
              if (onTransformChange) onTransformChange(transformTarget)
              if (onTransformEnd) {
                const pos = transformTarget.position
                onTransformEnd([pos.x, pos.y, pos.z])
              }
            }
          }}
        />
      )}
      {children}
    </>
  )
}

export default function SceneViewport({
  children,
  onPointerMissed,
  transformTarget,
  transformMode,
  onTransformEnd,
  onTransformChange,
  cameraPreset,
  snapEnabled,
  snapIncrement,
}: SceneViewportProps) {
  return (
    <Canvas
      camera={{ position: [5, 5, 5], fov: 60 }}
      onPointerMissed={onPointerMissed}
      className="rounded-lg"
      style={{ background: "hsl(var(--background))" }}
    >
      <Suspense fallback={null}>
        <SceneContent
          transformTarget={transformTarget}
          transformMode={transformMode}
          onTransformEnd={onTransformEnd}
          onTransformChange={onTransformChange}
          cameraPreset={cameraPreset}
          snapEnabled={snapEnabled}
          snapIncrement={snapIncrement}
        >
          {children}
        </SceneContent>
      </Suspense>
    </Canvas>
  )
}
