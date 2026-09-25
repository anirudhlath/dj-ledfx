import type { LiveSocket, OpenSocket } from '@/api/live-client'
import type { ClientCommand } from '@/api/ws-messages'

/** A socket a test drives by hand: it opens, speaks and closes when told to. */
export class FakeSocket implements LiveSocket {
  binaryType: BinaryType = 'blob'
  onopen: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  readonly url: string
  /** What the client sent, parsed. */
  readonly sent: ClientCommand[] = []
  closed = false

  constructor(url: string) {
    this.url = url
  }

  send(data: string): void {
    this.sent.push(JSON.parse(data) as ClientCommand)
  }

  close(): void {
    this.closed = true
  }

  open(): void {
    this.onopen?.(new Event('open'))
  }

  /** The server sends a JSON message. */
  say(message: object): void {
    this.onmessage?.({ data: JSON.stringify(message) } as MessageEvent)
  }

  /** The server sends raw text or a binary frame. */
  sayRaw(data: string | ArrayBuffer): void {
    this.onmessage?.({ data } as MessageEvent)
  }

  /** The link drops. */
  drop(): void {
    this.onclose?.({} as CloseEvent)
  }

  /** The id the client gave its last command of this kind. */
  idOf(action: ClientCommand['action']): number {
    const command = this.sent.findLast((sent) => sent.action === action)
    if (command === undefined) throw new Error(`the client never sent ${action}`)
    return command.id
  }
}

export function fakeSockets(): { sockets: FakeSocket[]; open: OpenSocket } {
  const sockets: FakeSocket[] = []
  return {
    sockets,
    open: (url) => {
      const socket = new FakeSocket(url)
      sockets.push(socket)
      return socket
    },
  }
}
