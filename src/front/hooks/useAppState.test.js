/**
 * Tests for useAppState hook.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useConfig } from '../config'
import { useCapabilities } from './useCapabilities'
import { useAppState } from './useAppState'

// ── Mocks ────────────────────────────────────────────────────────────────

vi.mock('../config', () => ({
  useConfig: vi.fn(() => ({
    storage: { prefix: 'test-prefix', layoutVersion: 2 },
    panels: {
      defaults: { filetree: 300, terminal: 450, shell: 200 },
      min: { filetree: 150, terminal: 200, shell: 80, center: 180 },
      collapsed: { filetree: 40, terminal: 40, shell: 30 },
    },
  })),
}))

vi.mock('./useCapabilities', () => ({
  useCapabilities: vi.fn(() => ({
    capabilities: { shell: true, filetree: true, sandbox: false },
    loading: false,
  })),
}))

vi.mock('./useProjectRoot', () => ({
  useProjectRoot: vi.fn(() => ({
    projectRoot: '/test/project',
    projectRootRef: { current: '/test/project' },
  })),
}))

vi.mock('../layout', () => ({
  loadCollapsedState: vi.fn(() => ({
    filetree: false,
    terminal: false,
    shell: false,
  })),
  loadPanelSizes: vi.fn(() => null),
}))

vi.mock('../registry/panes', () => ({
  getUnavailableEssentialPanes: vi.fn((caps) => {
    const missing = []
    if (!caps.shell) missing.push('shell')
    if (!caps.filetree) missing.push('filetree')
    return missing
  }),
}))

// ── Tests ────────────────────────────────────────────────────────────────

describe('useAppState', () => {
  it('returns config-derived values from useConfig', () => {
    const { result } = renderHook(() => useAppState())

    expect(result.current.storagePrefix).toBe('test-prefix')
    expect(result.current.layoutVersion).toBe(2)
    expect(result.current.panelDefaults).toEqual({
      filetree: 300, terminal: 450, shell: 200,
    })
    expect(result.current.panelMin).toEqual({
      filetree: 150, terminal: 200, shell: 80, center: 180,
    })
    expect(result.current.panelCollapsed).toEqual({
      filetree: 40, terminal: 40, shell: 30,
    })
  })

  it('returns capabilities from useCapabilities', () => {
    const { result } = renderHook(() => useAppState())

    expect(result.current.capabilities).toEqual({
      shell: true, filetree: true, sandbox: false,
    })
    expect(result.current.capabilitiesLoading).toBe(false)
  })

  it('computes unavailableEssentials from capabilities', () => {
    const { result } = renderHook(() => useAppState())
    expect(result.current.unavailableEssentials).toEqual([])
  })

  it('initializes core state with defaults', () => {
    const { result } = renderHook(() => useAppState())

    expect(result.current.dockApi).toBeNull()
    expect(result.current.tabs).toEqual({})
    expect(result.current.activeFile).toBeNull()
    expect(result.current.activeDiffFile).toBeNull()
  })

  it('provides state setters that update values', () => {
    const { result } = renderHook(() => useAppState())

    act(() => {
      result.current.setDockApi({ mock: true })
    })
    expect(result.current.dockApi).toEqual({ mock: true })

    act(() => {
      result.current.setTabs({ 'file.js': { content: 'x', isDirty: false } })
    })
    expect(result.current.tabs).toEqual({
      'file.js': { content: 'x', isDirty: false },
    })

    act(() => {
      result.current.setActiveFile('file.js')
    })
    expect(result.current.activeFile).toBe('file.js')

    act(() => {
      result.current.setActiveDiffFile('diff.js')
    })
    expect(result.current.activeDiffFile).toBe('diff.js')
  })

  it('initializes collapsed state from localStorage', () => {
    const { result } = renderHook(() => useAppState())

    expect(result.current.collapsed).toEqual({
      filetree: false,
      terminal: false,
      shell: false,
    })
  })

  it('provides stable refs across rerenders', () => {
    const { result, rerender } = renderHook(() => useAppState())

    const refs1 = {
      panelSizesRef: result.current.panelSizesRef,
      centerGroupRef: result.current.centerGroupRef,
      isInitialized: result.current.isInitialized,
      layoutRestored: result.current.layoutRestored,
      ensureCorePanelsRef: result.current.ensureCorePanelsRef,
    }

    rerender()

    expect(result.current.panelSizesRef).toBe(refs1.panelSizesRef)
    expect(result.current.centerGroupRef).toBe(refs1.centerGroupRef)
    expect(result.current.isInitialized).toBe(refs1.isInitialized)
    expect(result.current.layoutRestored).toBe(refs1.layoutRestored)
    expect(result.current.ensureCorePanelsRef).toBe(refs1.ensureCorePanelsRef)
  })

  it('syncs config refs on rerender', () => {
    const { result } = renderHook(() => useAppState())

    expect(result.current.panelMinRef.current).toEqual({
      filetree: 150, terminal: 200, shell: 80, center: 180,
    })
    expect(result.current.storagePrefixRef.current).toBe('test-prefix')
    expect(result.current.layoutVersionRef.current).toBe(2)
  })

  it('returns projectRoot from useProjectRoot', () => {
    const { result } = renderHook(() => useAppState())

    expect(result.current.projectRoot).toBe('/test/project')
    expect(result.current.projectRootRef.current).toBe('/test/project')
  })

  it('uses default panelSizes from config when localStorage is empty', () => {
    const { result } = renderHook(() => useAppState())

    expect(result.current.panelSizesRef.current).toEqual({
      filetree: 300, terminal: 450, shell: 200,
    })
  })
})

describe('useAppState with missing config', () => {
  beforeEach(() => {
    vi.mocked(useConfig).mockReturnValue({})
  })

  it('falls back to default values when config is empty', () => {
    const { result } = renderHook(() => useAppState())

    expect(result.current.storagePrefix).toBe('kurt-web')
    expect(result.current.layoutVersion).toBe(1)
    expect(result.current.panelDefaults).toEqual({
      filetree: 280, terminal: 400, shell: 250,
    })
    expect(result.current.panelMin).toEqual({
      filetree: 180, terminal: 250, shell: 100, center: 200,
    })
    expect(result.current.panelCollapsed).toEqual({
      filetree: 48, terminal: 48, shell: 36,
    })
  })
})

describe('useAppState with null capabilities', () => {
  beforeEach(() => {
    vi.mocked(useCapabilities).mockReturnValue({ capabilities: null, loading: true })
  })

  it('returns empty unavailableEssentials when capabilities are null', () => {
    const { result } = renderHook(() => useAppState())

    expect(result.current.capabilities).toBeNull()
    expect(result.current.capabilitiesLoading).toBe(true)
    expect(result.current.unavailableEssentials).toEqual([])
  })
})
