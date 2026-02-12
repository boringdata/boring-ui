/**
 * Tests for useTabManager hook.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useTabManager } from './useTabManager'

const mockLoadSavedTabs = vi.fn()
const mockSaveTabs = vi.fn()
vi.mock('../layout', () => ({
  loadSavedTabs: (...args) => mockLoadSavedTabs(...args),
  saveTabs: (...args) => mockSaveTabs(...args),
}))

function createMockDockApi() {
  return { getPanel: vi.fn() }
}

function createOptions(overrides = {}) {
  return {
    dockApi: createMockDockApi(),
    projectRoot: '/project',
    storagePrefix: 'test-prefix',
    tabs: {},
    openFile: vi.fn(),
    isInitialized: { current: true },
    layoutRestored: { current: false },
    ...overrides,
  }
}

beforeEach(() => {
  mockLoadSavedTabs.mockReset().mockReturnValue([])
  mockSaveTabs.mockReset()
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('useTabManager', () => {
  describe('tab restoration', () => {
    it('does nothing when dockApi is null', () => {
      renderHook(() => useTabManager(createOptions({ dockApi: null })))

      expect(mockLoadSavedTabs).not.toHaveBeenCalled()
    })

    it('does nothing when projectRoot is null', () => {
      renderHook(() => useTabManager(createOptions({ projectRoot: null })))

      expect(mockLoadSavedTabs).not.toHaveBeenCalled()
    })

    it('skips restoration when layout was restored from JSON', () => {
      mockLoadSavedTabs.mockReturnValue(['src/a.js'])
      const openFile = vi.fn()
      renderHook(() => useTabManager(createOptions({ openFile, layoutRestored: { current: true } })))

      vi.advanceTimersByTime(100)

      expect(openFile).not.toHaveBeenCalled()
    })

    it('restores saved tabs when layout was not restored', () => {
      mockLoadSavedTabs.mockReturnValue(['src/a.js', 'src/b.js'])
      const openFile = vi.fn()
      renderHook(() => useTabManager(createOptions({ openFile })))

      vi.advanceTimersByTime(100)

      expect(openFile).toHaveBeenCalledWith('src/a.js')
      expect(openFile).toHaveBeenCalledWith('src/b.js')
    })

    it('does not restore when no saved tabs', () => {
      mockLoadSavedTabs.mockReturnValue([])
      const openFile = vi.fn()
      renderHook(() => useTabManager(createOptions({ openFile })))

      vi.advanceTimersByTime(100)

      expect(openFile).not.toHaveBeenCalled()
    })

    it('only restores once across rerenders', () => {
      mockLoadSavedTabs.mockReturnValue(['src/a.js'])
      const openFile = vi.fn()
      const opts = createOptions({ openFile })
      const { rerender } = renderHook(
        (props) => useTabManager(props),
        { initialProps: opts },
      )

      vi.advanceTimersByTime(100)
      expect(openFile).toHaveBeenCalledTimes(1)

      // Re-render with same options — should not restore again
      rerender(opts)
      vi.advanceTimersByTime(100)
      expect(openFile).toHaveBeenCalledTimes(1)
    })
  })

  describe('tab persistence', () => {
    it('saves tabs when they change', () => {
      const tabs = { 'src/a.js': { content: 'a', isDirty: false } }
      renderHook(() => useTabManager(createOptions({ tabs })))

      expect(mockSaveTabs).toHaveBeenCalledWith('test-prefix', '/project', ['src/a.js'])
    })

    it('does not save when not initialized', () => {
      renderHook(() => useTabManager(createOptions({ isInitialized: { current: false } })))

      expect(mockSaveTabs).not.toHaveBeenCalled()
    })

    it('does not save when projectRoot is null', () => {
      renderHook(() => useTabManager(createOptions({ projectRoot: null })))

      expect(mockSaveTabs).not.toHaveBeenCalled()
    })
  })
})
