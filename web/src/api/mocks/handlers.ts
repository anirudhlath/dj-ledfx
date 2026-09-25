// MSW's handlers over a MockServer (spec §12.5): every /api request, and the /ws socket.
import { HttpResponse, http, ws } from 'msw'
import type { MockServer } from './mock-server'

export function mockHandlers(server: MockServer, socketUrl: string) {
  return [
    http.all('*/api/*', async ({ request }) => {
      const text = await request.text()
      let body: unknown
      try {
        body = text === '' ? undefined : JSON.parse(text)
      } catch {
        return HttpResponse.json({ detail: 'Invalid JSON' }, { status: 400 })
      }
      const reply = server.handle(request.method, new URL(request.url).pathname, body)
      return reply.body === undefined
        ? new HttpResponse(null, { status: reply.status })
        : HttpResponse.json(reply.body, { status: reply.status })
    }),
    ws.link(socketUrl).addEventListener('connection', ({ client }) => {
      const session = server.connect({ send: (data) => client.send(data), close: () => client.close() })
      if (session === null) {
        client.close()
        return
      }
      client.addEventListener('message', (event) => {
        if (typeof event.data === 'string') server.receive(session, event.data)
      })
      client.addEventListener('close', () => server.disconnect(session))
    }),
  ]
}
