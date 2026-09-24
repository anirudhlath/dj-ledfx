import type { ReactNode } from 'react'
import { AttentionButton } from '@/chrome/attention-button'
import { ConnectionIndicator } from '@/chrome/connection-indicator'
import type { ChromeState } from '@/chrome/state'
import { PreviewOnlySwitch } from '@/chrome/preview-only-switch'

export interface PhoneHeaderProps {
  title: string
  context?: string
  chrome: ChromeState
  /** Drawn under the title row, inside the banner: the tempo strip on Live. */
  children?: ReactNode
}

/** §4.2 phone header (Phone-Live.png): serif title and context; reconnect, eye and attention. */
export function PhoneHeader({ title, context, chrome, children }: PhoneHeaderProps) {
  return (
    <header className="shrink-0">
      <div className="flex h-(--phone-header-h) items-center justify-between gap-2 px-4">
        <div className="flex min-w-0 flex-col">
          <h1 className="truncate font-serif text-display-md leading-none">{title}</h1>
          {context && <span className="mt-0.75 truncate text-meta text-text-3">{context}</span>}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <ConnectionIndicator variant="header" connection={chrome.connection} />
          <PreviewOnlySwitch variant="header" on={chrome.previewOnly} />
          <AttentionButton variant="header" count={chrome.attention.total} />
        </div>
      </div>
      {children}
    </header>
  )
}
