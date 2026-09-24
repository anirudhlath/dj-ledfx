import { Select as BaseSelect } from '@base-ui/react/select'
import { useCallback, useRef } from 'react'
import { cx } from './cx'
import { Icon } from './icon'

export interface SelectProps<T extends string> {
  /** The accessible name of the trigger. */
  label: string
  value: T
  /** Value → label, in display order. */
  items: Record<T, string>
  onValueChange: (value: T) => void
  className?: string
}

/** Where the list opens: inside the dialog or the <main> around the trigger, else <body>. */
const HOSTS = '[role="dialog"], [role="alertdialog"], main'

/**
 * §6.1 SelectTrigger, opening a Base UI select list. The list opens inside the landmark (or dialog)
 * its trigger is in, rather than loose in <body>, so it's part of the page around it (axe's region
 * rule). Inside a dialog that scrolls, Base UI's collision handling keeps the list in view.
 */
export function Select<T extends string>({ label, value, items, onValueChange, className }: SelectProps<T>) {
  // Base UI reads the ref when the list opens; while it's empty (no host found) the list goes to <body>.
  const host = useRef<HTMLElement | null>(null)
  const findHost = useCallback((trigger: HTMLElement | null) => {
    host.current = trigger?.closest<HTMLElement>(HOSTS) ?? null
  }, [])
  return (
    <BaseSelect.Root
      items={items}
      value={value}
      onValueChange={(next) => {
        if (next !== null) onValueChange(next as T)
      }}
    >
      <BaseSelect.Trigger
        ref={findHost}
        aria-label={label}
        className={cx(
          'inline-flex h-8 min-w-0 items-center justify-between gap-2 rounded-control border border-line bg-control px-2.5 text-size-control font-medium text-text',
          className,
        )}
      >
        <BaseSelect.Value className="truncate" />
        <Icon name="down" size={14} className="text-text-3" />
      </BaseSelect.Trigger>
      <BaseSelect.Portal container={host}>
        <BaseSelect.Positioner sideOffset={4} alignItemWithTrigger={false} className="z-50">
          <BaseSelect.Popup className="min-w-(--anchor-width) rounded-card border border-line-strong bg-raised py-1 shadow-pop outline-none">
            <BaseSelect.List>
              {(Object.keys(items) as T[]).map((key) => (
                <BaseSelect.Item
                  key={key}
                  value={key}
                  className="flex h-8 cursor-pointer items-center justify-between gap-6 px-2.5 text-size-control text-text-2 outline-none select-none data-[highlighted]:bg-control data-[highlighted]:text-text data-[selected]:text-text"
                >
                  <BaseSelect.ItemText>{items[key]}</BaseSelect.ItemText>
                  <BaseSelect.ItemIndicator>
                    <Icon name="check" size={14} />
                  </BaseSelect.ItemIndicator>
                </BaseSelect.Item>
              ))}
            </BaseSelect.List>
          </BaseSelect.Popup>
        </BaseSelect.Positioner>
      </BaseSelect.Portal>
    </BaseSelect.Root>
  )
}
