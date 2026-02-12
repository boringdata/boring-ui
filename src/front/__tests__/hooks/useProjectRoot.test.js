import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useProjectRoot } from '../../hooks/useProjectRoot'
import * as apiBase from '../../utils/apiBase'

// Mock buildApiUrl
vi.mock('../../utils/apiBase', () => ({
  buildApiUrl: vi.fn((path) => `/mocked${path}`),
}))

describe('useProjectRoot', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    global.fetch = vi.fn()
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    vi.spyOn(console, 'info').mockImplementation(() => {})
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('fetches project root on mount and sets state', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ root: '/home/ubuntu/project' }),
    })

    const { result } = renderHook(() => useProjectRoot())

    expect(result.current.isLoading).toBe(true)
    expect(result.current.projectRoot).toBe(null)

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.projectRoot).toBe('/home/ubuntu/project')
    expect(result.current.error).toBe(null)
    expect(result.current.hasFallback).toBe(false)
  })

  it('handles empty root in response', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ root: '' }),
    })

    const { result } = renderHook(() => useProjectRoot())

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.projectRoot).toBe('')
    expect(result.current.hasFallback).toBe(false)
  })

  it('handles missing root field in response', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({}),
    })

    const { result } = renderHook(() => useProjectRoot())

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.projectRoot).toBe('')
  })

  it('retries on fetch failure with 500ms delay', async () => {
    global.fetch
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ root: '/home/ubuntu/project' }),
      })

    const { result } = renderHook(() => useProjectRoot())

    expect(result.current.isLoading).toBe(true)

    // Wait for first fetch to fail
    await vi.runOnlyPendingTimersAsync()

    // Advance 500ms for retry
    await vi.advanceTimersByTimeAsync(500)

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.projectRoot).toBe('/home/ubuntu/project')
    expect(global.fetch).toHaveBeenCalledTimes(2)
  })

  it('retries on HTTP error status', async () => {
    global.fetch
      .mockResolvedValueOnce({ ok: false, status: 500 })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ root: '/home/ubuntu/project' }),
      })

    const { result } = renderHook(() => useProjectRoot())

    // Wait for first fetch to fail
    await vi.runOnlyPendingTimersAsync()

    // Advance 500ms for retry
    await vi.advanceTimersByTimeAsync(500)

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.projectRoot).toBe('/home/ubuntu/project')
    expect(global.fetch).toHaveBeenCalledTimes(2)
  })

  it('applies fallback after max retries (6 attempts)', async () => {
    global.fetch.mockRejectedValue(new Error('Network error'))

    const { result } = renderHook(() => useProjectRoot())

    expect(result.current.isLoading).toBe(true)

    // Simulate 6 failed attempts with retries
    for (let i = 0; i < 6; i++) {
      await vi.runOnlyPendingTimersAsync()
      if (i < 5) {
        await vi.advanceTimersByTimeAsync(500)
      }
    }

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.projectRoot).toBe('')
    expect(result.current.hasFallback).toBe(true)
    expect(result.current.error).toBeTruthy()
    expect(console.warn).toHaveBeenCalledWith(
      expect.stringContaining('Failed to fetch project root after retries')
    )
  })

  it('does not update state after fallback is applied', async () => {
    // First 6 calls fail, 7th succeeds
    global.fetch
      .mockRejectedValueOnce(new Error('Network error'))
      .mockRejectedValueOnce(new Error('Network error'))
      .mockRejectedValueOnce(new Error('Network error'))
      .mockRejectedValueOnce(new Error('Network error'))
      .mockRejectedValueOnce(new Error('Network error'))
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ root: '/home/ubuntu/project' }),
      })

    const { result } = renderHook(() => useProjectRoot())

    // Simulate all 6 retries
    for (let i = 0; i < 6; i++) {
      await vi.runOnlyPendingTimersAsync()
      if (i < 5) {
        await vi.advanceTimersByTimeAsync(500)
      }
    }

    await waitFor(() => {
      expect(result.current.hasFallback).toBe(true)
    })

    // Even if backend becomes available, state should not update
    expect(result.current.projectRoot).toBe('')
    expect(console.info).toHaveBeenCalledWith(
      expect.stringContaining('Backend available but fallback already applied')
    )
  })

  it('cleans up timeout on unmount', async () => {
    global.fetch.mockRejectedValue(new Error('Network error'))

    const { unmount } = renderHook(() => useProjectRoot())

    // Let first fetch fail
    await vi.runOnlyPendingTimersAsync()

    // Unmount before retry happens
    unmount()

    // Advance timers - should not cause any errors
    await vi.advanceTimersByTimeAsync(500)

    // No additional fetch should have been made
    expect(global.fetch).toHaveBeenCalledTimes(1)
  })

  it('refetch() resets state and retries', async () => {
    // First attempt fails with max retries, then refetch succeeds
    global.fetch
      .mockRejectedValueOnce(new Error('Network error'))
      .mockRejectedValueOnce(new Error('Network error'))
      .mockRejectedValueOnce(new Error('Network error'))
      .mockRejectedValueOnce(new Error('Network error'))
      .mockRejectedValueOnce(new Error('Network error'))
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ root: '/home/ubuntu/project' }),
      })

    const { result } = renderHook(() => useProjectRoot())

    // Simulate all 6 retries to trigger fallback
    for (let i = 0; i < 6; i++) {
      await vi.runOnlyPendingTimersAsync()
      if (i < 5) {
        await vi.advanceTimersByTimeAsync(500)
      }
    }

    await waitFor(() => {
      expect(result.current.hasFallback).toBe(true)
    })

    expect(result.current.projectRoot).toBe('')

    // Call refetch
    result.current.refetch()

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.projectRoot).toBe('/home/ubuntu/project')
    expect(result.current.hasFallback).toBe(false)
    expect(result.current.error).toBe(null)
  })

  it('calls buildApiUrl with /api/project', () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ root: '/home/ubuntu/project' }),
    })

    renderHook(() => useProjectRoot())

    expect(apiBase.buildApiUrl).toHaveBeenCalledWith('/api/project')
  })

  it('sets error state on fetch failure', async () => {
    const error = new Error('Network error')
    global.fetch.mockRejectedValueOnce(error)

    const { result } = renderHook(() => useProjectRoot())

    // Wait for first attempt
    await vi.runOnlyPendingTimersAsync()

    expect(result.current.error).toEqual(error)
    expect(result.current.isLoading).toBe(true) // Still loading because it will retry
  })

  it('clears error on successful retry', async () => {
    global.fetch
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ root: '/home/ubuntu/project' }),
      })

    const { result } = renderHook(() => useProjectRoot())

    // Wait for first fetch to fail
    await vi.runOnlyPendingTimersAsync()
    expect(result.current.error).toBeTruthy()

    // Advance for retry
    await vi.advanceTimersByTimeAsync(500)

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.error).toBe(null)
    expect(result.current.projectRoot).toBe('/home/ubuntu/project')
  })
})
