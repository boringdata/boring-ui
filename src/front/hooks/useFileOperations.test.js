/**
 * Tests for useFileOperations hook.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useFileOperations } from './useFileOperations'

// Mock dependencies
vi.mock('../utils/apiBase', () => ({
  buildApiUrl: (url) => url,
}))

const mockFindEditorPosition = vi.fn(() => ({ referenceGroup: 'center' }))
const mockFindSidePosition = vi.fn(() => ({ direction: 'right', referencePanel: 'editor-foo' }))
const mockFindDiffPosition = vi.fn(() => ({ referenceGroup: 'center' }))
vi.mock('../utils/filePositioning', () => ({
  findEditorPosition: (...args) => mockFindEditorPosition(...args),
  findSidePosition: (...args) => mockFindSidePosition(...args),
  findDiffPosition: (...args) => mockFindDiffPosition(...args),
}))

vi.mock('../layout', () => ({
  getFileName: (p) => p.split('/').pop(),
}))

function createMockPanel(id) {
  return {
    id,
    api: {
      setActive: vi.fn(),
      close: vi.fn(),
      updateParameters: vi.fn(),
      setTitle: vi.fn(),
      setConstraints: vi.fn(),
    },
    group: {
      header: { hidden: false },
      api: { setConstraints: vi.fn() },
    },
  }
}

function createMockDockApi(panels = {}) {
  return {
    getPanel: vi.fn((id) => panels[id] || null),
    addPanel: vi.fn((opts) => {
      const panel = createMockPanel(opts.id)
      return panel
    }),
    panels: Object.values(panels),
    activePanel: null,
  }
}

function createOptions(overrides = {}) {
  return {
    dockApi: createMockDockApi(),
    setTabs: vi.fn(),
    setActiveDiffFile: vi.fn(),
    centerGroupRef: { current: { header: { hidden: false } } },
    panelMinRef: { current: { center: 100 } },
    ...overrides,
  }
}

// Stub global fetch
const mockFetch = vi.fn()
global.fetch = mockFetch

beforeEach(() => {
  vi.clearAllMocks()
  mockFetch.mockResolvedValue({
    json: () => Promise.resolve({ content: 'file content' }),
  })
})

describe('useFileOperations', () => {
  describe('openFileAtPosition', () => {
    it('returns all four functions', () => {
      const { result } = renderHook(() => useFileOperations(createOptions()))

      expect(result.current.openFileAtPosition).toBeTypeOf('function')
      expect(result.current.openFile).toBeTypeOf('function')
      expect(result.current.openFileToSide).toBeTypeOf('function')
      expect(result.current.openDiff).toBeTypeOf('function')
    })

    it('is a no-op when dockApi is null', async () => {
      const opts = createOptions({ dockApi: null })
      const { result } = renderHook(() => useFileOperations(opts))

      await act(async () => {
        result.current.openFileAtPosition('src/foo.js', { referenceGroup: 'center' })
      })

      expect(mockFetch).not.toHaveBeenCalled()
    })

    it('activates existing panel instead of creating a new one', async () => {
      const existingPanel = createMockPanel('editor-src/foo.js')
      const dockApi = createMockDockApi({ 'editor-src/foo.js': existingPanel })
      const opts = createOptions({ dockApi })
      const { result } = renderHook(() => useFileOperations(opts))

      await act(async () => {
        result.current.openFileAtPosition('src/foo.js', { referenceGroup: 'center' })
      })

      expect(existingPanel.api.setActive).toHaveBeenCalled()
      expect(dockApi.addPanel).not.toHaveBeenCalled()
    })

    it('updates initialMode on existing panel when provided', async () => {
      const existingPanel = createMockPanel('editor-src/foo.js')
      const dockApi = createMockDockApi({ 'editor-src/foo.js': existingPanel })
      const opts = createOptions({ dockApi })
      const { result } = renderHook(() => useFileOperations(opts))

      await act(async () => {
        result.current.openFileAtPosition('src/foo.js', {}, { initialMode: 'git-diff' })
      })

      expect(existingPanel.api.updateParameters).toHaveBeenCalledWith({ initialMode: 'git-diff' })
    })

    it('fetches content and creates panel for new file', async () => {
      const opts = createOptions()
      const { result } = renderHook(() => useFileOperations(opts))

      await act(async () => {
        result.current.openFileAtPosition('src/bar.js', { referenceGroup: 'center' })
        // Allow fetch promise to resolve
        await new Promise((r) => setTimeout(r, 0))
      })

      expect(mockFetch).toHaveBeenCalledWith(expect.stringContaining('bar.js'))
      expect(opts.dockApi.addPanel).toHaveBeenCalledWith(
        expect.objectContaining({
          id: 'editor-src/bar.js',
          component: 'editor',
        }),
      )
    })

    it('updates tabs state when creating panel', async () => {
      const opts = createOptions()
      const { result } = renderHook(() => useFileOperations(opts))

      await act(async () => {
        result.current.openFileAtPosition('src/bar.js', { referenceGroup: 'center' })
        await new Promise((r) => setTimeout(r, 0))
      })

      expect(opts.setTabs).toHaveBeenCalled()
      // Verify the updater adds the file
      const updater = opts.setTabs.mock.calls[0][0]
      const newState = updater({})
      expect(newState['src/bar.js']).toEqual({ content: 'file content', isDirty: false })
    })

    it('closes empty-center panel when creating editor', async () => {
      const emptyPanel = createMockPanel('empty-center')
      const dockApi = createMockDockApi({ 'empty-center': emptyPanel })
      const opts = createOptions({ dockApi })
      const { result } = renderHook(() => useFileOperations(opts))

      await act(async () => {
        result.current.openFileAtPosition('src/bar.js', { referenceGroup: 'center' })
        await new Promise((r) => setTimeout(r, 0))
      })

      expect(emptyPanel.api.close).toHaveBeenCalled()
    })

    it('handles fetch failure gracefully', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'))
      const opts = createOptions()
      const { result } = renderHook(() => useFileOperations(opts))

      await act(async () => {
        result.current.openFileAtPosition('src/bar.js', { referenceGroup: 'center' })
        await new Promise((r) => setTimeout(r, 0))
      })

      // Should still create panel with empty content
      expect(opts.dockApi.addPanel).toHaveBeenCalled()
    })
  })

  describe('openFile', () => {
    it('is a no-op when dockApi is null', () => {
      const opts = createOptions({ dockApi: null })
      const { result } = renderHook(() => useFileOperations(opts))

      let returnVal
      act(() => {
        returnVal = result.current.openFile('src/foo.js')
      })

      expect(returnVal).toBe(false)
    })

    it('activates existing panel and returns true', () => {
      const existingPanel = createMockPanel('editor-src/foo.js')
      const dockApi = createMockDockApi({ 'editor-src/foo.js': existingPanel })
      const opts = createOptions({ dockApi })
      const { result } = renderHook(() => useFileOperations(opts))

      let returnVal
      act(() => {
        returnVal = result.current.openFile('src/foo.js')
      })

      expect(returnVal).toBe(true)
      expect(existingPanel.api.setActive).toHaveBeenCalled()
    })

    it('calls findEditorPosition for new files', async () => {
      const opts = createOptions()
      const { result } = renderHook(() => useFileOperations(opts))

      await act(async () => {
        result.current.openFile('src/new.js')
      })

      expect(mockFindEditorPosition).toHaveBeenCalledWith(
        opts.dockApi,
        expect.objectContaining({ header: expect.any(Object) }),
      )
    })
  })

  describe('openFileToSide', () => {
    it('is a no-op when dockApi is null', () => {
      const opts = createOptions({ dockApi: null })
      const { result } = renderHook(() => useFileOperations(opts))

      act(() => {
        result.current.openFileToSide('src/foo.js')
      })

      expect(mockFindSidePosition).not.toHaveBeenCalled()
    })

    it('activates existing panel instead of opening to side', () => {
      const existingPanel = createMockPanel('editor-src/foo.js')
      const dockApi = createMockDockApi({ 'editor-src/foo.js': existingPanel })
      const opts = createOptions({ dockApi })
      const { result } = renderHook(() => useFileOperations(opts))

      act(() => {
        result.current.openFileToSide('src/foo.js')
      })

      expect(existingPanel.api.setActive).toHaveBeenCalled()
      expect(mockFindSidePosition).not.toHaveBeenCalled()
    })

    it('calls findSidePosition for new files', async () => {
      const opts = createOptions()
      const { result } = renderHook(() => useFileOperations(opts))

      await act(async () => {
        result.current.openFileToSide('src/new.js')
      })

      expect(mockFindSidePosition).toHaveBeenCalledWith(
        opts.dockApi,
        expect.objectContaining({ header: expect.any(Object) }),
      )
    })
  })

  describe('openDiff', () => {
    it('is a no-op when dockApi is null', () => {
      const opts = createOptions({ dockApi: null })
      const { result } = renderHook(() => useFileOperations(opts))

      act(() => {
        result.current.openDiff('src/foo.js')
      })

      expect(opts.setActiveDiffFile).not.toHaveBeenCalled()
    })

    it('updates existing panel to git-diff mode', () => {
      const existingPanel = createMockPanel('editor-src/foo.js')
      const dockApi = createMockDockApi({ 'editor-src/foo.js': existingPanel })
      const opts = createOptions({ dockApi })
      const { result } = renderHook(() => useFileOperations(opts))

      act(() => {
        result.current.openDiff('src/foo.js')
      })

      expect(existingPanel.api.updateParameters).toHaveBeenCalledWith({ initialMode: 'git-diff' })
      expect(existingPanel.api.setActive).toHaveBeenCalled()
      expect(opts.setActiveDiffFile).toHaveBeenCalledWith('src/foo.js')
    })

    it('calls findDiffPosition for new files', async () => {
      const opts = createOptions()
      const { result } = renderHook(() => useFileOperations(opts))

      await act(async () => {
        result.current.openDiff('src/new.js')
      })

      expect(mockFindDiffPosition).toHaveBeenCalledWith(
        opts.dockApi,
        expect.objectContaining({ header: expect.any(Object) }),
      )
      expect(opts.setActiveDiffFile).toHaveBeenCalledWith('src/new.js')
    })
  })
})
