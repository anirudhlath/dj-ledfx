// §14 Accessibility: "the stage has an accessible alternative (the Running panel and a zone list with
// room buttons)". The rooms with lights, as links to the composer: out of sight until one has focus.
import { Link } from 'react-router'
import type { Room } from '@/api/contract'

export interface RoomLinksProps {
  rooms: readonly Room[]
  to: (room: Room) => string
}

export function RoomLinks({ rooms, to }: RoomLinksProps) {
  const withLights = rooms.filter((room) => room.hasLights)
  if (withLights.length === 0) return null
  return (
    <nav
      aria-label="Rooms"
      className="sr-only focus-within:not-sr-only focus-within:absolute focus-within:inset-x-0 focus-within:bottom-0 focus-within:flex focus-within:flex-wrap focus-within:gap-2 focus-within:bg-panel focus-within:p-3"
    >
      {withLights.map((room) => (
        <Link key={room.id} to={to(room)} className="rounded-control border border-line bg-control px-3 py-1.5 text-size-control text-text">
          Put a look on {room.name}
        </Link>
      ))}
    </nav>
  )
}
