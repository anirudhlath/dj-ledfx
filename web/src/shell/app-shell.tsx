import { Outlet } from 'react-router'
import { usePageMeta } from '@/app/page-meta'
import { useChrome } from '@/chrome/state'
import { TempoModule } from '@/chrome/tempo-module'
import { useIsPhone } from '@/lib/use-media-query'
import { useNow } from '@/lib/use-now'
import { PhoneHeader } from './phone-header'
import { Rail } from './rail'
import { TabBar } from './tab-bar'
import { TopBar } from './top-bar'

/**
 * §4.1–4.2: rail and top bar on desktop; header (with the tempo strip on Live) and tab bar on phone.
 * `<main>` keeps its place in the tree, so crossing the breakpoint swaps the chrome without
 * remounting the page.
 */
export function AppShell() {
  const isPhone = useIsPhone()
  const meta = usePageMeta()
  const chrome = useChrome()
  const now = useNow()
  const at = { now, chrome }

  return (
    <div
      className={
        isPhone
          ? 'flex h-dvh flex-col pt-[env(safe-area-inset-top)]'
          : 'grid h-dvh grid-cols-[var(--rail-w)_minmax(0,1fr)] grid-rows-[var(--topbar-h)_minmax(0,1fr)]'
      }
    >
      <title>{`${meta.title} · dj-ledfx`}</title>
      {isPhone ? (
        <PhoneHeader title={meta.phoneTitle ?? meta.title} context={meta.phoneContext?.(at)} chrome={chrome}>
          {meta.tempoStrip && (
            <div className="mx-4 mt-1.5">
              <TempoModule variant="strip" {...chrome.tempo} />
            </div>
          )}
        </PhoneHeader>
      ) : (
        <div className="row-span-2">
          <Rail attention={chrome.attention} server={chrome.server} />
        </div>
      )}
      {!isPhone && <TopBar title={meta.title} context={meta.context?.(at)} chrome={chrome} />}
      <main className="min-h-0 flex-1 overflow-y-auto">
        <Outlet />
      </main>
      {isPhone && <TabBar attention={chrome.attention} />}
    </div>
  )
}
