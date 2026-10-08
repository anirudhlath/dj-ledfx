// The consequence line's words (§8.2; consequence.ts), each look's name in serif italic as the renders
// draw it, at each one's size (Live-PutLookOn, Phone-PutLookOn), which the caller's class gives.
import type { ConsequencePart } from './consequence'

export function ConsequenceText({ parts, lookClassName }: { parts: readonly ConsequencePart[]; lookClassName: string }) {
  return parts.map((part, index) =>
    part.look === true ? (
      <span key={index} className={lookClassName}>
        {part.text}
      </span>
    ) : (
      part.text
    ),
  )
}
