import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useApprovalPanels } from '../../hooks/useApprovalPanels'

function mockPanel(id, group = null) {
  return {
    id,
    group,
    api: {
      close: vi.fn(),
      updateParameters: vi.fn(),
      setTitle: vi.fn(),
      setActive: vi.fn(),
      setConstraints: vi.fn(),
    },
  }
}

function mockGroup(id) {
  return {
    id,
    header: { hidden: false },
    api: { setConstraints: vi.fn() },
  }
}

function mockDockApi(panels = [], panelMap = {}) {
  return {
    panels,
    getPanel: vi.fn((id) => panelMap[id] ?? null),
    addPanel: vi.fn(() => null),
    getPanels: vi.fn(() => panels),
  }
}

describe('useApprovalPanels', () => {
  let defaultOpts

  beforeEach(() => {
    vi.clearAllMocks()
    defaultOpts = {
      dockApi: mockDockApi(),
      approvals: [],
      approvalsLoaded: true,
      projectRoot: '/project',
      handleDecision: vi.fn(),
      openFile: vi.fn(),
      normalizeApprovalPath: vi.fn((a) => a.file_path || ''),
      centerGroupRef: { current: null },
      panelMinRef: { current: { center: 100 } },
    }
  })

  function render(overrides = {}) {
    return renderHook(() =>
      useApprovalPanels({ ...defaultOpts, ...overrides }),
    )
  }

  it('does nothing when dockApi is null', () => {
    expect(() => render({ dockApi: null })).not.toThrow()
  })

  it('does nothing when approvalsLoaded is false', () => {
    const dockApi = mockDockApi()
    render({ dockApi, approvalsLoaded: false })
    expect(dockApi.addPanel).not.toHaveBeenCalled()
  })

  it('closes review panels for dismissed approvals', () => {
    const reviewPanel = mockPanel('review-abc')
    const dockApi = mockDockApi([reviewPanel], { 'review-abc': reviewPanel })

    render({ dockApi, approvals: [] })

    expect(reviewPanel.api.close).toHaveBeenCalled()
  })

  it('does not close non-review panels', () => {
    const editorPanel = mockPanel('editor-file.js')
    const dockApi = mockDockApi([editorPanel])

    render({ dockApi, approvals: [] })

    expect(editorPanel.api.close).not.toHaveBeenCalled()
  })

  it('creates review panel for new approval', () => {
    const dockApi = mockDockApi([], {})

    render({
      dockApi,
      approvals: [{ id: 'req1', file_path: 'src/app.js' }],
    })

    expect(dockApi.addPanel).toHaveBeenCalledWith(
      expect.objectContaining({
        id: 'review-req1',
        component: 'review',
      }),
    )
  })

  it('updates existing review panel params', () => {
    const reviewPanel = mockPanel('review-req1')
    const dockApi = mockDockApi([reviewPanel], { 'review-req1': reviewPanel })

    render({
      dockApi,
      approvals: [{ id: 'req1', file_path: 'src/app.js' }],
    })

    expect(reviewPanel.api.updateParameters).toHaveBeenCalledWith(
      expect.objectContaining({
        request: { id: 'req1', file_path: 'src/app.js' },
      }),
    )
    expect(reviewPanel.api.setTitle).toHaveBeenCalled()
    expect(dockApi.addPanel).not.toHaveBeenCalled()
  })

  it('positions panel relative to editor group', () => {
    const group = mockGroup('center')
    const editorPanel = mockPanel('editor-file.js', group)
    const dockApi = mockDockApi([editorPanel], { 'editor-file.js': editorPanel })

    render({
      dockApi,
      approvals: [{ id: 'req1', file_path: 'src/a.js' }],
    })

    expect(dockApi.addPanel).toHaveBeenCalledWith(
      expect.objectContaining({
        position: { referenceGroup: group },
      }),
    )
  })

  it('positions panel relative to shell when no editor', () => {
    const shellGroup = mockGroup('shell-group')
    const shellPanel = mockPanel('shell', shellGroup)
    const dockApi = mockDockApi([], { shell: shellPanel })

    render({
      dockApi,
      approvals: [{ id: 'req1', file_path: 'src/a.js' }],
    })

    expect(dockApi.addPanel).toHaveBeenCalledWith(
      expect.objectContaining({
        position: { direction: 'above', referenceGroup: shellGroup },
      }),
    )
  })

  it('closes empty panel after creating review', () => {
    const emptyGroup = mockGroup('empty-group')
    const emptyPanel = mockPanel('empty-center', emptyGroup)
    const dockApi = mockDockApi([], { 'empty-center': emptyPanel })

    render({
      dockApi,
      approvals: [{ id: 'req1', file_path: 'src/a.js' }],
    })

    expect(emptyPanel.api.close).toHaveBeenCalled()
  })

  it('sets center group ref and constraints on new panel', () => {
    const newGroup = mockGroup('new-group')
    const newPanel = mockPanel('review-req1', newGroup)
    const dockApi = mockDockApi([], {})
    dockApi.addPanel.mockReturnValue(newPanel)
    const centerGroupRef = { current: null }

    render({
      dockApi,
      approvals: [{ id: 'req1', file_path: 'src/a.js' }],
      centerGroupRef,
    })

    expect(centerGroupRef.current).toBe(newGroup)
    expect(newGroup.header.hidden).toBe(false)
    expect(newGroup.api.setConstraints).toHaveBeenCalledWith({
      minimumHeight: 100,
      maximumHeight: Infinity,
    })
  })

  it('handles multiple approvals', () => {
    const dockApi = mockDockApi([], {})

    render({
      dockApi,
      approvals: [
        { id: 'req1', file_path: 'a.js' },
        { id: 'req2', file_path: 'b.js' },
      ],
    })

    expect(dockApi.addPanel).toHaveBeenCalledTimes(2)
  })

  it('fallback position when no panels exist', () => {
    const dockApi = mockDockApi([], {})

    render({
      dockApi,
      approvals: [{ id: 'req1', file_path: 'src/a.js' }],
    })

    expect(dockApi.addPanel).toHaveBeenCalledWith(
      expect.objectContaining({
        position: { direction: 'right', referencePanel: 'filetree' },
      }),
    )
  })
})
