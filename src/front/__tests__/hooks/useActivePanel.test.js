import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useActivePanel } from '../../hooks/useActivePanel'

describe('useActivePanel', () => {
  let setActiveFile
  let setActiveDiffFile
  let disposeFn
  let changeHandler

  function mockDockApi() {
    disposeFn = vi.fn()
    return {
      onDidActivePanelChange: vi.fn((handler) => {
        changeHandler = handler
        return { dispose: disposeFn }
      }),
    }
  }

  beforeEach(() => {
    vi.clearAllMocks()
    setActiveFile = vi.fn()
    setActiveDiffFile = vi.fn()
    changeHandler = null
  })

  function render(dockApi) {
    return renderHook(() =>
      useActivePanel({ dockApi, setActiveFile, setActiveDiffFile }),
    )
  }

  it('registers onDidActivePanelChange handler', () => {
    const dockApi = mockDockApi()
    render(dockApi)

    expect(dockApi.onDidActivePanelChange).toHaveBeenCalledWith(
      expect.any(Function),
    )
  })

  it('sets active file for editor panel', () => {
    const dockApi = mockDockApi()
    render(dockApi)

    changeHandler({ id: 'editor-src/app.js' })

    expect(setActiveFile).toHaveBeenCalledWith('src/app.js')
    expect(setActiveDiffFile).toHaveBeenCalledWith('src/app.js')
  })

  it('clears active file for non-editor panel', () => {
    const dockApi = mockDockApi()
    render(dockApi)

    changeHandler({ id: 'filetree' })

    expect(setActiveFile).toHaveBeenCalledWith(null)
    expect(setActiveDiffFile).toHaveBeenCalledWith(null)
  })

  it('clears active file for null panel', () => {
    const dockApi = mockDockApi()
    render(dockApi)

    changeHandler(null)

    expect(setActiveFile).toHaveBeenCalledWith(null)
  })

  it('disposes on unmount', () => {
    const dockApi = mockDockApi()
    const { unmount } = render(dockApi)

    unmount()

    expect(disposeFn).toHaveBeenCalled()
  })

  it('does nothing when dockApi is null', () => {
    render(null)
    // No error, no handler registered
  })

  it('updates URL with doc param for editor panel', () => {
    const replaceStateSpy = vi.spyOn(window.history, 'replaceState')
    const dockApi = mockDockApi()
    render(dockApi)

    changeHandler({ id: 'editor-src/main.js' })

    expect(replaceStateSpy).toHaveBeenCalled()
    const url = new URL(replaceStateSpy.mock.calls[0][2], window.location.origin)
    expect(url.searchParams.get('doc')).toBe('src/main.js')

    replaceStateSpy.mockRestore()
  })

  it('clears doc param for non-editor panel', () => {
    const replaceStateSpy = vi.spyOn(window.history, 'replaceState')
    const dockApi = mockDockApi()
    render(dockApi)

    changeHandler({ id: 'terminal' })

    expect(replaceStateSpy).toHaveBeenCalled()
    const url = new URL(replaceStateSpy.mock.calls[0][2], window.location.origin)
    expect(url.searchParams.has('doc')).toBe(false)

    replaceStateSpy.mockRestore()
  })
})
