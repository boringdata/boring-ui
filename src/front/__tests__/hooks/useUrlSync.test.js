import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useUrlSync } from '../../hooks/useUrlSync'

describe('useUrlSync', () => {
  let openFile
  let originalLocation

  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
    openFile = vi.fn()
    // Save original search
    originalLocation = window.location.search
  })

  afterEach(() => {
    vi.useRealTimers()
    // Reset URL
    window.history.replaceState({}, '', window.location.pathname)
  })

  function mockDockApi(hasFiletree = true) {
    return {
      getPanel: vi.fn((id) => {
        if (id === 'filetree' && hasFiletree) return { id: 'filetree' }
        return null
      }),
    }
  }

  function render(overrides = {}) {
    const defaults = {
      dockApi: mockDockApi(),
      projectRoot: '/project',
      openFile,
    }
    return renderHook(() => useUrlSync({ ...defaults, ...overrides }))
  }

  it('opens file from doc query param', () => {
    window.history.replaceState({}, '', '?doc=src/app.js')
    render()
    vi.advanceTimersByTime(200)
    expect(openFile).toHaveBeenCalledWith('src/app.js')
  })

  it('does nothing when no doc param', () => {
    window.history.replaceState({}, '', '?other=val')
    render()
    vi.advanceTimersByTime(200)
    expect(openFile).not.toHaveBeenCalled()
  })

  it('does nothing when dockApi is null', () => {
    window.history.replaceState({}, '', '?doc=file.js')
    render({ dockApi: null })
    vi.advanceTimersByTime(200)
    expect(openFile).not.toHaveBeenCalled()
  })

  it('does nothing when projectRoot is null', () => {
    window.history.replaceState({}, '', '?doc=file.js')
    render({ projectRoot: null })
    vi.advanceTimersByTime(200)
    expect(openFile).not.toHaveBeenCalled()
  })

  it('waits for filetree panel to exist', () => {
    window.history.replaceState({}, '', '?doc=file.js')
    const dockApi = mockDockApi(false)
    render({ dockApi })
    vi.advanceTimersByTime(200)
    expect(openFile).not.toHaveBeenCalled()
  })

  it('only restores once', () => {
    window.history.replaceState({}, '', '?doc=src/app.js')
    const dockApi = mockDockApi()
    const { rerender } = render({ dockApi })

    vi.advanceTimersByTime(200)
    expect(openFile).toHaveBeenCalledTimes(1)

    rerender()
    vi.advanceTimersByTime(200)
    expect(openFile).toHaveBeenCalledTimes(1)
  })

  it('delays file open by 150ms', () => {
    window.history.replaceState({}, '', '?doc=src/app.js')
    render()

    vi.advanceTimersByTime(100)
    expect(openFile).not.toHaveBeenCalled()

    vi.advanceTimersByTime(50)
    expect(openFile).toHaveBeenCalledWith('src/app.js')
  })

  it('works with empty string projectRoot', () => {
    window.history.replaceState({}, '', '?doc=file.js')
    render({ projectRoot: '' })
    vi.advanceTimersByTime(200)
    expect(openFile).toHaveBeenCalledWith('file.js')
  })
})
