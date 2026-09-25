import { Outlet } from 'react-router'
import { documentTitle, usePageMeta, type MetaContext } from '@/app/page-meta'
import { useConnectionNews } from '@/chrome/connection-news'
import { useConnectionStatus, useServerName, useSunset } from '@/chrome/hooks'
import { ChromeTempoStrip } from '@/chrome/live'
import { Announcer } from '@/design/announcer'
import { cx } from '@/design/cx'
import { useIsPhone } from '@/lib/use-media-query'
import { useNow } from '@/lib/use-now'
import { PhoneHeader } from './phone-header'
import { Rail } from './rail'
import { TabBar } from './tab-bar'
import { TopBar } from './top-bar'

/**
 * §4.1–4.2: rail and top bar on desktop; header (with the tempo strip on Live) and tab bar on phone.
 * `<main>` keeps its place in the tree, so crossing the breakpoint swaps the chrome without
 * remounting the page. The root alone keeps everything out of the safe-area insets (index.html
 * sets viewport-fit=cover): a notch, a home indicator, a phone turned sideways, in either layout.
 * The page's one status region sits outside the swapped chrome, so it's there before any news.
 * Each part of the chrome reads its own slice of the live store (src/chrome/live.tsx); the shell
 * follows only the link's status, for that news.
 */
export function AppShell() {
  const isPhone = useIsPhone()
  const meta = usePageMeta()
  const news = useConnectionNews(useConnectionStatus())
  const server = useServerName()

  return (
    <Announcer news={news}>
      <div
        className={cx(
          'h-dvh pt-[env(safe-area-inset-top)] pr-[env(safe-area-inset-right)] pb-[env(safe-area-inset-bottom)] pl-[env(safe-area-inset-left)]',
          isPhone ? 'flex flex-col' : 'grid grid-cols-[var(--rail-w)_minmax(0,1fr)] grid-rows-[var(--topbar-h)_minmax(0,1fr)]',
        )}
      >
        <title>{documentTitle(meta.title)}</title>
        {isPhone ? (
          <PhoneHeader title={meta.phoneTitle ?? meta.title} context={meta.phoneContext && <PageContext get={meta.phoneContext} />}>
            {meta.tempoStrip && <ChromeTempoStrip />}
          </PhoneHeader>
        ) : (
          <>
            <div className="row-span-2">
              <Rail server={server} />
            </div>
            <TopBar title={meta.title} context={meta.context && <PageContext get={meta.context} />} />
          </>
        )}
        <main className="min-h-0 flex-1 overflow-y-auto">
          <Outlet />
        </main>
        {isPhone && <TabBar />}
      </div>
    </Announcer>
  )
}

/** A page's context line. It alone reads the clock, so the minute ticking over redraws just the line. */
function PageContext({ get }: { get: (at: MetaContext) => string }) {
  return get({ now: useNow(), sunset: useSunset() })
}
