/**
 * Tests for useLayoutInit hook.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useLayoutInit } from './useLayoutInit'

// Mock layout utilities
const mockApplyLockedPanels = vi.fn()
const mockEnsureCorePanels = vi.fn(() => ({ id: 'center-group' }))
const mockApplyPanelSizes = vi.fn()
const mockRestoreEmptyPanel = vi.fn()
vi.mock('../utils/layoutUtils', () => ({
  applyLockedPanels: (...args) => mockApplyLockedPanels(...args),
  ensureCorePanels: (...args) => mockEnsureCorePanels(...args),
  applyPanelSizes: (...args) => mockApplyPanelSizes(...args),
  restoreEmptyPanel: (...args) => mockRestoreEmptyPanel(...args),
}))

const mockSaveLayout = vi.fn()
const mockSavePanelSizes = vi.fn()
vi.mock('../layout', () => ({
  LAYOUT_VERSION: 1,
  validateLayoutStructure: vi.fn(() => true),
  saveLayout: (...args) => mockSaveLayout(...args),
  savePanelSizes: (...args) => mockSavePanelSizes(...args),
}))

function createMockApi() {
  const removeHandlers = []
  const layoutChangeHandlers = []
  return {
    getPanel: vi.fn(() => null),
    addPanel: vi.fn(),
    onDidRemovePanel: vi.fn((fn) => removeHandlers.push(fn)),
    onDidLayoutChange: vi.fn((fn) => layoutChangeHandlers.push(fn)),
    toJSON: vi.fn(() => ({})),
    _removeHandlers: removeHandlers,
    _layoutChangeHandlers: layoutChangeHandlers,
  }
}

function createOptions(overrides = {}) {
  return {
    setDockApi: vi.fn(),
    setTabs: vi.fn(),
    storagePrefix: 'test-prefix',
    panelSizesRef: { current: { filetree: 280, terminal: 400, shell: 250 } },
    panelMinRef: { current: { filetree: 180, terminal: 250, shell: 100, center: 100 } },
    panelCollapsedRef: { current: { filetree: 48, terminal: 48, shell: 36 } },
    centerGroupRef: { current: null },
    ensureCorePanelsRef: { current: null },
    storagePrefixRef: { current: 'test-prefix' },
    projectRootRef: { current: '/project' },
    layoutVersionRef: { current: 1 },
    isInitialized: { current: false },
    ...overrides,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  // Clear localStorage
  localStorage.clear()
})

describe('useLayoutInit', () => {
  it('returns an onReady function', () => {
    const { result } = renderHook(() => useLayoutInit(createOptions()))
    expect(result.current.onReady).toBeTypeOf('function')
  })

  it('calls setDockApi with the api from the event', () => {
    const opts = createOptions()
    const { result } = renderHook(() => useLayoutInit(opts))
    const api = createMockApi()

    result.current.onReady({ api })

    expect(opts.setDockApi).toHaveBeenCalledWith(api)
  })

  it('creates core panels when no saved layout exists', () => {
    const opts = createOptions()
    const { result } = renderHook(() => useLayoutInit(opts))
    const api = createMockApi()

    result.current.onReady({ api })

    expect(mockEnsureCorePanels).toHaveBeenCalledWith(api, opts.panelMinRef.current)
    expect(mockApplyLockedPanels).toHaveBeenCalledWith(api, opts.panelMinRef.current)
  })

  it('skips core panel creation when valid saved layout exists', () => {
    const opts = createOptions()
    // Set up a saved layout in localStorage
    localStorage.setItem('test-prefix-project-layout', JSON.stringify({
      version: 1,
      panels: [{ id: 'filetree' }],
    }))

    const { result } = renderHook(() => useLayoutInit(opts))
    const api = createMockApi()

    result.current.onReady({ api })

    expect(mockEnsureCorePanels).not.toHaveBeenCalled()
  })

  it('sets ensureCorePanelsRef to a callable function', () => {
    const opts = createOptions()
    const { result } = renderHook(() => useLayoutInit(opts))
    const api = createMockApi()

    result.current.onReady({ api })

    expect(opts.ensureCorePanelsRef.current).toBeTypeOf('function')
    // Calling it should invoke ensureCorePanels and applyLockedPanels
    mockEnsureCorePanels.mockClear()
    mockApplyLockedPanels.mockClear()
    opts.ensureCorePanelsRef.current()
    expect(mockEnsureCorePanels).toHaveBeenCalled()
    expect(mockApplyLockedPanels).toHaveBeenCalledTimes(2) // once from ensure, once standalone
  })

  it('registers onDidRemovePanel handler that cleans up tabs', () => {
    const opts = createOptions()
    const { result } = renderHook(() => useLayoutInit(opts))
    const api = createMockApi()

    result.current.onReady({ api })

    expect(api.onDidRemovePanel).toHaveBeenCalled()

    // Simulate removing an editor panel
    const removeHandler = api._removeHandlers[0]
    removeHandler({ id: 'editor-src/foo.js' })

    expect(opts.setTabs).toHaveBeenCalled()
    const updater = opts.setTabs.mock.calls[0][0]
    const result2 = updater({ 'src/foo.js': { content: 'x', isDirty: false }, 'other.js': {} })
    expect(result2).not.toHaveProperty('src/foo.js')
    expect(result2).toHaveProperty('other.js')
  })

  it('does not clean up tabs for non-editor panels', () => {
    const opts = createOptions()
    const { result } = renderHook(() => useLayoutInit(opts))
    const api = createMockApi()

    result.current.onReady({ api })

    const removeHandler = api._removeHandlers[0]
    removeHandler({ id: 'filetree' })

    expect(opts.setTabs).not.toHaveBeenCalled()
  })

  it('registers restoreEmptyPanel handler', () => {
    const opts = createOptions()
    const { result } = renderHook(() => useLayoutInit(opts))
    const api = createMockApi()

    result.current.onReady({ api })

    // Second onDidRemovePanel handler is for restoreEmptyPanel
    const restoreHandler = api._removeHandlers[1]
    restoreHandler({ id: 'editor-foo' })

    expect(mockRestoreEmptyPanel).toHaveBeenCalledWith(api, opts.centerGroupRef, opts.panelMinRef.current)
  })

  it('sets isInitialized to true', () => {
    const opts = createOptions()
    const { result } = renderHook(() => useLayoutInit(opts))
    const api = createMockApi()

    expect(opts.isInitialized.current).toBe(false)
    result.current.onReady({ api })
    expect(opts.isInitialized.current).toBe(true)
  })

  it('registers layout change handler that debounces saves', () => {
    const opts = createOptions()
    const { result } = renderHook(() => useLayoutInit(opts))
    const api = createMockApi()

    result.current.onReady({ api })

    expect(api.onDidLayoutChange).toHaveBeenCalled()
  })
})
