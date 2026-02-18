import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { apiFetchJson, fetchJsonUrl, openWebSocket } from './transport'

describe('transport helpers', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn()
    globalThis.WebSocket = vi.fn((url) => ({ url }))
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('apiFetchJson routes requests through buildApiUrl with query support', async () => {
    fetch.mockResolvedValue({
      ok: true,
      text: vi.fn().mockResolvedValue('{"ok":true}'),
    })

    const { data } = await apiFetchJson('/api/test', {
      query: { q: 'hello world', tag: ['a', 'b'] },
      method: 'POST',
    })

    expect(fetch).toHaveBeenCalledTimes(1)
    const [url, init] = fetch.mock.calls[0]
    expect(url).toContain('/api/test?q=hello+world&tag=a&tag=b')
    expect(init.method).toBe('POST')
    expect(data).toEqual({ ok: true })
  })

  it('openWebSocket builds websocket URLs from shared API base', () => {
    openWebSocket('/ws/pty', { query: { session_id: 'abc123', resume: '1' } })

    expect(WebSocket).toHaveBeenCalledTimes(1)
    const [url] = WebSocket.mock.calls[0]
    expect(url).toContain('/ws/pty?session_id=abc123&resume=1')
  })

  it('fetchJsonUrl parses JSON responses for absolute URLs', async () => {
    fetch.mockResolvedValue({
      ok: true,
      text: vi.fn().mockResolvedValue('{"sessions":[]}'),
    })

    const { data } = await fetchJsonUrl('https://example.test/api/sessions')

    expect(fetch).toHaveBeenCalledWith('https://example.test/api/sessions', {})
    expect(data).toEqual({ sessions: [] })
  })
})
