import type { ReactNode } from 'react'
import { ChromeAttention, ChromeConnection, ChromePreviewOnly } from '@/chrome/live'

export interface PhoneHeaderProps {
  title: string
  context?: ReactNode
  /** Drawn under the title row, inside the banner: the tempo strip on Live. */
  children?: ReactNode
}

/** §4.2 phone header (Phone-Live.png): serif title and context; reconnect, eye and attention. */
export function PhoneHeader({ title, context, children }: PhoneHeaderProps) {
  return (
    <header className="shrink-0">
      <div className="flex h-(--phone-header-h) items-center justify-between gap-2 px-4">
        <div className="flex min-w-0 flex-col">
          <h1 className="truncate font-serif text-display-md leading-none">{title}</h1>
          {context && <span className="mt-0.75 truncate text-meta text-text-3">{context}</span>}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <ChromeConnection variant="header" />
          <ChromePreviewOnly variant="header" />
          <ChromeAttention variant="header" />
        </div>
      </div>
      {children}
    </header>
  )
}
