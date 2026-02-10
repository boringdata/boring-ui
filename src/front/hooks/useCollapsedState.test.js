/**
 * Tests for useCollapsedState hook.
 */
import { describe, it, expect, vi } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useCollapsedState } from './useCollapsedState'

const mockApplyPanelSizes = vi.fn()
vi.mock('../utils/layoutUtils', () => ({
  applyPanelSizes: (...args) => mockApplyPanelSizes(...args),
}))

function createOptions(overrides = {}) {
  return {
    dockApi: { getPanel: vi.fn(), getGroup: vi.fn() },
    collapsed: { filetree: false, terminal: false, shell: false },
    panelSizesRef: { current: { filetree: 280, terminal: 400, shell: 250 } },
    panelMinRef: { current: { filetree: 180, terminal: 250, shell: 100 } },
    panelCollapsedRef: { current: { filetree: 48, terminal: 48, shell: 36 } },
    collapsedEffectRan: { current: false },
    ...overrides,
  }
}

describe('useCollapsedState', () => {
  it('skips when dockApi is null', () => {
    const opts = createOptions({ dockApi: null })
    renderHook(() => useCollapsedState(opts))
    expect(mockApplyPanelSizes).not.toHaveBeenCalled()
  })

  it('calls applyPanelSizes with setExpandedSizes=false on first run', () => {
    const opts = createOptions()
    renderHook(() => useCollapsedState(opts))

    expect(mockApplyPanelSizes).toHaveBeenCalledWith(
      opts.dockApi,
      expect.objectContaining({ setExpandedSizes: false }),
    )
  })

  it('sets collapsedEffectRan to true after first run', () => {
    const opts = createOptions()
    renderHook(() => useCollapsedState(opts))
    expect(opts.collapsedEffectRan.current).toBe(true)
  })

  it('calls applyPanelSizes with setExpandedSizes=true on subsequent runs', () => {
    const opts = createOptions({ collapsedEffectRan: { current: true } })
    renderHook(() => useCollapsedState(opts))

    expect(mockApplyPanelSizes).toHaveBeenCalledWith(
      opts.dockApi,
      expect.objectContaining({ setExpandedSizes: true }),
    )
  })

  it('passes collapsed state through to applyPanelSizes', () => {
    const collapsed = { filetree: true, terminal: false, shell: true }
    const opts = createOptions({ collapsed, collapsedEffectRan: { current: true } })
    renderHook(() => useCollapsedState(opts))

    expect(mockApplyPanelSizes).toHaveBeenCalledWith(
      opts.dockApi,
      expect.objectContaining({ collapsed }),
    )
  })

  it('re-runs effect when collapsed changes', () => {
    mockApplyPanelSizes.mockClear()
    const opts = createOptions({ collapsedEffectRan: { current: true } })
    const { rerender } = renderHook(
      (props) => useCollapsedState(props),
      { initialProps: opts },
    )

    expect(mockApplyPanelSizes).toHaveBeenCalledTimes(1)

    const newCollapsed = { filetree: true, terminal: false, shell: false }
    rerender({ ...opts, collapsed: newCollapsed })

    expect(mockApplyPanelSizes).toHaveBeenCalledTimes(2)
    expect(mockApplyPanelSizes).toHaveBeenLastCalledWith(
      opts.dockApi,
      expect.objectContaining({ collapsed: newCollapsed }),
    )
  })
})
