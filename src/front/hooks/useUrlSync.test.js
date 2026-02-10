/**
 * Tests for useUrlSync hook.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useUrlSync } from './useUrlSync'

function createMockDockApi(panels = {}) {
  return {
    getPanel: vi.fn((id) => panels[id] || null),
  }
}

let originalSearch

beforeEach(() => {
  vi.clearAllMocks()
  vi.useFakeTimers()
  originalSearch = window.location.search
})

afterEach(() => {
  vi.useRealTimers()
  // Restore original search
  window.history.replaceState({}, '', window.location.pathname + originalSearch)
})

describe('useUrlSync', () => {
  it('does nothing when dockApi is null', () => {
    const openFile = vi.fn()
    renderHook(() => useUrlSync({ dockApi: null, projectRoot: '/project', openFile }))

    expect(openFile).not.toHaveBeenCalled()
  })

  it('does nothing when projectRoot is null', () => {
    const openFile = vi.fn()
    const dockApi = createMockDockApi({ filetree: { id: 'filetree' } })
    renderHook(() => useUrlSync({ dockApi, projectRoot: null, openFile }))

    expect(openFile).not.toHaveBeenCalled()
  })

  it('does nothing when filetree panel does not exist', () => {
    const openFile = vi.fn()
    const dockApi = createMockDockApi()
    renderHook(() => useUrlSync({ dockApi, projectRoot: '/project', openFile }))

    expect(openFile).not.toHaveBeenCalled()
  })

  it('opens file from URL doc param', () => {
    // Set URL with doc param
    window.history.replaceState({}, '', '?doc=src/foo.js')

    const openFile = vi.fn()
    const dockApi = createMockDockApi({ filetree: { id: 'filetree' } })
    renderHook(() => useUrlSync({ dockApi, projectRoot: '/project', openFile }))

    vi.advanceTimersByTime(200)

    expect(openFile).toHaveBeenCalledWith('src/foo.js')
  })

  it('does not open file when no doc param in URL', () => {
    window.history.replaceState({}, '', '?other=value')

    const openFile = vi.fn()
    const dockApi = createMockDockApi({ filetree: { id: 'filetree' } })
    renderHook(() => useUrlSync({ dockApi, projectRoot: '/project', openFile }))

    vi.advanceTimersByTime(200)

    expect(openFile).not.toHaveBeenCalled()
  })

  it('only runs once', () => {
    window.history.replaceState({}, '', '?doc=src/foo.js')

    const openFile = vi.fn()
    const dockApi = createMockDockApi({ filetree: { id: 'filetree' } })
    const { rerender } = renderHook(() => useUrlSync({ dockApi, projectRoot: '/project', openFile }))

    vi.advanceTimersByTime(200)
    expect(openFile).toHaveBeenCalledTimes(1)

    rerender()
    vi.advanceTimersByTime(200)
    expect(openFile).toHaveBeenCalledTimes(1) // Still just once
  })
})
