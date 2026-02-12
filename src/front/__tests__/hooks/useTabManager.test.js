import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'

vi.mock('../../layout', () => ({
  loadSavedTabs: vi.fn(() => []),
  saveTabs: vi.fn(),
}))

import { useTabManager } from '../../hooks/useTabManager'
import { loadSavedTabs, saveTabs } from '../../layout'

describe('useTabManager', () => {
  let defaultOpts

  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
    loadSavedTabs.mockReturnValue([])
    defaultOpts = {
      storagePrefix: 'test',
      projectRoot: '/project',
      dockApi: { getPanel: vi.fn() },
      layoutRestored: { current: false },
      isInitialized: { current: true },
      openFile: vi.fn(),
    }
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  function render(overrides = {}) {
    return renderHook(() => useTabManager({ ...defaultOpts, ...overrides }))
  }

  it('returns expected state shape', () => {
    const { result } = render()
    expect(result.current).toHaveProperty('tabs')
    expect(result.current).toHaveProperty('setTabs')
    expect(result.current).toHaveProperty('activeFile')
    expect(result.current).toHaveProperty('setActiveFile')
    expect(result.current).toHaveProperty('activeDiffFile')
    expect(result.current).toHaveProperty('setActiveDiffFile')
    expect(result.current).toHaveProperty('hasRestoredTabs')
  })

  it('initializes with empty state', () => {
    const { result } = render()
    expect(result.current.tabs).toEqual({})
    expect(result.current.activeFile).toBeNull()
    expect(result.current.activeDiffFile).toBeNull()
  })

  it('restores tabs from localStorage', () => {
    loadSavedTabs.mockReturnValue(['src/a.js', 'src/b.js'])
    const openFile = vi.fn()
    render({ openFile })

    expect(loadSavedTabs).toHaveBeenCalledWith('test', '/project')

    vi.advanceTimersByTime(50)

    expect(openFile).toHaveBeenCalledWith('src/a.js')
    expect(openFile).toHaveBeenCalledWith('src/b.js')
  })

  it('skips restoration when layoutRestored is true', () => {
    loadSavedTabs.mockReturnValue(['src/a.js'])
    const openFile = vi.fn()
    render({ openFile, layoutRestored: { current: true } })

    vi.advanceTimersByTime(100)

    expect(openFile).not.toHaveBeenCalled()
  })

  it('skips restoration when dockApi is null', () => {
    loadSavedTabs.mockReturnValue(['src/a.js'])
    const openFile = vi.fn()
    render({ openFile, dockApi: null })

    vi.advanceTimersByTime(100)

    expect(loadSavedTabs).not.toHaveBeenCalled()
    expect(openFile).not.toHaveBeenCalled()
  })

  it('skips restoration when projectRoot is null', () => {
    loadSavedTabs.mockReturnValue(['src/a.js'])
    const openFile = vi.fn()
    render({ openFile, projectRoot: null })

    vi.advanceTimersByTime(100)

    expect(loadSavedTabs).not.toHaveBeenCalled()
  })

  it('does not restore twice', () => {
    loadSavedTabs.mockReturnValue(['src/a.js'])
    const openFile = vi.fn()
    const { rerender } = render({ openFile })

    vi.advanceTimersByTime(50)
    expect(openFile).toHaveBeenCalledTimes(1)

    rerender()
    vi.advanceTimersByTime(50)

    // Still only called once
    expect(openFile).toHaveBeenCalledTimes(1)
  })

  it('persists tabs on change', () => {
    const { result } = render()

    act(() => {
      result.current.setTabs({ 'a.js': { content: 'x', isDirty: false } })
    })

    expect(saveTabs).toHaveBeenCalledWith('test', '/project', ['a.js'])
  })

  it('skips persistence when projectRoot is null', () => {
    const { result } = render({ projectRoot: null })

    act(() => {
      result.current.setTabs({ 'a.js': { content: 'x', isDirty: false } })
    })

    // saveTabs called once for initial empty tabs (but skipped due to null projectRoot)
    expect(saveTabs).not.toHaveBeenCalled()
  })

  it('skips persistence when not initialized', () => {
    const { result } = render({ isInitialized: { current: false } })

    act(() => {
      result.current.setTabs({ 'a.js': { content: 'x', isDirty: false } })
    })

    expect(saveTabs).not.toHaveBeenCalled()
  })

  it('setters update state correctly', () => {
    const { result } = render()

    act(() => {
      result.current.setActiveFile('src/main.js')
    })
    expect(result.current.activeFile).toBe('src/main.js')

    act(() => {
      result.current.setActiveDiffFile('src/diff.js')
    })
    expect(result.current.activeDiffFile).toBe('src/diff.js')
  })

  it('handles empty saved tabs gracefully', () => {
    loadSavedTabs.mockReturnValue([])
    const openFile = vi.fn()
    render({ openFile })

    vi.advanceTimersByTime(100)

    expect(openFile).not.toHaveBeenCalled()
  })

  it('handles missing openFile callback', () => {
    loadSavedTabs.mockReturnValue(['src/a.js'])
    // No openFile provided
    expect(() => render({ openFile: undefined })).not.toThrow()
  })
})
