import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'

vi.mock('../../utils/apiBase', () => ({
  buildApiUrl: vi.fn((path) => path),
}))

import { useApprovals } from '../../hooks/useApprovals'

describe('useApprovals', () => {
  let fetchMock

  beforeEach(() => {
    vi.useFakeTimers()
    fetchMock = vi.fn(() =>
      Promise.resolve({
        json: () => Promise.resolve({ requests: [] }),
      }),
    )
    global.fetch = fetchMock
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('returns expected state shape', async () => {
    const { result } = renderHook(() => useApprovals())
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })

    expect(result.current).toHaveProperty('approvals')
    expect(result.current).toHaveProperty('approvalsLoaded')
    expect(result.current).toHaveProperty('handleDecision')
    expect(result.current).toHaveProperty('dismissedApprovalsRef')
    expect(result.current).toHaveProperty('setApprovals')
    expect(result.current).toHaveProperty('setApprovalsLoaded')
  })

  it('initializes with empty approvals and not loaded', () => {
    const { result } = renderHook(() => useApprovals())
    expect(result.current.approvals).toEqual([])
    expect(result.current.approvalsLoaded).toBe(false)
  })

  it('fetches approvals on mount', async () => {
    fetchMock.mockResolvedValue({
      json: () =>
        Promise.resolve({
          requests: [{ id: '1', tool_name: 'Edit' }],
        }),
    })

    const { result } = renderHook(() => useApprovals())

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })

    expect(fetchMock).toHaveBeenCalledWith('/api/approval/pending')
    expect(result.current.approvals).toEqual([{ id: '1', tool_name: 'Edit' }])
    expect(result.current.approvalsLoaded).toBe(true)
  })

  it('polls at specified interval', async () => {
    const { result } = renderHook(() =>
      useApprovals({ pollInterval: 2000 }),
    )

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })

    // Initial fetch
    expect(fetchMock).toHaveBeenCalledTimes(1)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000)
    })

    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('filters dismissed approvals', async () => {
    fetchMock.mockResolvedValue({
      json: () =>
        Promise.resolve({
          requests: [
            { id: '1', tool_name: 'Edit' },
            { id: '2', tool_name: 'Write' },
          ],
        }),
    })

    const { result } = renderHook(() => useApprovals())

    // Dismiss id '1' before fetch completes
    result.current.dismissedApprovalsRef.current.add('1')

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })

    expect(result.current.approvals).toEqual([{ id: '2', tool_name: 'Write' }])
  })

  it('handles fetch errors gracefully', async () => {
    fetchMock.mockRejectedValue(new Error('Network error'))

    const { result } = renderHook(() => useApprovals())

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })

    // Should not crash; stays at initial state
    expect(result.current.approvals).toEqual([])
    expect(result.current.approvalsLoaded).toBe(false)
  })

  it('handleDecision dismisses approval and closes panel', async () => {
    const closeFn = vi.fn()
    const dockApi = {
      getPanel: vi.fn(() => ({ api: { close: closeFn } })),
    }

    fetchMock.mockResolvedValue({
      json: () =>
        Promise.resolve({
          requests: [{ id: 'req-1', tool_name: 'Edit' }],
        }),
    })

    const { result } = renderHook(() => useApprovals({ dockApi }))

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })

    expect(result.current.approvals).toHaveLength(1)

    await act(async () => {
      await result.current.handleDecision('req-1', 'approve', 'looks good')
    })

    expect(result.current.approvals).toEqual([])
    expect(dockApi.getPanel).toHaveBeenCalledWith('review-req-1')
    expect(closeFn).toHaveBeenCalled()
    expect(result.current.dismissedApprovalsRef.current.has('req-1')).toBe(true)
  })

  it('handleDecision sends POST to backend', async () => {
    fetchMock.mockResolvedValue({
      json: () => Promise.resolve({ requests: [] }),
    })

    const { result } = renderHook(() => useApprovals())

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })

    await act(async () => {
      await result.current.handleDecision('req-1', 'reject', 'not safe')
    })

    expect(fetchMock).toHaveBeenCalledWith('/api/approval/decision', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        request_id: 'req-1',
        decision: 'reject',
        reason: 'not safe',
      }),
    })
  })

  it('handleDecision with null requestId clears all approvals', async () => {
    fetchMock.mockResolvedValue({
      json: () =>
        Promise.resolve({
          requests: [{ id: '1' }, { id: '2' }],
        }),
    })

    const { result } = renderHook(() => useApprovals())

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })

    expect(result.current.approvals).toHaveLength(2)

    await act(async () => {
      await result.current.handleDecision(null, 'dismiss', '')
    })

    expect(result.current.approvals).toEqual([])
  })

  it('handles non-array data.requests', async () => {
    fetchMock.mockResolvedValue({
      json: () => Promise.resolve({ requests: null }),
    })

    const { result } = renderHook(() => useApprovals())

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })

    expect(result.current.approvals).toEqual([])
    expect(result.current.approvalsLoaded).toBe(true)
  })

  it('cleans up interval on unmount', async () => {
    const { unmount } = renderHook(() => useApprovals())

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })

    unmount()

    // After unmount, further ticks should not cause fetches
    const callCount = fetchMock.mock.calls.length
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000)
    })

    expect(fetchMock).toHaveBeenCalledTimes(callCount)
  })
})
