import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'

// Mock dependencies before importing hook
vi.mock('../../config', () => ({
  useConfig: vi.fn(() => ({})),
}))

vi.mock('../../hooks/useCapabilities', () => ({
  useCapabilities: vi.fn(() => ({ capabilities: null, loading: true })),
}))

vi.mock('../../layout', () => ({
  loadCollapsedState: vi.fn(() => ({
    filetree: false,
    terminal: false,
    shell: false,
  })),
  loadPanelSizes: vi.fn(() => null),
}))

vi.mock('../../registry/panes', () => ({
  getUnavailableEssentialPanes: vi.fn(() => []),
}))

import { useAppState, DEFAULT_PANEL_DEFAULTS, DEFAULT_PANEL_MIN, DEFAULT_PANEL_COLLAPSED } from '../../hooks/useAppState'
import { useConfig } from '../../config'
import { useCapabilities } from '../../hooks/useCapabilities'
import { loadCollapsedState, loadPanelSizes } from '../../layout'
import { getUnavailableEssentialPanes } from '../../registry/panes'

describe('useAppState', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useConfig.mockReturnValue({})
    useCapabilities.mockReturnValue({ capabilities: null, loading: true })
    loadCollapsedState.mockReturnValue({
      filetree: false,
      terminal: false,
      shell: false,
    })
    loadPanelSizes.mockReturnValue(null)
    getUnavailableEssentialPanes.mockReturnValue([])
  })

  it('returns all expected state keys', () => {
    const { result } = renderHook(() => useAppState())
    const state = result.current

    // Config
    expect(state).toHaveProperty('config')
    expect(state).toHaveProperty('storagePrefix')
    expect(state).toHaveProperty('layoutVersion')
    expect(state).toHaveProperty('panelDefaults')
    expect(state).toHaveProperty('panelMin')
    expect(state).toHaveProperty('panelCollapsed')

    // Capabilities
    expect(state).toHaveProperty('capabilities')
    expect(state).toHaveProperty('capabilitiesLoading')
    expect(state).toHaveProperty('unavailableEssentials')

    // Dockview
    expect(state).toHaveProperty('dockApi')
    expect(state).toHaveProperty('setDockApi')

    // Tabs / files
    expect(state).toHaveProperty('tabs')
    expect(state).toHaveProperty('setTabs')
    expect(state).toHaveProperty('activeFile')
    expect(state).toHaveProperty('setActiveFile')
    expect(state).toHaveProperty('activeDiffFile')
    expect(state).toHaveProperty('setActiveDiffFile')

    // Approvals
    expect(state).toHaveProperty('approvals')
    expect(state).toHaveProperty('setApprovals')
    expect(state).toHaveProperty('approvalsLoaded')
    expect(state).toHaveProperty('setApprovalsLoaded')

    // Collapsed
    expect(state).toHaveProperty('collapsed')
    expect(state).toHaveProperty('setCollapsed')
    expect(state).toHaveProperty('panelSizesRef')

    // Project
    expect(state).toHaveProperty('projectRoot')
    expect(state).toHaveProperty('setProjectRoot')

    // Refs
    expect(state).toHaveProperty('projectRootRef')
    expect(state).toHaveProperty('storagePrefixRef')
    expect(state).toHaveProperty('layoutVersionRef')
    expect(state).toHaveProperty('panelCollapsedRef')
    expect(state).toHaveProperty('panelMinRef')
    expect(state).toHaveProperty('collapsedEffectRan')
    expect(state).toHaveProperty('dismissedApprovalsRef')
    expect(state).toHaveProperty('centerGroupRef')
    expect(state).toHaveProperty('isInitialized')
    expect(state).toHaveProperty('layoutRestored')
    expect(state).toHaveProperty('ensureCorePanelsRef')
  })

  it('applies config defaults when config is empty', () => {
    const { result } = renderHook(() => useAppState())

    expect(result.current.storagePrefix).toBe('kurt-web')
    expect(result.current.layoutVersion).toBe(1)
    expect(result.current.panelDefaults).toEqual(DEFAULT_PANEL_DEFAULTS)
    expect(result.current.panelMin).toEqual(DEFAULT_PANEL_MIN)
    expect(result.current.panelCollapsed).toEqual(DEFAULT_PANEL_COLLAPSED)
  })

  it('uses config values when provided', () => {
    useConfig.mockReturnValue({
      storage: { prefix: 'custom-prefix', layoutVersion: 3 },
      panels: {
        defaults: { filetree: 300, terminal: 500, shell: 200 },
        min: { filetree: 100, terminal: 100, shell: 50, center: 100 },
        collapsed: { filetree: 30, terminal: 30, shell: 20 },
      },
    })

    const { result } = renderHook(() => useAppState())

    expect(result.current.storagePrefix).toBe('custom-prefix')
    expect(result.current.layoutVersion).toBe(3)
    expect(result.current.panelDefaults).toEqual({
      filetree: 300,
      terminal: 500,
      shell: 200,
    })
    expect(result.current.panelMin).toEqual({
      filetree: 100,
      terminal: 100,
      shell: 50,
      center: 100,
    })
  })

  it('initializes collapsed state from localStorage', () => {
    const savedCollapsed = { filetree: true, terminal: false, shell: true }
    loadCollapsedState.mockReturnValue(savedCollapsed)

    const { result } = renderHook(() => useAppState())

    expect(loadCollapsedState).toHaveBeenCalledWith('kurt-web')
    expect(result.current.collapsed).toEqual(savedCollapsed)
  })

  it('initializes panelSizesRef from localStorage', () => {
    const savedSizes = { filetree: 350, terminal: 450, shell: 300 }
    loadPanelSizes.mockReturnValue(savedSizes)

    const { result } = renderHook(() => useAppState())

    expect(loadPanelSizes).toHaveBeenCalledWith('kurt-web')
    expect(result.current.panelSizesRef.current).toEqual(savedSizes)
  })

  it('falls back to panelDefaults when no saved sizes', () => {
    loadPanelSizes.mockReturnValue(null)

    const { result } = renderHook(() => useAppState())

    expect(result.current.panelSizesRef.current).toEqual(DEFAULT_PANEL_DEFAULTS)
  })

  it('reports capabilities loading state', () => {
    useCapabilities.mockReturnValue({ capabilities: null, loading: true })

    const { result } = renderHook(() => useAppState())

    expect(result.current.capabilities).toBeNull()
    expect(result.current.capabilitiesLoading).toBe(true)
  })

  it('computes unavailableEssentials when capabilities loaded', () => {
    const caps = { files: true, git: true, pty: false }
    useCapabilities.mockReturnValue({ capabilities: caps, loading: false })
    getUnavailableEssentialPanes.mockReturnValue(['terminal'])

    const { result } = renderHook(() => useAppState())

    expect(getUnavailableEssentialPanes).toHaveBeenCalledWith(caps)
    expect(result.current.unavailableEssentials).toEqual(['terminal'])
  })

  it('returns empty unavailableEssentials when capabilities null', () => {
    useCapabilities.mockReturnValue({ capabilities: null, loading: true })

    const { result } = renderHook(() => useAppState())

    expect(getUnavailableEssentialPanes).not.toHaveBeenCalled()
    expect(result.current.unavailableEssentials).toEqual([])
  })

  it('initial state values are correct', () => {
    const { result } = renderHook(() => useAppState())

    expect(result.current.dockApi).toBeNull()
    expect(result.current.tabs).toEqual({})
    expect(result.current.activeFile).toBeNull()
    expect(result.current.activeDiffFile).toBeNull()
    expect(result.current.approvals).toEqual([])
    expect(result.current.approvalsLoaded).toBe(false)
    expect(result.current.projectRoot).toBeNull()
  })

  it('setters update state correctly', () => {
    const { result } = renderHook(() => useAppState())

    act(() => {
      result.current.setActiveFile('src/index.js')
    })
    expect(result.current.activeFile).toBe('src/index.js')

    act(() => {
      result.current.setTabs({ 'a.js': { content: 'x', isDirty: false } })
    })
    expect(result.current.tabs).toEqual({
      'a.js': { content: 'x', isDirty: false },
    })

    act(() => {
      result.current.setProjectRoot('/home/user/project')
    })
    expect(result.current.projectRoot).toBe('/home/user/project')

    act(() => {
      result.current.setApprovalsLoaded(true)
    })
    expect(result.current.approvalsLoaded).toBe(true)
  })

  it('refs have correct initial values', () => {
    const { result } = renderHook(() => useAppState())

    expect(result.current.projectRootRef.current).toBeNull()
    expect(result.current.storagePrefixRef.current).toBe('kurt-web')
    expect(result.current.layoutVersionRef.current).toBe(1)
    expect(result.current.collapsedEffectRan.current).toBe(false)
    expect(result.current.dismissedApprovalsRef.current).toBeInstanceOf(Set)
    expect(result.current.dismissedApprovalsRef.current.size).toBe(0)
    expect(result.current.centerGroupRef.current).toBeNull()
    expect(result.current.isInitialized.current).toBe(false)
    expect(result.current.layoutRestored.current).toBe(false)
    expect(result.current.ensureCorePanelsRef.current).toBeNull()
  })

  it('storagePrefixRef stays in sync with config', () => {
    useConfig.mockReturnValue({ storage: { prefix: 'v1' } })
    const { result, rerender } = renderHook(() => useAppState())

    expect(result.current.storagePrefixRef.current).toBe('v1')

    useConfig.mockReturnValue({ storage: { prefix: 'v2' } })
    rerender()

    expect(result.current.storagePrefixRef.current).toBe('v2')
  })

  it('panelMinRef stays in sync with config', () => {
    const min1 = { filetree: 100, terminal: 100, shell: 50, center: 100 }
    const min2 = { filetree: 200, terminal: 200, shell: 100, center: 200 }

    useConfig.mockReturnValue({ panels: { min: min1 } })
    const { result, rerender } = renderHook(() => useAppState())
    expect(result.current.panelMinRef.current).toEqual(min1)

    useConfig.mockReturnValue({ panels: { min: min2 } })
    rerender()
    expect(result.current.panelMinRef.current).toEqual(min2)
  })
})
