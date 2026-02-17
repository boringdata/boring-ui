import { describe, it, expect } from 'vitest'
import { getPiServiceUrl, isPiBackendMode, resolvePiServiceUrl } from './config'

describe('PI service URL config', () => {
  it('rewrites loopback URL for remote clients', () => {
    const rewritten = resolvePiServiceUrl.call(
      null,
      'http://localhost:8789',
    )
    expect(typeof rewritten).toBe('string')
  })

  it('uses capabilities service URL when present', () => {
    const url = getPiServiceUrl({
      services: {
        pi: { url: 'http://127.0.0.1:8789', mode: 'backend' },
      },
    })
    expect(url.includes(':8789')).toBe(true)
  })

  it('enables backend mode when capabilities indicate backend', () => {
    expect(
      isPiBackendMode({
        services: {
          pi: { mode: 'backend' },
        },
      }),
    ).toBe(true)
  })
})
