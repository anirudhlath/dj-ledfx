// A browser without WebGL 2, or with it switched off, can't draw the home. It says so where the stage
// would be; the room links (room-links.tsx) and the Running panel still work.
import { EmptyState } from '@/pages/empty-state'

export function NoWebGL() {
  return (
    <div className="absolute inset-0 grid place-items-center p-6">
      <EmptyState title="The home can't be drawn here">This browser has WebGL switched off, so the 3D home can't be shown. Everything else still works.</EmptyState>
    </div>
  )
}
