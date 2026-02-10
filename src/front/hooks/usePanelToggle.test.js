/**
 * Tests for usePanelToggle hook.
 */
import { describe, it, expect, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { usePanelToggle } from './usePanelToggle'

// Mock createPanelToggle to track calls and return a no-op toggle
const mockToggleFn = vi.fn()
vi.mock('../utils/panelToggleUtils', () => ({
  createPanelToggle: vi.fn(() => mockToggleFn),
}))

import { createPanelToggle } from '../utils/panelToggleUtils'

function createOptions(overrides = {}) {
  return {
    dockApi: { getPanel: vi.fn() },
    collapsed: { filetree: false, terminal: false, shell: false },
    setCollapsed: vi.fn(),
    panelSizesRef: { current: { filetree: 280, terminal: 400, shell: 250 } },
    panelCollapsedRef: { current: { filetree: 48, terminal: 48, shell: 36 } },
    storagePrefixRef: { current: 'test-prefix' },
    ...overrides,
  }
}

describe('usePanelToggle', () => {
  it('returns toggle functions for all three panels', () => {
    const { result } = renderHook(() => usePanelToggle(createOptions()))

    expect(result.current.toggleFiletree).toBeTypeOf('function')
    expect(result.current.toggleTerminal).toBeTypeOf('function')
    expect(result.current.toggleShell).toBeTypeOf('function')
  })

  it('calls createPanelToggle with correct args for filetree', () => {
    const opts = createOptions()
    const { result } = renderHook(() => usePanelToggle(opts))

    act(() => {
      result.current.toggleFiletree()
    })

    expect(createPanelToggle).toHaveBeenCalledWith(
      expect.objectContaining({
        panelId: 'filetree',
        panelKey: 'filetree',
        dimension: 'width',
        dockApi: opts.dockApi,
        isCollapsed: false,
        collapsedThreshold: 48,
        storagePrefix: 'test-prefix',
      }),
    )
  })

  it('calls createPanelToggle with correct args for terminal', () => {
    const opts = createOptions()
    const { result } = renderHook(() => usePanelToggle(opts))

    act(() => {
      result.current.toggleTerminal()
    })

    expect(createPanelToggle).toHaveBeenCalledWith(
      expect.objectContaining({
        panelId: 'terminal',
        panelKey: 'terminal',
        dimension: 'width',
        isCollapsed: false,
        collapsedThreshold: 48,
      }),
    )
  })

  it('calls createPanelToggle with correct args for shell', () => {
    const opts = createOptions()
    const { result } = renderHook(() => usePanelToggle(opts))

    act(() => {
      result.current.toggleShell()
    })

    expect(createPanelToggle).toHaveBeenCalledWith(
      expect.objectContaining({
        panelId: 'shell',
        panelKey: 'shell',
        dimension: 'height',
        isCollapsed: false,
        collapsedThreshold: 36,
      }),
    )
  })

  it('passes isCollapsed true when panel is collapsed', () => {
    const opts = createOptions({
      collapsed: { filetree: true, terminal: false, shell: true },
    })
    const { result } = renderHook(() => usePanelToggle(opts))

    act(() => {
      result.current.toggleFiletree()
    })
    expect(createPanelToggle).toHaveBeenCalledWith(
      expect.objectContaining({ panelId: 'filetree', isCollapsed: true }),
    )

    act(() => {
      result.current.toggleShell()
    })
    expect(createPanelToggle).toHaveBeenCalledWith(
      expect.objectContaining({ panelId: 'shell', isCollapsed: true }),
    )
  })

  it('invokes the returned toggle function', () => {
    const opts = createOptions()
    const { result } = renderHook(() => usePanelToggle(opts))

    act(() => {
      result.current.toggleFiletree()
    })

    expect(mockToggleFn).toHaveBeenCalled()
  })

  it('works with null dockApi', () => {
    const opts = createOptions({ dockApi: null })
    const { result } = renderHook(() => usePanelToggle(opts))

    // Should not throw
    act(() => {
      result.current.toggleFiletree()
    })
    expect(createPanelToggle).toHaveBeenCalledWith(
      expect.objectContaining({ dockApi: null }),
    )
  })
})
