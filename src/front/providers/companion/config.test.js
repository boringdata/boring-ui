import { describe, it, expect } from 'vitest'
import { __companionConfigTestUtils } from './config'

describe('companion config loopback rewrite', () => {
  it('rewrites localhost companion URL for remote browser clients', () => {
    const rewritten = __companionConfigTestUtils.rewriteLoopbackForRemoteClient(
      'http://localhost:3456',
      {
        origin: 'http://213.32.19.186:5190',
        hostname: '213.32.19.186',
      },
    )

    expect(rewritten).toBe('http://213.32.19.186:3456/')
  })

  it('keeps localhost companion URL for local browsers', () => {
    const rewritten = __companionConfigTestUtils.rewriteLoopbackForRemoteClient(
      'http://localhost:3456',
      {
        origin: 'http://localhost:5190',
        hostname: 'localhost',
      },
    )

    expect(rewritten).toBe('http://localhost:3456')
  })

  it('supports IPv6 loopback rewrite for remote browser hosts', () => {
    const rewritten = __companionConfigTestUtils.rewriteLoopbackForRemoteClient(
      'http://[::1]:3456',
      {
        origin: 'http://213.32.19.186:5190',
        hostname: '213.32.19.186',
      },
    )

    expect(rewritten).toBe('http://213.32.19.186:3456/')
  })
})
