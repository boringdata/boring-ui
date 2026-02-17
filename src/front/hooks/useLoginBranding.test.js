/**
 * useLoginBranding hook and resolveClientBranding unit tests.
 *
 * Bead: bd-223o.14.5 (H5)
 *
 * Validates:
 *   - resolveClientBranding precedence: workspace > app-config > local > fallback.
 *   - Partial overrides at each level.
 *   - Source field reflects the winning level.
 *   - Hook fetches /api/v1/app-config and applies branding.
 *   - Hook falls back gracefully on fetch failure.
 */

import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { renderHook, waitFor, cleanup, act } from '@testing-library/react'
import useLoginBranding, { resolveClientBranding } from './useLoginBranding.js'
import { resetConfig, setConfig } from '../config/appConfig'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  resetConfig()
})

// =====================================================================
// resolveClientBranding — pure function tests
// =====================================================================

describe('resolveClientBranding', () => {
  beforeEach(() => resetConfig())

  it('returns hardcoded fallback when nothing is set', () => {
    const result = resolveClientBranding(null, null)
    // Local config default is "Boring UI" with logo "B"
    expect(result.name).toBe('Boring UI')
    expect(result.logo).toBe('B')
    expect(result.source).toBe('local')
  })

  it('uses app-config over local config', () => {
    const result = resolveClientBranding(null, { name: 'Acme Corp', logo: '/acme.svg' })
    expect(result.name).toBe('Acme Corp')
    expect(result.logo).toBe('/acme.svg')
    expect(result.source).toBe('app')
  })

  it('uses workspace branding over app-config', () => {
    const result = resolveClientBranding(
      { name: 'WS Brand', logo: '/ws.svg' },
      { name: 'Acme Corp', logo: '/acme.svg' },
    )
    expect(result.name).toBe('WS Brand')
    expect(result.logo).toBe('/ws.svg')
    expect(result.source).toBe('workspace')
  })

  it('allows partial workspace override (name only)', () => {
    const result = resolveClientBranding(
      { name: 'WS Brand', logo: '' },
      { name: 'Acme Corp', logo: '/acme.svg' },
    )
    expect(result.name).toBe('WS Brand')
    expect(result.logo).toBe('/acme.svg')
    expect(result.source).toBe('workspace')
  })

  it('allows partial workspace override (logo only)', () => {
    const result = resolveClientBranding(
      { name: '', logo: '/ws.svg' },
      { name: 'Acme Corp', logo: '/acme.svg' },
    )
    expect(result.name).toBe('Acme Corp')
    expect(result.logo).toBe('/ws.svg')
    expect(result.source).toBe('workspace')
  })

  it('falls through to local config when app-config is empty', () => {
    const result = resolveClientBranding(null, { name: '', logo: '' })
    expect(result.name).toBe('Boring UI')
    expect(result.source).toBe('local')
  })

  it('uses setConfig values as local config', () => {
    setConfig({ branding: { name: 'Custom App', logo: '/custom.svg' } })
    const result = resolveClientBranding(null, null)
    expect(result.name).toBe('Custom App')
    expect(result.logo).toBe('/custom.svg')
    expect(result.source).toBe('local')
  })
})

// =====================================================================
// useLoginBranding — hook tests
// =====================================================================

describe('useLoginBranding', () => {
  it('fetches app-config and applies branding', async () => {
    globalThis.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ name: 'Remote App', logo: '/remote.svg' }),
      }),
    )

    const { result } = renderHook(() => useLoginBranding())

    // Initially loading.
    expect(result.current.loading).toBe(true)

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.name).toBe('Remote App')
    expect(result.current.logo).toBe('/remote.svg')
    expect(result.current.source).toBe('app')
  })

  it('falls back to local config on fetch failure', async () => {
    globalThis.fetch = vi.fn(() => Promise.reject(new Error('network')))

    const { result } = renderHook(() => useLoginBranding())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.name).toBe('Boring UI')
    expect(result.current.source).toBe('local')
  })

  it('falls back on non-ok response', async () => {
    globalThis.fetch = vi.fn(() =>
      Promise.resolve({ ok: false, status: 404 }),
    )

    const { result } = renderHook(() => useLoginBranding())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.name).toBe('Boring UI')
  })

  it('applies workspace branding override', async () => {
    globalThis.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ name: 'Remote App', logo: '/remote.svg' }),
      }),
    )

    const { result } = renderHook(() =>
      useLoginBranding({ workspaceBranding: { name: 'My WS', logo: '' } }),
    )

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.name).toBe('My WS')
    expect(result.current.logo).toBe('/remote.svg')
    expect(result.current.source).toBe('workspace')
  })
})
