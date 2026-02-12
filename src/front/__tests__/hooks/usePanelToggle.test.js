import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'

vi.mock('../../layout', () => ({
  savePanelSizes: vi.fn(),
  saveCollapsedState: vi.fn(),
}))

import {
  usePanelToggle,
  DEFAULT_TOGGLE_CONFIGS,
} from '../../hooks/usePanelToggle'
import { savePanelSizes, saveCollapsedState } from '../../layout'

function mockDockApi(panels = {}) {
  return {
    getPanel: (id) => panels[id] ?? null,
  }
}

function mockPanel(dimension, size) {
  return {
    group: {
      api: { [dimension]: size },
    },
  }
}

describe('DEFAULT_TOGGLE_CONFIGS', () => {
  it('includes filetree, terminal, shell', () => {
    const keys = DEFAULT_TOGGLE_CONFIGS.map((c) => c.stateKey)
    expect(keys).toEqual(['filetree', 'terminal', 'shell'])
  })

  it('filetree and terminal use width, shell uses height', () => {
    const dims = DEFAULT_TOGGLE_CONFIGS.map((c) => c.dimension)
    expect(dims).toEqual(['width', 'width', 'height'])
  })
})

describe('usePanelToggle', () => {
  let collapsed
  let setCollapsed
  let panelSizesRef
  let panelCollapsedRef
  let storagePrefixRef

  beforeEach(() => {
    vi.clearAllMocks()
    collapsed = { filetree: false, terminal: false, shell: false }
    setCollapsed = vi.fn((fn) => {
      if (typeof fn === 'function') {
        collapsed = fn(collapsed)
      }
    })
    panelSizesRef = { current: { filetree: 280, terminal: 400, shell: 250 } }
    panelCollapsedRef = { current: { filetree: 48, terminal: 48, shell: 36 } }
    storagePrefixRef = { current: 'test-prefix' }
  })

  function renderToggle(dockApi, overrides = {}) {
    return renderHook(() =>
      usePanelToggle({
        dockApi,
        collapsed,
        setCollapsed,
        panelSizesRef,
        panelCollapsedRef,
        storagePrefixRef,
        ...overrides,
      }),
    )
  }

  it('returns toggle functions for all default panels', () => {
    const { result } = renderToggle(null)
    expect(typeof result.current.filetree).toBe('function')
    expect(typeof result.current.terminal).toBe('function')
    expect(typeof result.current.shell).toBe('function')
  })

  it('captures width before collapsing filetree', () => {
    const dockApi = mockDockApi({
      filetree: mockPanel('width', 300),
    })
    const { result } = renderToggle(dockApi)

    act(() => {
      result.current.filetree()
    })

    expect(panelSizesRef.current.filetree).toBe(300)
    expect(savePanelSizes).toHaveBeenCalledWith(
      expect.objectContaining({ filetree: 300 }),
      'test-prefix',
    )
  })

  it('captures width before collapsing terminal', () => {
    const dockApi = mockDockApi({
      terminal: mockPanel('width', 500),
    })
    const { result } = renderToggle(dockApi)

    act(() => {
      result.current.terminal()
    })

    expect(panelSizesRef.current.terminal).toBe(500)
    expect(savePanelSizes).toHaveBeenCalledWith(
      expect.objectContaining({ terminal: 500 }),
      'test-prefix',
    )
  })

  it('captures height before collapsing shell', () => {
    const dockApi = mockDockApi({
      shell: mockPanel('height', 200),
    })
    const { result } = renderToggle(dockApi)

    act(() => {
      result.current.shell()
    })

    expect(panelSizesRef.current.shell).toBe(200)
    expect(savePanelSizes).toHaveBeenCalledWith(
      expect.objectContaining({ shell: 200 }),
      'test-prefix',
    )
  })

  it('does not capture size when panel is already collapsed', () => {
    collapsed = { filetree: true, terminal: false, shell: false }
    const dockApi = mockDockApi({
      filetree: mockPanel('width', 300),
    })
    const { result } = renderToggle(dockApi)

    act(() => {
      result.current.filetree()
    })

    expect(savePanelSizes).not.toHaveBeenCalled()
  })

  it('does not capture size below collapsed threshold', () => {
    const dockApi = mockDockApi({
      filetree: mockPanel('width', 30), // below 48 threshold
    })
    const { result } = renderToggle(dockApi)

    act(() => {
      result.current.filetree()
    })

    expect(savePanelSizes).not.toHaveBeenCalled()
  })

  it('updates collapsed state via setCollapsed', () => {
    const { result } = renderToggle(null)

    act(() => {
      result.current.filetree()
    })

    expect(setCollapsed).toHaveBeenCalledWith(expect.any(Function))
    expect(collapsed.filetree).toBe(true)
  })

  it('persists collapsed state via saveCollapsedState', () => {
    const { result } = renderToggle(null)

    act(() => {
      result.current.terminal()
    })

    expect(saveCollapsedState).toHaveBeenCalledWith(
      expect.objectContaining({ terminal: true }),
      'test-prefix',
    )
  })

  it('handles null dockApi gracefully', () => {
    const { result } = renderToggle(null)

    expect(() => {
      act(() => {
        result.current.filetree()
      })
    }).not.toThrow()

    // State still toggles even without dockApi
    expect(setCollapsed).toHaveBeenCalled()
  })

  it('handles missing panel gracefully', () => {
    const dockApi = mockDockApi({}) // no panels
    const { result } = renderToggle(dockApi)

    expect(() => {
      act(() => {
        result.current.filetree()
      })
    }).not.toThrow()

    expect(savePanelSizes).not.toHaveBeenCalled()
    expect(setCollapsed).toHaveBeenCalled()
  })

  it('works with custom panel configs', () => {
    const customPanels = [
      { panelId: 'sidebar', stateKey: 'sidebar', dimension: 'width' },
    ]
    collapsed = { sidebar: false }
    const dockApi = mockDockApi({
      sidebar: mockPanel('width', 250),
    })

    const { result } = renderToggle(dockApi, { panels: customPanels })

    expect(typeof result.current.sidebar).toBe('function')
    expect(result.current.filetree).toBeUndefined()

    act(() => {
      result.current.sidebar()
    })

    expect(panelSizesRef.current.sidebar).toBe(250)
  })

  it('each toggle operates independently', () => {
    const dockApi = mockDockApi({
      filetree: mockPanel('width', 300),
      terminal: mockPanel('width', 450),
      shell: mockPanel('height', 200),
    })
    const { result } = renderToggle(dockApi)

    act(() => {
      result.current.filetree()
    })

    expect(panelSizesRef.current.filetree).toBe(300)
    expect(panelSizesRef.current.terminal).toBe(400) // unchanged
    expect(panelSizesRef.current.shell).toBe(250) // unchanged
  })
})
