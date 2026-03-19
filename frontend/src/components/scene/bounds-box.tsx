import * as THREE from "three"
import { Edges } from "@react-three/drei"

const BOUNDS_COLOR = "#00ccff"

interface BoundsBoxProps {
  min: [number, number, number]
  max: [number, number, number]
}

export default function BoundsBox({ min, max }: BoundsBoxProps) {
  const center: [number, number, number] = [
    (min[0] + max[0]) / 2,
    (min[1] + max[1]) / 2,
    (min[2] + max[2]) / 2,
  ]
  const size: [number, number, number] = [
    max[0] - min[0],
    max[1] - min[1],
    max[2] - min[2],
  ]

  return (
    <group position={center}>
      <mesh>
        <boxGeometry args={size} />
        <meshStandardMaterial
          color={BOUNDS_COLOR}
          transparent
          opacity={0.03}
          side={THREE.DoubleSide}
          depthWrite={false}
        />
        <Edges threshold={1} color={BOUNDS_COLOR} />
      </mesh>
    </group>
  )
}
