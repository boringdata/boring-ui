import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useLayoutRestore } from '../../hooks/useLayoutRestore'

// Mock the layout module
vi.mock('../../layout', () => ({
  loadLayout: vi.fn(() => null),
  saveLayout: vi.fn(),
  pruneEmptyGroups: vi.fn(() => false),
  getFileName: vi.fn((p) => p.split('/').pop()),
}))

import { loadLayout, saveLayout, pruneEmptyGroups } from '../../layout'

function mockGroupApi(opts = {}) {
  return {
    setConstraints: vi.fn(),
    setSize: vi.fn(),
    height: opts.height ?? 200,
  }
}

function mockGroup(id, opts = {}) {
  return {
    id,
    locked: false,
    header: { hidden: false },
    api: mockGroupApi(opts),
    panels: [],
  }
}

function mockPanel(id, group = null) {
  return {
    id,
    group,
    api: {
      close: vi.fn(),
      updateParameters: vi.fn(),
      setTitle: vi.fn(),
      setActive: vi.fn(),
    },
  }
}

function mockDockApi(panels = [], panelMap = {}, groupMap = {}) {
  return {
    panels,
    fromJSON: vi.fn(),
    toJSON: vi.fn(() => ({})),
    getPanel: vi.fn((id) => panelMap[id] ?? null),
    getGroup: vi.fn((id) => groupMap[id] ?? null),
    getPanels: vi.fn(() => panels),
  }
}

describe('useLayoutRestore', () => {
  let defaultOpts
  // Capture requestAnimationFrame callbacks
  let rafCallbacks

  beforeEach(() => {
    vi.clearAllMocks()
    rafCallbacks = []
    vi.spyOn(globalThis, 'requestAnimationFrame').mockImplementation((cb) => {
      rafCallbacks.push(cb)
      return rafCallbacks.length
    })

    loadLayout.mockReturnValue(null)
    pruneEmptyGroups.mockReturnValue(false)

    defaultOpts = {
      dockApi: mockDockApi(),
      projectRoot: '/project',
      storagePrefix: 'test',
      layoutVersion: 1,
      knownComponents: ['filetree', 'terminal', 'shell', 'editor', 'review'],
      collapsed: { filetree: false, terminal: false, shell: false },
      panelCollapsedRef: { current: { filetree: 36, terminal: 36, shell: 36 } },
      panelMinRef: { current: { filetree: 200, terminal: 200, shell: 100, center: 100 } },
      panelSizesRef: { current: { filetree: 250, terminal: 250, shell: 150 } },
      centerGroupRef: { current: null },
      layoutRestored: { current: false },
      collapsedEffectRan: { current: false },
      ensureCorePanelsRef: { current: vi.fn() },
      openFile: vi.fn(),
      openFileToSide: vi.fn(),
      openDiff: vi.fn(),
      activeFile: null,
      activeDiffFile: null,
      toggleFiletree: vi.fn(),
      setTabs: vi.fn(),
    }
  })

  function render(overrides = {}) {
    return renderHook(() =>
      useLayoutRestore({ ...defaultOpts, ...overrides }),
    )
  }

  it('does nothing when dockApi is null', () => {
    render({ dockApi: null })
    expect(loadLayout).not.toHaveBeenCalled()
  })

  it('does nothing when projectRoot is null', () => {
    render({ projectRoot: null })
    expect(loadLayout).not.toHaveBeenCalled()
  })

  it('calls ensureCorePanels when no saved layout', () => {
    render()
    expect(defaultOpts.ensureCorePanelsRef.current).toHaveBeenCalled()
    expect(defaultOpts.layoutRestored.current).toBe(true)
  })

  it('applies collapsed sizes after ensuring core panels', () => {
    const ftGroup = mockGroup('ft-group')
    const dockApi = mockDockApi([], { filetree: mockPanel('filetree', ftGroup) }, { 'ft-group': { api: mockGroupApi() } })
    render({ dockApi })

    // Trigger rAF callback
    expect(rafCallbacks.length).toBe(1)
    rafCallbacks[0]()

    expect(defaultOpts.collapsedEffectRan.current).toBe(true)
  })

  it('restores saved layout with fromJSON', () => {
    const savedLayout = { grid: {} }
    loadLayout.mockReturnValue(savedLayout)

    const dockApi = mockDockApi()
    render({ dockApi })

    expect(dockApi.fromJSON).toHaveBeenCalledWith(savedLayout)
    expect(defaultOpts.layoutRestored.current).toBe(true)
  })

  it('locks filetree group and hides header', () => {
    loadLayout.mockReturnValue({ grid: {} })

    const ftGroup = mockGroup('ft-group')
    const ftPanel = mockPanel('filetree', ftGroup)
    const dockApi = mockDockApi([], { filetree: ftPanel })

    render({ dockApi })

    expect(ftGroup.locked).toBe(true)
    expect(ftGroup.header.hidden).toBe(true)
  })

  it('restores filetree panel callbacks', () => {
    loadLayout.mockReturnValue({ grid: {} })

    const ftPanel = mockPanel('filetree', mockGroup('ft-group'))
    const dockApi = mockDockApi([], { filetree: ftPanel })

    render({ dockApi })

    expect(ftPanel.api.updateParameters).toHaveBeenCalledWith(
      expect.objectContaining({
        onOpenFile: defaultOpts.openFile,
        onOpenFileToSide: defaultOpts.openFileToSide,
        onOpenDiff: defaultOpts.openDiff,
        projectRoot: '/project',
      }),
    )
  })

  it('locks terminal group', () => {
    loadLayout.mockReturnValue({ grid: {} })

    const tGroup = mockGroup('t-group')
    const tPanel = mockPanel('terminal', tGroup)
    const dockApi = mockDockApi([], { terminal: tPanel })

    render({ dockApi })

    expect(tGroup.locked).toBe(true)
    expect(tGroup.header.hidden).toBe(true)
  })

  it('locks shell group with constraints', () => {
    loadLayout.mockReturnValue({ grid: {} })

    const sGroup = mockGroup('s-group')
    const sPanel = mockPanel('shell', sGroup)
    const dockApi = mockDockApi([], { shell: sPanel })

    render({ dockApi })

    expect(sGroup.locked).toBe(true)
    expect(sGroup.header.hidden).toBe(false)
    expect(sGroup.api.setConstraints).toHaveBeenCalledWith({
      minimumHeight: 100,
      maximumHeight: Infinity,
    })
  })

  it('fixes shell height when between collapsed and min', () => {
    loadLayout.mockReturnValue({ grid: {} })

    const sGroup = mockGroup('s-group', { height: 50 })
    const sPanel = mockPanel('shell', sGroup)
    const dockApi = mockDockApi([], { shell: sPanel })

    render({ dockApi })

    // Height 50 is between collapsed (36) and min (100), so should be fixed
    expect(sGroup.api.setSize).toHaveBeenCalledWith({ height: 100 })
  })

  it('sets center group ref from editor panel', () => {
    loadLayout.mockReturnValue({ grid: {} })

    const editorGroup = mockGroup('editor-group')
    const editorPanel = mockPanel('editor-file.js', editorGroup)
    const dockApi = mockDockApi([editorPanel], {})
    const centerGroupRef = { current: null }

    render({ dockApi, centerGroupRef })

    expect(centerGroupRef.current).toBe(editorGroup)
    expect(editorGroup.api.setConstraints).toHaveBeenCalledWith({
      minimumHeight: 100,
      maximumHeight: Infinity,
    })
  })

  it('closes empty-center when editors exist', () => {
    loadLayout.mockReturnValue({ grid: {} })

    const emptyPanel = mockPanel('empty-center')
    const editorPanel = mockPanel('editor-file.js', mockGroup('eg'))
    const dockApi = mockDockApi([editorPanel], { 'empty-center': emptyPanel })

    render({ dockApi })

    expect(emptyPanel.api.close).toHaveBeenCalled()
  })

  it('restores editor panel callbacks', () => {
    loadLayout.mockReturnValue({ grid: {} })

    const editorPanel = mockPanel('editor-src/app.js')
    const dockApi = mockDockApi([editorPanel], {})

    render({ dockApi })

    expect(editorPanel.api.updateParameters).toHaveBeenCalledWith(
      expect.objectContaining({
        onContentChange: expect.any(Function),
        onDirtyChange: expect.any(Function),
      }),
    )
  })

  it('prunes empty groups and saves if pruned', () => {
    loadLayout.mockReturnValue({ grid: {} })
    pruneEmptyGroups.mockReturnValue(true)

    const dockApi = mockDockApi()
    render({ dockApi })

    expect(pruneEmptyGroups).toHaveBeenCalled()
    expect(saveLayout).toHaveBeenCalled()
  })

  it('does not save when no groups pruned', () => {
    loadLayout.mockReturnValue({ grid: {} })
    pruneEmptyGroups.mockReturnValue(false)

    const dockApi = mockDockApi()
    render({ dockApi })

    expect(saveLayout).not.toHaveBeenCalled()
  })

  it('only runs once (guard ref)', () => {
    const dockApi = mockDockApi()
    const { rerender } = render({ dockApi })

    expect(loadLayout).toHaveBeenCalledTimes(1)

    rerender()
    expect(loadLayout).toHaveBeenCalledTimes(1)
  })

  it('handles fromJSON error gracefully', () => {
    loadLayout.mockReturnValue({ grid: {} })
    const dockApi = mockDockApi()
    dockApi.fromJSON.mockImplementation(() => {
      throw new Error('bad layout')
    })
    const layoutRestored = { current: false }

    render({ dockApi, layoutRestored })

    expect(layoutRestored.current).toBe(false)
  })

  it('tracks center group from empty panel when no editors', () => {
    loadLayout.mockReturnValue({ grid: {} })

    const emptyGroup = mockGroup('empty-group')
    const emptyPanel = mockPanel('empty-center', emptyGroup)
    const dockApi = mockDockApi([], { 'empty-center': emptyPanel })
    const centerGroupRef = { current: null }

    render({ dockApi, centerGroupRef })

    expect(centerGroupRef.current).toBe(emptyGroup)
  })
})
