import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { usePanelParams } from '../../hooks/usePanelParams'

function mockPanel(id) {
  return {
    id,
    api: {
      updateParameters: vi.fn(),
      setActive: vi.fn(),
    },
  }
}

function mockDockApi(panels = {}) {
  return {
    getPanel: vi.fn((id) => panels[id] ?? null),
  }
}

describe('usePanelParams', () => {
  let defaultOpts

  beforeEach(() => {
    vi.clearAllMocks()
    defaultOpts = {
      dockApi: mockDockApi(),
      fileOps: {
        openFile: vi.fn(),
        openFileToSide: vi.fn(),
        openDiff: vi.fn(),
      },
      toggles: {
        filetree: vi.fn(),
        terminal: vi.fn(),
        shell: vi.fn(),
      },
      collapsed: { filetree: false, terminal: false, shell: false },
      projectRoot: '/project',
      activeFile: null,
      activeDiffFile: null,
      approvals: [],
      handleDecision: vi.fn(),
      normalizeApprovalPath: vi.fn(),
    }
  })

  function render(overrides = {}) {
    return renderHook(() => usePanelParams({ ...defaultOpts, ...overrides }))
  }

  it('updates filetree panel parameters', () => {
    const filetreePanel = mockPanel('filetree')
    const dockApi = mockDockApi({ filetree: filetreePanel })
    render({ dockApi })

    expect(filetreePanel.api.updateParameters).toHaveBeenCalledWith({
      onOpenFile: defaultOpts.fileOps.openFile,
      onOpenFileToSide: defaultOpts.fileOps.openFileToSide,
      onOpenDiff: defaultOpts.fileOps.openDiff,
      projectRoot: '/project',
      activeFile: null,
      activeDiffFile: null,
      collapsed: false,
      onToggleCollapse: defaultOpts.toggles.filetree,
    })
  })

  it('updates terminal panel parameters', () => {
    const terminalPanel = mockPanel('terminal')
    const dockApi = mockDockApi({ terminal: terminalPanel })
    render({ dockApi })

    expect(terminalPanel.api.updateParameters).toHaveBeenCalledWith({
      collapsed: false,
      onToggleCollapse: defaultOpts.toggles.terminal,
      approvals: [],
      onFocusReview: expect.any(Function),
      onDecision: defaultOpts.handleDecision,
      normalizeApprovalPath: defaultOpts.normalizeApprovalPath,
    })
  })

  it('updates shell panel parameters', () => {
    const shellPanel = mockPanel('shell')
    const dockApi = mockDockApi({ shell: shellPanel })
    render({ dockApi })

    expect(shellPanel.api.updateParameters).toHaveBeenCalledWith({
      collapsed: false,
      onToggleCollapse: defaultOpts.toggles.shell,
    })
  })

  it('skips updates when dockApi is null', () => {
    render({ dockApi: null })
    // No error, no panel updates
  })

  it('skips updates when panel does not exist', () => {
    const dockApi = mockDockApi({}) // no panels
    render({ dockApi })
    // No error
  })

  it('returns focusReviewPanel function', () => {
    const { result } = render()
    expect(typeof result.current.focusReviewPanel).toBe('function')
  })

  it('focusReviewPanel activates review panel', () => {
    const reviewPanel = mockPanel('review-123')
    const dockApi = mockDockApi({ 'review-123': reviewPanel })
    const { result } = render({ dockApi })

    result.current.focusReviewPanel('123')

    expect(dockApi.getPanel).toHaveBeenCalledWith('review-123')
    expect(reviewPanel.api.setActive).toHaveBeenCalled()
  })

  it('focusReviewPanel handles missing panel', () => {
    const dockApi = mockDockApi({})
    const { result } = render({ dockApi })

    expect(() => result.current.focusReviewPanel('999')).not.toThrow()
  })

  it('focusReviewPanel handles null dockApi', () => {
    const { result } = render({ dockApi: null })

    expect(() => result.current.focusReviewPanel('123')).not.toThrow()
  })

  it('handles null fileOps gracefully', () => {
    const dockApi = mockDockApi({ filetree: mockPanel('filetree') })
    expect(() => render({ dockApi, fileOps: null })).not.toThrow()
  })

  it('handles null toggles gracefully', () => {
    const dockApi = mockDockApi({ shell: mockPanel('shell') })
    expect(() => render({ dockApi, toggles: null })).not.toThrow()
  })
})
