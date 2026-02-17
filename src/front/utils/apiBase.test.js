import { describe, it, expect } from 'vitest'
import { __apiBaseTestUtils, buildWsUrl } from './apiBase'

describe('apiBase loopback rewrite', () => {
  it('rewrites loopback VITE_API_URL to current host for remote browser clients', () => {
    const rewritten = __apiBaseTestUtils.rewriteLoopbackForRemoteClient(
      'http://127.0.0.1:3456',
      {
        origin: 'http://213.32.19.186:5190',
        hostname: '213.32.19.186',
      },
    )
    expect(rewritten).toBe('http://213.32.19.186:3456')
  })

  it('keeps loopback VITE_API_URL when the browser itself is local', () => {
    const rewritten = __apiBaseTestUtils.rewriteLoopbackForRemoteClient(
      'http://127.0.0.1:3456',
      {
        origin: 'http://127.0.0.1:5190',
        hostname: '127.0.0.1',
      },
    )
    expect(rewritten).toBe('http://127.0.0.1:3456')
  })

  it('supports IPv6 loopback rewrite for remote browser hosts', () => {
    const rewritten = __apiBaseTestUtils.rewriteLoopbackForRemoteClient(
      'http://[::1]:3456',
      {
        origin: 'http://213.32.19.186:5190',
        hostname: '213.32.19.186',
      },
    )
    expect(rewritten).toBe('http://213.32.19.186:3456')
  })

  it('treats 5190 as a dev port for fallback API host resolution', () => {
    expect(__apiBaseTestUtils.isDevPort('5190')).toBe(true)
    expect(__apiBaseTestUtils.isDevPort('5173')).toBe(true)
    expect(__apiBaseTestUtils.isDevPort('8000')).toBe(false)
  })

  it('builds query strings from objects while skipping empty values', () => {
    expect(
      __apiBaseTestUtils.toSearchParams({
        q: 'hello',
        tag: ['a', 'b'],
        ignored: undefined,
      }),
    ).toBe('?q=hello&tag=a&tag=b')
  })

  it('serializes array query values as repeated parameters for websocket URLs', () => {
    const wsUrl = buildWsUrl('/ws/claude-stream', {
      session_id: 'abc123',
      file: ['one.txt', 'two.txt'],
    })

    expect(wsUrl).toContain('/ws/claude-stream?')
    expect(wsUrl).toContain('session_id=abc123')
    expect(wsUrl).toContain('file=one.txt')
    expect(wsUrl).toContain('file=two.txt')
  })
})
