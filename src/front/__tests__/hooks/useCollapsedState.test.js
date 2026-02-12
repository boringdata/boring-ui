import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import {
  useCollapsedEffect,
  DEFAULT_COLLAPSE_PANELS,
} from '../../hooks/useCollapsedState'

function mockGroup() {
  return {
    api: {
      setConstraints: vi.fn(),
      setSize: vi.fn(),
    },
  }
}

function mockDockApi(panels = {}) {
  return {
    getPanel: (id) => panels[id] ?? null,
  }
}

function mockPanel(group) {
  return { group }
}

describe('DEFAULT_COLLAPSE_PANELS', () => {
  it('has filetree (width), terminal (width), shell (height)', () => {
    expect(DEFAULT_COLLAPSE_PANELS).toEqual([
      { panelId: 'filetree', dimension: 'width' },
      { panelId: 'terminal', dimension: 'width' },
      { panelId: 'shell', dimension: 'height' },
    ])
  })
})

describe('useCollapsedEffect', () => {
  let panelSizesRef
  let panelCollapsedRef
  let panelMinRef
  let collapsedEffectRan

  beforeEach(() => {
    vi.clearAllMocks()
    panelSizesRef = { current: { filetree: 280, terminal: 400, shell: 250 } }
    panelCollapsedRef = { current: { filetree: 48, terminal: 48, shell: 36 } }
    panelMinRef = { current: { filetree: 180, terminal: 250, shell: 100 } }
    collapsedEffectRan = { current: false }
  })

  function renderEffect(dockApi, collapsed, overrides = {}) {
    return renderHook(() =>
      useCollapsedEffect({
        dockApi,
        collapsed,
        panelSizesRef,
        panelCollapsedRef,
        panelMinRef,
        collapsedEffectRan,
        ...overrides,
      }),
    )
  }

  it('skips when dockApi is null', () => {
    const collapsed = { filetree: false, terminal: false, shell: false }
    renderEffect(null, collapsed)
    expect(collapsedEffectRan.current).toBe(false)
  })

  it('sets collapsedEffectRan on first run', () => {
    const dockApi = mockDockApi({})
    const collapsed = { filetree: false, terminal: false, shell: false }
    renderEffect(dockApi, collapsed)
    expect(collapsedEffectRan.current).toBe(true)
  })

  it('first run: applies constraints but skips setSize for expanded panels', () => {
    const filetreeGroup = mockGroup()
    const dockApi = mockDockApi({
      filetree: mockPanel(filetreeGroup),
    })
    const collapsed = { filetree: false, terminal: false, shell: false }

    renderEffect(dockApi, collapsed)

    // Constraints are set
    expect(filetreeGroup.api.setConstraints).toHaveBeenCalledWith({
      minimumWidth: 180,
      maximumWidth: Infinity,
    })
    // setSize NOT called on first run for expanded panels
    expect(filetreeGroup.api.setSize).not.toHaveBeenCalled()
  })

  it('first run: applies constraints AND setSize for collapsed panels', () => {
    const filetreeGroup = mockGroup()
    const dockApi = mockDockApi({
      filetree: mockPanel(filetreeGroup),
    })
    const collapsed = { filetree: true, terminal: false, shell: false }

    renderEffect(dockApi, collapsed)

    expect(filetreeGroup.api.setConstraints).toHaveBeenCalledWith({
      minimumWidth: 48,
      maximumWidth: 48,
    })
    expect(filetreeGroup.api.setSize).toHaveBeenCalledWith({ width: 48 })
  })

  it('subsequent run: sets size for expanded panels', () => {
    const filetreeGroup = mockGroup()
    const dockApi = mockDockApi({
      filetree: mockPanel(filetreeGroup),
    })
    // Mark as not first run
    collapsedEffectRan.current = true
    const collapsed = { filetree: false, terminal: false, shell: false }

    renderEffect(dockApi, collapsed)

    expect(filetreeGroup.api.setConstraints).toHaveBeenCalledWith({
      minimumWidth: 180,
      maximumWidth: Infinity,
    })
    expect(filetreeGroup.api.setSize).toHaveBeenCalledWith({ width: 280 })
  })

  it('collapsed panel: sets min=max=collapsedSize for width panel', () => {
    collapsedEffectRan.current = true
    const terminalGroup = mockGroup()
    const dockApi = mockDockApi({
      terminal: mockPanel(terminalGroup),
    })
    const collapsed = { filetree: false, terminal: true, shell: false }

    renderEffect(dockApi, collapsed)

    expect(terminalGroup.api.setConstraints).toHaveBeenCalledWith({
      minimumWidth: 48,
      maximumWidth: 48,
    })
    expect(terminalGroup.api.setSize).toHaveBeenCalledWith({ width: 48 })
  })

  it('shell uses height dimension', () => {
    collapsedEffectRan.current = true
    const shellGroup = mockGroup()
    const dockApi = mockDockApi({
      shell: mockPanel(shellGroup),
    })
    const collapsed = { filetree: false, terminal: false, shell: true }

    renderEffect(dockApi, collapsed)

    expect(shellGroup.api.setConstraints).toHaveBeenCalledWith({
      minimumHeight: 36,
      maximumHeight: 36,
    })
    expect(shellGroup.api.setSize).toHaveBeenCalledWith({ height: 36 })
  })

  it('shell expanded: applies Math.max(savedSize, minSize)', () => {
    collapsedEffectRan.current = true
    panelSizesRef.current.shell = 50 // below min of 100
    const shellGroup = mockGroup()
    const dockApi = mockDockApi({
      shell: mockPanel(shellGroup),
    })
    const collapsed = { filetree: false, terminal: false, shell: false }

    renderEffect(dockApi, collapsed)

    expect(shellGroup.api.setSize).toHaveBeenCalledWith({ height: 100 }) // min, not 50
  })

  it('shell expanded: uses saved size when above min', () => {
    collapsedEffectRan.current = true
    panelSizesRef.current.shell = 250
    const shellGroup = mockGroup()
    const dockApi = mockDockApi({
      shell: mockPanel(shellGroup),
    })
    const collapsed = { filetree: false, terminal: false, shell: false }

    renderEffect(dockApi, collapsed)

    expect(shellGroup.api.setSize).toHaveBeenCalledWith({ height: 250 })
  })

  it('width panels use saved size directly (no Math.max)', () => {
    collapsedEffectRan.current = true
    panelSizesRef.current.filetree = 100 // below min of 180, but width doesn't clamp
    const filetreeGroup = mockGroup()
    const dockApi = mockDockApi({
      filetree: mockPanel(filetreeGroup),
    })
    const collapsed = { filetree: false, terminal: false, shell: false }

    renderEffect(dockApi, collapsed)

    // Width panels use savedSize directly (Dockview enforces constraints)
    expect(filetreeGroup.api.setSize).toHaveBeenCalledWith({ width: 100 })
  })

  it('handles missing panels gracefully', () => {
    collapsedEffectRan.current = true
    const dockApi = mockDockApi({}) // no panels
    const collapsed = { filetree: true, terminal: true, shell: true }

    // Should not throw
    expect(() => renderEffect(dockApi, collapsed)).not.toThrow()
  })

  it('handles panel without group gracefully', () => {
    collapsedEffectRan.current = true
    const dockApi = mockDockApi({
      filetree: { group: null },
    })
    const collapsed = { filetree: true, terminal: false, shell: false }

    expect(() => renderEffect(dockApi, collapsed)).not.toThrow()
  })

  it('works with custom panel configs', () => {
    collapsedEffectRan.current = true
    const sidebarGroup = mockGroup()
    const dockApi = mockDockApi({
      sidebar: mockPanel(sidebarGroup),
    })
    panelCollapsedRef.current = { sidebar: 40 }
    panelMinRef.current = { sidebar: 150 }
    panelSizesRef.current = { sidebar: 300 }
    const collapsed = { sidebar: true }
    const customPanels = [{ panelId: 'sidebar', dimension: 'width' }]

    renderEffect(dockApi, collapsed, { panels: customPanels })

    expect(sidebarGroup.api.setConstraints).toHaveBeenCalledWith({
      minimumWidth: 40,
      maximumWidth: 40,
    })
    expect(sidebarGroup.api.setSize).toHaveBeenCalledWith({ width: 40 })
  })
})
