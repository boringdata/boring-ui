/**
 * Tests for useActivePanel hook.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useActivePanel } from './useActivePanel'

// Mock window.history.replaceState
const mockReplaceState = vi.fn()
Object.defineProperty(window, 'history', {
  value: { replaceState: mockReplaceState },
  writable: true,
})

function createMockDockApi() {
  const handlers = []
  return {
    onDidActivePanelChange: vi.fn((fn) => {
      handlers.push(fn)
      return { dispose: vi.fn() }
    }),
    _handlers: handlers,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useActivePanel', () => {
  it('does nothing when dockApi is null', () => {
    const setActiveFile = vi.fn()
    const setActiveDiffFile = vi.fn()
    renderHook(() => useActivePanel({ dockApi: null, setActiveFile, setActiveDiffFile }))

    expect(setActiveFile).not.toHaveBeenCalled()
  })

  it('registers onDidActivePanelChange handler', () => {
    const dockApi = createMockDockApi()
    renderHook(() => useActivePanel({
      dockApi, setActiveFile: vi.fn(), setActiveDiffFile: vi.fn(),
    }))

    expect(dockApi.onDidActivePanelChange).toHaveBeenCalled()
  })

  it('sets activeFile when editor panel becomes active', () => {
    const dockApi = createMockDockApi()
    const setActiveFile = vi.fn()
    const setActiveDiffFile = vi.fn()
    renderHook(() => useActivePanel({ dockApi, setActiveFile, setActiveDiffFile }))

    const handler = dockApi._handlers[0]
    handler({ id: 'editor-src/foo.js' })

    expect(setActiveFile).toHaveBeenCalledWith('src/foo.js')
    expect(setActiveDiffFile).toHaveBeenCalledWith('src/foo.js')
  })

  it('updates URL with doc param for editor panels', () => {
    const dockApi = createMockDockApi()
    renderHook(() => useActivePanel({
      dockApi, setActiveFile: vi.fn(), setActiveDiffFile: vi.fn(),
    }))

    dockApi._handlers[0]({ id: 'editor-src/foo.js' })

    expect(mockReplaceState).toHaveBeenCalled()
    const url = String(mockReplaceState.mock.calls[0][2])
    expect(url).toContain('doc=src')
    expect(url).toContain('foo.js')
  })

  it('clears state for non-editor panels', () => {
    const dockApi = createMockDockApi()
    const setActiveFile = vi.fn()
    const setActiveDiffFile = vi.fn()
    renderHook(() => useActivePanel({ dockApi, setActiveFile, setActiveDiffFile }))

    dockApi._handlers[0]({ id: 'filetree' })

    expect(setActiveFile).toHaveBeenCalledWith(null)
    expect(setActiveDiffFile).toHaveBeenCalledWith(null)
  })

  it('clears state for null panel', () => {
    const dockApi = createMockDockApi()
    const setActiveFile = vi.fn()
    const setActiveDiffFile = vi.fn()
    renderHook(() => useActivePanel({ dockApi, setActiveFile, setActiveDiffFile }))

    dockApi._handlers[0](null)

    expect(setActiveFile).toHaveBeenCalledWith(null)
    expect(setActiveDiffFile).toHaveBeenCalledWith(null)
  })

  it('disposes handler on unmount', () => {
    const disposeFn = vi.fn()
    const dockApi = {
      onDidActivePanelChange: vi.fn(() => ({ dispose: disposeFn })),
    }
    const { unmount } = renderHook(() => useActivePanel({
      dockApi, setActiveFile: vi.fn(), setActiveDiffFile: vi.fn(),
    }))

    unmount()
    expect(disposeFn).toHaveBeenCalled()
  })
})
