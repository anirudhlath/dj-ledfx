import { renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { fakeSockets } from '@/test/fake-socket'
import { startDataLayer } from './live'
import { useFxStream } from './use-fx'

describe('useFxStream', () => {
  it('asks for the fx channel while the stage draws the effects in space, and lets go when it stops or goes', () => {
    const { sockets, open } = fakeSockets()
    startDataLayer({ openSocket: open, url: 'ws://test/ws' })
    sockets[0].open()
    const asked = () => sockets[0].sent.filter((command) => command.action === 'subscribe_fx').map((command) => command.on)
    const { rerender, unmount } = renderHook(({ on }) => useFxStream(on), { initialProps: { on: false } })
    expect(asked()).toEqual([])
    rerender({ on: true })
    rerender({ on: false })
    rerender({ on: true })
    unmount()
    expect(asked()).toEqual([true, false, true, false])
  })
})
