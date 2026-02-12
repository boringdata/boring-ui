import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook } from '@testing-library/react'

vi.mock('../../layout', () => ({
  LAYOUT_VERSION: 1,
  validateLayoutStructure: vi.fn(() => true),
  saveLayout: vi.fn(),
  savePanelSizes: vi.fn(),
}))

import { useLayoutInit, debounce } from '../../hooks/useLayoutInit'

describe('debounce', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('delays function call', () => {
    const fn = vi.fn()
    const debounced = debounce(fn, 100)

    debounced()
    expect(fn).not.toHaveBeenCalled()

    vi.advanceTimersByTime(100)
    expect(fn).toHaveBeenCalledTimes(1)
  })

  it('resets timer on subsequent calls', () => {
    const fn = vi.fn()
    const debounced = debounce(fn, 100)

    debounced()
    vi.advanceTimersByTime(50)
    debounced()
    vi.advanceTimersByTime(50)
    expect(fn).not.toHaveBeenCalled()

    vi.advanceTimersByTime(50)
    expect(fn).toHaveBeenCalledTimes(1)
  })

  it('flush executes immediately', () => {
    const fn = vi.fn()
    const debounced = debounce(fn, 100)

    debounced()
    debounced.flush()
    expect(fn).toHaveBeenCalledTimes(1)
  })

  it('flush is no-op when no pending call', () => {
    const fn = vi.fn()
    const debounced = debounce(fn, 100)

    debounced.flush()
    expect(fn).not.toHaveBeenCalled()
  })

  it('cancel prevents execution', () => {
    const fn = vi.fn()
    const debounced = debounce(fn, 100)

    debounced()
    debounced.cancel()
    vi.advanceTimersByTime(200)
    expect(fn).not.toHaveBeenCalled()
  })
})

describe('useLayoutInit', () => {
  let opts

  function mockGroup(id) {
    return {
      id,
      locked: false,
      header: { hidden: false },
      panels: [],
      api: {
        setConstraints: vi.fn(),
        setSize: vi.fn(),
        width: 300,
        height: 250,
      },
    }
  }

  function mockPanel(id, group) {
    return {
      id,
      group: group || mockGroup(`group-${id}`),
      api: {
        setActive: vi.fn(),
        close: vi.fn(),
        updateParameters: vi.fn(),
      },
    }
  }

  function mockDockApi(panels = {}) {
    const removeHandlers = []
    const layoutHandlers = []
    return {
      getPanel: vi.fn((id) => panels[id] ?? null),
      getGroup: vi.fn((id) => panels[id]?.group ?? null),
      addPanel: vi.fn((config) => {
        const group = mockGroup(`group-${config.id}`)
        const panel = mockPanel(config.id, group)
        panels[config.id] = panel
        return panel
      }),
      panels: Object.values(panels),
      groups: [],
      onDidRemovePanel: vi.fn((handler) => removeHandlers.push(handler)),
      onDidLayoutChange: vi.fn((handler) => layoutHandlers.push(handler)),
      toJSON: vi.fn(() => ({})),
      _removeHandlers: removeHandlers,
      _layoutHandlers: layoutHandlers,
    }
  }

  beforeEach(() => {
    vi.clearAllMocks()
    // Clear localStorage
    localStorage.clear()

    opts = {
      setDockApi: vi.fn(),
      setTabs: vi.fn(),
      storagePrefix: 'test',
      panelMinRef: {
        current: { filetree: 180, terminal: 250, shell: 100, center: 200 },
      },
      panelCollapsedRef: {
        current: { filetree: 48, terminal: 48, shell: 36 },
      },
      panelSizesRef: {
        current: { filetree: 280, terminal: 400, shell: 250 },
      },
      centerGroupRef: { current: null },
      isInitialized: { current: false },
      ensureCorePanelsRef: { current: null },
      storagePrefixRef: { current: 'test' },
      projectRootRef: { current: '/project' },
      layoutVersionRef: { current: 1 },
    }
  })

  it('returns a function', () => {
    const { result } = renderHook(() => useLayoutInit(opts))
    expect(typeof result.current).toBe('function')
  })

  it('calls setDockApi with the event api', () => {
    const { result } = renderHook(() => useLayoutInit(opts))
    const api = mockDockApi()

    result.current({ api })

    expect(opts.setDockApi).toHaveBeenCalledWith(api)
  })

  it('marks isInitialized after onReady', () => {
    const { result } = renderHook(() => useLayoutInit(opts))
    const api = mockDockApi()

    result.current({ api })

    expect(opts.isInitialized.current).toBe(true)
  })

  it('creates core panels when no saved layout', () => {
    const { result } = renderHook(() => useLayoutInit(opts))
    const api = mockDockApi()

    result.current({ api })

    // Should have created filetree, terminal, empty-center, shell
    expect(api.addPanel).toHaveBeenCalled()
    const addedIds = api.addPanel.mock.calls.map((c) => c[0].id)
    expect(addedIds).toContain('filetree')
    expect(addedIds).toContain('terminal')
    expect(addedIds).toContain('empty-center')
    expect(addedIds).toContain('shell')
  })

  it('sets ensureCorePanelsRef', () => {
    const { result } = renderHook(() => useLayoutInit(opts))
    const api = mockDockApi()

    result.current({ api })

    expect(typeof opts.ensureCorePanelsRef.current).toBe('function')
  })

  it('registers onDidRemovePanel handlers', () => {
    const { result } = renderHook(() => useLayoutInit(opts))
    const api = mockDockApi()

    result.current({ api })

    expect(api.onDidRemovePanel).toHaveBeenCalled()
  })

  it('registers onDidLayoutChange handler', () => {
    const { result } = renderHook(() => useLayoutInit(opts))
    const api = mockDockApi()

    result.current({ api })

    expect(api.onDidLayoutChange).toHaveBeenCalled()
  })

  it('cleans up editor tabs on panel remove', () => {
    const { result } = renderHook(() => useLayoutInit(opts))
    const api = mockDockApi()

    result.current({ api })

    // Simulate editor panel removal
    const removeHandler = api._removeHandlers[0]
    removeHandler({ id: 'editor-src/app.js' })

    expect(opts.setTabs).toHaveBeenCalledWith(expect.any(Function))
  })

  it('does not clean up non-editor panel removes', () => {
    const { result } = renderHook(() => useLayoutInit(opts))
    const api = mockDockApi()

    result.current({ api })

    const removeHandler = api._removeHandlers[0]
    removeHandler({ id: 'review-123' })

    expect(opts.setTabs).not.toHaveBeenCalled()
  })
})
