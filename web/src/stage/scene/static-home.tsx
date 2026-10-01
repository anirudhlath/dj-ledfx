// The static home on the canvas (§7.1): made once per home, recoloured when the view turns, sized to
// the stage. React doesn't dispose a <primitive>'s three objects, so this does when the home changes.
import { useThree } from '@react-three/fiber'
import { useEffect, useMemo } from 'react'
import type { Home } from '@/api/contract'
import { bearingDeg } from '../camera'
import { STAGE_PALETTE } from '../palette'
import { HomeScene } from './home-scene'

export interface StaticHomeProps {
  home: Home
  /** The camera's bearing (camera.ts's bearingDeg). */
  bearing: number
  width: number
  height: number
}

export function StaticHome({ home, bearing, width, height }: StaticHomeProps) {
  const scene = useMemo(() => new HomeScene(home, STAGE_PALETTE, bearingDeg(0)), [home])
  const pixelRatio = useThree((state) => state.viewport.dpr)
  const invalidate = useThree((state) => state.invalidate)
  useEffect(() => () => scene.dispose(), [scene])
  useEffect(() => {
    scene.turn(bearing)
    invalidate()
  }, [scene, bearing, invalidate])
  useEffect(() => {
    scene.setView({ width, height }, pixelRatio)
    invalidate()
  }, [scene, width, height, pixelRatio, invalidate])
  return <primitive object={scene.group} />
}
