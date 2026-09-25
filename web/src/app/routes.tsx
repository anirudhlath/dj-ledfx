import { Navigate, type RouteObject } from 'react-router'
import { formatDayDateTime, formatDayTime } from '@/lib/format'
import { AppError, RootError } from '@/pages/app-error'
import { NotFound } from '@/pages/not-found'
import { Placeholder } from '@/pages/placeholder'
import { AppShell } from '@/shell/app-shell'
import type { PageMeta } from './page-meta'

// Titles and context lines are the renders' (Main, Looks, Home-Map, Devices, Inputs, Settings and
// their Phone-* twins). Lines that count data ("29 looks · 3 running") arrive with that data.
const LIVE: PageMeta = {
  title: 'Live',
  context: ({ now }) => formatDayDateTime(now),
  phoneTitle: 'Home',
  phoneContext: ({ now, sunset }) => `${formatDayTime(now)} · sun sets ${sunset}`,
  tempoStrip: true,
}
const LOOKS: PageMeta = { title: 'Looks' }
const MAP: PageMeta = {
  title: 'Map',
  context: () => 'Place lights, anchors and sub-zones',
  phoneContext: () => 'Confirm guessed positions',
}
const DEVICES: PageMeta = { title: 'Devices', context: () => 'Lights and PC parts' }
const INPUTS: PageMeta = {
  title: 'Inputs',
  context: () => 'Tempo, music, Home Assistant, the sun',
  phoneTitle: 'Tempo',
  phoneContext: ({ now }) => formatDayDateTime(now),
}
const SETTINGS: PageMeta = { title: 'Settings' }

/** Spec §4.3. Paths are relative to the router's basename (/next until F11). */
export const routes: RouteObject[] = [
  {
    element: <AppShell />,
    // AppShell itself failed, so there's no chrome to keep.
    errorElement: <RootError />,
    children: [
      {
        // A page that throws, or a lazy page that fails to load, keeps the chrome around it.
        errorElement: <AppError />,
        children: [
          { index: true, element: <Navigate to="/live" replace /> },
          { path: 'live', handle: LIVE, element: <Placeholder name="Stage and Running panel" milestone="F2 and F3" /> },
          { path: 'live/put', handle: LIVE, element: <Placeholder name="Put a look on" milestone="F4" /> },
          { path: 'live/zones/:zoneId', handle: LIVE, element: <Placeholder name="Zone" milestone="F3" /> },
          { path: 'looks', handle: LOOKS, element: <Placeholder name="Looks" milestone="F5" /> },
          { path: 'looks/:lookId', handle: LOOKS, element: <Placeholder name="Look editor" milestone="F8" /> },
          { path: 'map', handle: MAP, element: <Placeholder name="Home map" milestone="F7" /> },
          { path: 'map/:thingId', handle: MAP, element: <Placeholder name="Home map" milestone="F7" /> },
          { path: 'devices', handle: DEVICES, element: <Placeholder name="Devices" milestone="F6" /> },
          { path: 'devices/:deviceId', handle: DEVICES, element: <Placeholder name="Devices" milestone="F6" /> },
          { path: 'inputs', handle: INPUTS, element: <Placeholder name="Inputs" milestone="F6" /> },
          { path: 'settings', handle: SETTINGS, element: <Placeholder name="Settings" milestone="F6" /> },
          // The primitives specimen loads on demand, keeping Base UI out of the first load.
          {
            path: 'system',
            handle: { title: 'System' } satisfies PageMeta,
            lazy: async () => ({ Component: (await import('@/pages/system')).SystemPage }),
          },
          { path: '*', handle: { title: 'Not found' } satisfies PageMeta, element: <NotFound /> },
        ],
      },
    ],
  },
]
