// A LiveSocket wired straight to a MockServer: the whole data layer runs in a test without MSW.
// It opens on the next timer and delivers each message in a microtask, as a real socket is async.
import type { LiveSocket, OpenSocket } from '../live-client'
import type { MockServer, MockSession } from './mock-server'

class InMemorySocket implements LiveSocket {
  binaryType: BinaryType = 'blob'
  onopen: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  private readonly server: MockServer
  private session: MockSession | null = null
  private closed = false

  constructor(server: MockServer) {
    this.server = server
    setTimeout(() => this.open(), 0)
  }

  send(data: string): void {
    if (this.session !== null && !this.closed) this.server.receive(this.session, data)
  }

  close(): void {
    if (this.closed) return
    this.closed = true
    if (this.session !== null) this.server.disconnect(this.session)
  }

  private open(): void {
    if (this.closed) return
    this.session = this.server.connect({ send: (data) => this.deliver(data), close: () => this.shut() })
    if (this.session === null) {
      this.shut()
      return
    }
    // The snapshots connect() sent are still in their microtasks, so open comes first, as on a real socket.
    this.onopen?.(new Event('open'))
  }

  private deliver(data: string | ArrayBuffer): void {
    queueMicrotask(() => {
      if (!this.closed) this.onmessage?.({ data } as MessageEvent)
    })
  }

  private shut(): void {
    if (this.closed) return
    this.closed = true
    queueMicrotask(() => this.onclose?.({} as CloseEvent))
  }
}

export function inMemorySockets(server: MockServer): OpenSocket {
  return () => new InMemorySocket(server)
}
