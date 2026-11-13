import { cx } from './cx'
import { Icon } from './icon'

export interface SearchFieldProps {
  value: string
  onValueChange: (value: string) => void
  placeholder: string
  /** The input's name for a screen reader, which the face doesn't draw. */
  label: string
  /** The face's own size and place (its height, width and positioning, and where it needs `touch-target`); it brings none of them itself. */
  className?: string
}

/**
 * The search box the composer's panel and the Looks library's filter bar share: a search icon and the input on a control face. The whole
 * face is the input's label, so a click on the icon or the padding focuses the input too, and the ring is the label's, as the input
 * draws none. An Esc clears a search that has words in it and marks the key handled (`preventDefault()`), and leaves a blank one's alone
 * for the page's own Esc (CLAUDE.md: Base UI's lists stop Esc, so a page-wide Esc listens for a key not yet handled). The words are
 * trimmed, so a box of spaces has nothing to clear.
 */
export function SearchField({ value, onValueChange, placeholder, label, className }: SearchFieldProps) {
  return (
    <label
      className={cx(
        'flex cursor-text items-center gap-2 rounded-control border border-line bg-control px-3 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-text',
        className,
      )}
    >
      <Icon name="search" size={15} className="text-text-3" />
      <span className="sr-only">{label}</span>
      <input
        type="search"
        value={value}
        placeholder={placeholder}
        className="min-w-0 grow bg-transparent text-size-control text-text outline-none placeholder:text-text-3 [&::-webkit-search-cancel-button]:appearance-none"
        onChange={(event) => onValueChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key !== 'Escape' || value.trim() === '') return
          event.preventDefault()
          onValueChange('')
        }}
      />
    </label>
  )
}
