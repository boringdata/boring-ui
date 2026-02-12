/**
 * Tests for authSSE utility — EventSource wrapper with qpToken auth.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createAuthSSE } from './authSSE'

// Track EventSource instances created during tests
let esInstances = []
const OriginalEventSource = EventSource

describe('createAuthSSE', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    esInstances = []

    // Wrap global EventSource to track instances
    vi.stubGlobal(
      'EventSource',
      class TrackingEventSource extends OriginalEventSource {
        constructor(url) {
          super(url)
          esInstances.push(this)
        }
      },
    )
    // Copy static constants
    EventSource.CONNECTING = 0
    EventSource.OPEN = 1
    EventSource.CLOSED = 2
  })

  afterEach(() => {
    vi.useRealTimers()
    esInstances.forEach((es) => es.close?.())
    esInstances = []
  })

  it('creates EventSource with token as query param', () => {
    const conn = createAuthSSE(
      'http://127.0.0.1:2468/v1/events/sse',
      'my-token',
    )
    expect(esInstances).toHaveLength(1)
    expect(esInstances[0].url).toContain('token=my-token')
    expect(esInstances[0].url).toContain('http://127.0.0.1:2468/v1/events/sse')
    conn.close()
  })

  it('creates EventSource without token when qpToken is null', () => {
    const conn = createAuthSSE(
      'http://127.0.0.1:2468/v1/events/sse',
      null,
    )
    expect(esInstances[0].url).not.toContain('token=')
    expect(esInstances[0].url).toBe('http://127.0.0.1:2468/v1/events/sse')
    conn.close()
  })

  it('appends token with & when URL already has query params', () => {
    const conn = createAuthSSE(
      'http://127.0.0.1:2468/v1/events/sse?format=json',
      'tok',
    )
    expect(esInstances[0].url).toContain('format=json')
    expect(esInstances[0].url).toContain('&token=tok')
    conn.close()
  })

  it('calls onOpen when connection opens', async () => {
    const onOpen = vi.fn()
    const conn = createAuthSSE(
      'http://127.0.0.1:2468/v1/events/sse',
      'tok',
      { onOpen },
    )

    await vi.advanceTimersByTimeAsync(10)

    expect(onOpen).toHaveBeenCalledTimes(1)
    conn.close()
  })

  it('calls onMessage with parsed JSON data', async () => {
    const onMessage = vi.fn()
    const conn = createAuthSSE(
      'http://127.0.0.1:2468/v1/events/sse',
      'tok',
      { onMessage },
    )

    await vi.advanceTimersByTimeAsync(10)

    const es = esInstances[0]
    es.simulateMessage({ type: 'item.delta', data: 'hello' })

    expect(onMessage).toHaveBeenCalledWith({ type: 'item.delta', data: 'hello' })
    conn.close()
  })

  it('calls onMessage with raw wrapper for non-JSON data', async () => {
    const onMessage = vi.fn()
    const conn = createAuthSSE(
      'http://127.0.0.1:2468/v1/events/sse',
      'tok',
      { onMessage },
    )

    await vi.advanceTimersByTimeAsync(10)

    const es = esInstances[0]
    es.onmessage?.(new MessageEvent('message', { data: 'not json' }))

    expect(onMessage).toHaveBeenCalledWith({ raw: 'not json' })
    conn.close()
  })

  it('calls onError on EventSource error', async () => {
    const onError = vi.fn()
    const conn = createAuthSSE(
      'http://127.0.0.1:2468/v1/events/sse',
      'tok',
      { onError },
    )

    await vi.advanceTimersByTimeAsync(10)

    const es = esInstances[0]
    es.simulateError()

    expect(onError).toHaveBeenCalledTimes(1)
    conn.close()
  })

  it('calls onTokenExpired after 2+ errors when connection CLOSED', async () => {
    const onTokenExpired = vi.fn()
    const conn = createAuthSSE(
      'http://127.0.0.1:2468/v1/events/sse',
      'tok',
      { onTokenExpired },
    )

    await vi.advanceTimersByTimeAsync(10)

    const es = esInstances[0]
    es.simulateError()
    expect(onTokenExpired).not.toHaveBeenCalled()

    es.readyState = EventSource.CLOSED
    es.simulateError()
    expect(onTokenExpired).toHaveBeenCalledTimes(1)

    conn.close()
  })

  it('does not call onTokenExpired if readyState is not CLOSED', async () => {
    const onTokenExpired = vi.fn()
    const conn = createAuthSSE(
      'http://127.0.0.1:2468/v1/events/sse',
      'tok',
      { onTokenExpired },
    )

    await vi.advanceTimersByTimeAsync(10)

    const es = esInstances[0]
    // Keep readyState as OPEN (not CLOSED)
    es.readyState = EventSource.OPEN
    es.onerror?.(new Event('error'))
    es.onerror?.(new Event('error'))

    expect(onTokenExpired).not.toHaveBeenCalled()
    conn.close()
  })

  it('resets error count on successful open', async () => {
    const onTokenExpired = vi.fn()
    const conn = createAuthSSE(
      'http://127.0.0.1:2468/v1/events/sse',
      'tok',
      { onTokenExpired },
    )

    await vi.advanceTimersByTimeAsync(10)

    const es = esInstances[0]
    es.simulateError()

    // Re-open resets count
    es.onopen?.(new Event('open'))

    es.readyState = EventSource.CLOSED
    es.simulateError()
    expect(onTokenExpired).not.toHaveBeenCalled()

    conn.close()
  })

  it('close() calls EventSource.close()', async () => {
    const conn = createAuthSSE(
      'http://127.0.0.1:2468/v1/events/sse',
      'tok',
    )

    await vi.advanceTimersByTimeAsync(10)

    const es = esInstances[0]
    conn.close()
    expect(es.close).toHaveBeenCalled()
  })

  it('encodes special characters in token', () => {
    const conn = createAuthSSE(
      'http://127.0.0.1:2468/v1/events/sse',
      'token with spaces&special=chars',
    )
    expect(esInstances[0].url).toContain('token=token%20with%20spaces%26special%3Dchars')
    conn.close()
  })
})
