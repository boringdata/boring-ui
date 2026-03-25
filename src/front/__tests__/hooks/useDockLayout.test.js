import { describe, it, expect, vi } from 'vitest'
import { renderHook } from '@testing-library/react'
import useDockLayout from '../../hooks/useDockLayout'

function makeDeps(overrides = {}) {
  return {
    dockApi: null,
    leftSidebarPanelIds: ['filetree', 'data-catalog'],
    collapsed: { filetree: false, agent: false },
    setCollapsed: vi.fn(),
    panelSizesRef: { current: {} },
    storagePrefixRef: { current: 'test' },
    centerGroupRef: { current: null },
    leftSidebarCollapsedWidth: 48,
    panelCollapsedRef: { current: { agent: 48 } },
    saveCollapsedState: vi.fn(),
    savePanelSizes: vi.fn(),
    ...overrides,
  }
}

describe('useDockLayout', () => {
  it('returns all layout helper functions', () => {
    const { result } = renderHook(() => useDockLayout(makeDeps()))
    expect(typeof result.current.getLeftSidebarGroups).toBe('function')
    expect(typeof result.current.getLeftSidebarAnchorPanelId).toBe('function')
    expect(typeof result.current.getLeftSidebarAnchorPosition).toBe('function')
    expect(typeof result.current.isLeftSidebarGroup).toBe('function')
    expect(typeof result.current.findCenterAnchorPanel).toBe('function')
    expect(typeof result.current.getLiveCenterGroup).toBe('function')
    expect(typeof result.current.toggleFiletree).toBe('function')
    expect(typeof result.current.toggleAgent).toBe('function')
  })

  it('getLeftSidebarGroups returns empty for null api', () => {
    const { result } = renderHook(() => useDockLayout(makeDeps()))
    expect(result.current.getLeftSidebarGroups(null)).toEqual([])
  })

  it('getLeftSidebarAnchorPanelId returns filetree as default', () => {
    const { result } = renderHook(() => useDockLayout(makeDeps()))
    expect(result.current.getLeftSidebarAnchorPanelId(null)).toBe('filetree')
  })

  it('isLeftSidebarGroup returns false for null', () => {
    const { result } = renderHook(() => useDockLayout(makeDeps()))
    expect(result.current.isLeftSidebarGroup(null)).toBe(false)
  })

  it('isLeftSidebarGroup returns true for group containing filetree', () => {
    const { result } = renderHook(() => useDockLayout(makeDeps()))
    const mockGroup = { panels: [{ id: 'filetree' }] }
    expect(result.current.isLeftSidebarGroup(mockGroup)).toBe(true)
  })

  it('isLeftSidebarGroup returns false for center group', () => {
    const { result } = renderHook(() => useDockLayout(makeDeps()))
    const mockGroup = { panels: [{ id: 'editor-main.ts' }] }
    expect(result.current.isLeftSidebarGroup(mockGroup)).toBe(false)
  })

  it('findCenterAnchorPanel returns null for null api', () => {
    const { result } = renderHook(() => useDockLayout(makeDeps()))
    expect(result.current.findCenterAnchorPanel(null)).toBeNull()
  })

  it('getLiveCenterGroup returns null for null api', () => {
    const { result } = renderHook(() => useDockLayout(makeDeps()))
    expect(result.current.getLiveCenterGroup(null)).toBeNull()
  })

  it('toggleFiletree calls setCollapsed', () => {
    const setCollapsed = vi.fn()
    const { result } = renderHook(() => useDockLayout(makeDeps({ setCollapsed })))
    result.current.toggleFiletree()
    expect(setCollapsed).toHaveBeenCalled()
  })

  it('toggleAgent calls setCollapsed', () => {
    const setCollapsed = vi.fn()
    const { result } = renderHook(() => useDockLayout(makeDeps({ setCollapsed })))
    result.current.toggleAgent()
    expect(setCollapsed).toHaveBeenCalled()
  })
})
