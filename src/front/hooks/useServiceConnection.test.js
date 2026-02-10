/**
 * Tests for useServiceConnection hook.
 *
 * Covers: capabilities fetch, auth helpers, token refresh,
 * 401 auto-retry, and token security (no localStorage).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useServiceConnection } from './useServiceConnection'

// Mock capabilities response with sandbox service
const mockCapabilities = {
  version: '0.1.0',
  features: { sandbox: true },
  services: {
    sandbox: {
      url: 'http://127.0.0.1:2468',
      token: 'test-bearer-token',
      qpToken: 'test-qp-token',
      protocol: 'rest+sse',
    },
  },
}

// Capabilities without services
const mockCapabilitiesNoServices = {
  version: '0.1.0',
  features: { files: true },
}

// Fresh tokens after refresh
const mockRefreshedCapabilities = {
  ...mockCapabilities,
  services: {
    sandbox: {
      url: 'http://127.0.0.1:2468',
      token: 'refreshed-bearer-token',
      qpToken: 'refreshed-qp-token',
      protocol: 'rest+sse',
    },
  },
}

function mockFetchOk(data) {
  return vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(data),
  })
}

function mockFetchError(status = 500) {
  return vi.fn().mockResolvedValue({
    ok: false,
    status,
    json: () => Promise.resolve({ detail: 'error' }),
  })
}

describe('useServiceConnection', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  // --- Capabilities fetch ---

  it('fetches capabilities on mount and exposes services', async () => {
    global.fetch = mockFetchOk(mockCapabilities)

    const { result } = renderHook(() => useServiceConnection())

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.services).toEqual(mockCapabilities.services)
    expect(result.current.error).toBeNull()
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/capabilities'),
    )
  })

  it('sets services to null when capabilities has no services section', async () => {
    global.fetch = mockFetchOk(mockCapabilitiesNoServices)

    const { result } = renderHook(() => useServiceConnection())

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.services).toBeNull()
  })

  it('sets error on network failure', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'))

    const { result } = renderHook(() => useServiceConnection())

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.error).toBeInstanceOf(Error)
    expect(result.current.error.message).toBe('Network error')
  })

  it('sets error on non-200 response', async () => {
    global.fetch = mockFetchError(503)

    const { result } = renderHook(() => useServiceConnection())

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.error).toBeInstanceOf(Error)
    expect(result.current.error.message).toContain('503')
  })

  // --- Auth helpers ---

  it('getAuthHeaders returns Authorization header with bearer token', async () => {
    global.fetch = mockFetchOk(mockCapabilities)

    const { result } = renderHook(() => useServiceConnection())

    await waitFor(() => {
      expect(result.current.services).toBeTruthy()
    })

    const headers = result.current.getAuthHeaders('sandbox')
    expect(headers).toEqual({
      Authorization: 'Bearer test-bearer-token',
    })
  })

  it('getAuthHeaders merges with extra headers', async () => {
    global.fetch = mockFetchOk(mockCapabilities)

    const { result } = renderHook(() => useServiceConnection())

    await waitFor(() => {
      expect(result.current.services).toBeTruthy()
    })

    const headers = result.current.getAuthHeaders('sandbox', {
      'Content-Type': 'application/json',
    })
    expect(headers).toEqual({
      Authorization: 'Bearer test-bearer-token',
      'Content-Type': 'application/json',
    })
  })

  it('getAuthHeaders returns empty object for unknown service', async () => {
    global.fetch = mockFetchOk(mockCapabilities)

    const { result } = renderHook(() => useServiceConnection())

    await waitFor(() => {
      expect(result.current.services).toBeTruthy()
    })

    const headers = result.current.getAuthHeaders('unknown')
    expect(headers).toEqual({})
  })

  it('getQpToken returns short-lived token for known service', async () => {
    global.fetch = mockFetchOk(mockCapabilities)

    const { result } = renderHook(() => useServiceConnection())

    await waitFor(() => {
      expect(result.current.services).toBeTruthy()
    })

    expect(result.current.getQpToken('sandbox')).toBe('test-qp-token')
  })

  it('getQpToken returns null for unknown service', async () => {
    global.fetch = mockFetchOk(mockCapabilities)

    const { result } = renderHook(() => useServiceConnection())

    await waitFor(() => {
      expect(result.current.services).toBeTruthy()
    })

    expect(result.current.getQpToken('unknown')).toBeNull()
  })

  it('getServiceUrl returns direct-connect URL', async () => {
    global.fetch = mockFetchOk(mockCapabilities)

    const { result } = renderHook(() => useServiceConnection())

    await waitFor(() => {
      expect(result.current.services).toBeTruthy()
    })

    expect(result.current.getServiceUrl('sandbox')).toBe('http://127.0.0.1:2468')
  })

  it('getServiceUrl returns null for unknown service', async () => {
    global.fetch = mockFetchOk(mockCapabilities)

    const { result } = renderHook(() => useServiceConnection())

    await waitFor(() => {
      expect(result.current.services).toBeTruthy()
    })

    expect(result.current.getServiceUrl('unknown')).toBeNull()
  })

  // --- Token refresh ---

  it('refreshTokens re-fetches capabilities and returns fresh services', async () => {
    let callCount = 0
    global.fetch = vi.fn().mockImplementation(() => {
      callCount++
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve(
            callCount === 1 ? mockCapabilities : mockRefreshedCapabilities,
          ),
      })
    })

    const { result } = renderHook(() => useServiceConnection())

    await waitFor(() => {
      expect(result.current.services).toBeTruthy()
    })

    let refreshResult
    await act(async () => {
      const p = result.current.refreshTokens()
      await vi.advanceTimersByTimeAsync(600) // 500ms initial backoff
      refreshResult = await p
    })

    expect(refreshResult).toBeTruthy()
    expect(refreshResult.sandbox.token).toBe('refreshed-bearer-token')
  })

  it('refreshTokens returns null after MAX_RETRIES exhausted', async () => {
    // Set up fetch that fails each time (simulating network issues)
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'))

    const { result } = renderHook(() => useServiceConnection())

    // Wait for initial fetch to fail
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    // Exhaust retries (MAX_RETRIES = 3)
    for (let i = 0; i < 3; i++) {
      await act(async () => {
        const p = result.current.refreshTokens()
        await vi.advanceTimersByTimeAsync(10000)
        await p
      })
    }

    // 4th call should return null immediately (no delay)
    let stopResult
    await act(async () => {
      stopResult = await result.current.refreshTokens()
    })
    expect(stopResult).toBeNull()
  })

  // --- 401 auto-retry ---

  it('fetchWithRetry passes auth headers on initial request', async () => {
    global.fetch = mockFetchOk(mockCapabilities)

    const { result } = renderHook(() => useServiceConnection())

    await waitFor(() => {
      expect(result.current.services).toBeTruthy()
    })

    const mockResponse = { ok: true, status: 200 }
    global.fetch = vi.fn().mockResolvedValue(mockResponse)

    let response
    await act(async () => {
      response = await result.current.fetchWithRetry(
        'sandbox',
        'http://127.0.0.1:2468/v1/agents',
      )
    })

    expect(response).toBe(mockResponse)
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:2468/v1/agents',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer test-bearer-token',
        }),
      }),
    )
  })

  it('fetchWithRetry retries once on 401 with fresh token', async () => {
    global.fetch = mockFetchOk(mockCapabilities)

    const { result } = renderHook(() => useServiceConnection())

    await waitFor(() => {
      expect(result.current.services).toBeTruthy()
    })

    let fetchCallCount = 0
    global.fetch = vi.fn().mockImplementation((url) => {
      fetchCallCount++
      if (typeof url === 'string' && url.includes('/api/capabilities')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockRefreshedCapabilities),
        })
      }
      if (fetchCallCount === 1) {
        return Promise.resolve({ ok: false, status: 401 })
      }
      return Promise.resolve({ ok: true, status: 200 })
    })

    let response
    await act(async () => {
      const p = result.current.fetchWithRetry(
        'sandbox',
        'http://127.0.0.1:2468/v1/agents',
      )
      await vi.advanceTimersByTimeAsync(600)
      response = await p
    })

    expect(response.status).toBe(200)
  })

  it('fetchWithRetry merges extra headers with auth', async () => {
    global.fetch = mockFetchOk(mockCapabilities)

    const { result } = renderHook(() => useServiceConnection())

    await waitFor(() => {
      expect(result.current.services).toBeTruthy()
    })

    global.fetch = vi.fn().mockResolvedValue({ ok: true, status: 200 })

    await act(async () => {
      await result.current.fetchWithRetry(
        'sandbox',
        'http://127.0.0.1:2468/v1/sessions/1',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: '{}',
        },
      )
    })

    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:2468/v1/sessions/1',
      expect.objectContaining({
        method: 'POST',
        body: '{}',
        headers: expect.objectContaining({
          Authorization: 'Bearer test-bearer-token',
          'Content-Type': 'application/json',
        }),
      }),
    )
  })

  // --- Token security ---

  it('never writes tokens to localStorage', async () => {
    const setItemSpy = vi.spyOn(Storage.prototype, 'setItem')
    global.fetch = mockFetchOk(mockCapabilities)

    const { result } = renderHook(() => useServiceConnection())

    await waitFor(() => {
      expect(result.current.services).toBeTruthy()
    })

    for (const [, value] of setItemSpy.mock.calls) {
      expect(String(value)).not.toContain('test-bearer-token')
      expect(String(value)).not.toContain('test-qp-token')
    }

    setItemSpy.mockRestore()
  })
})
