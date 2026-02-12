import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'

vi.mock('../../utils/apiBase', () => ({
  buildApiUrl: vi.fn((path) => path),
}))

vi.mock('../../layout', () => ({
  getFileName: vi.fn((path) => path.split('/').pop()),
}))

import { useFileOperations } from '../../hooks/useFileOperations'

function mockGroup(name) {
  return {
    id: name,
    header: { hidden: false },
    api: { setConstraints: vi.fn() },
  }
}

function mockPanel(id, group = null) {
  return {
    id,
    group: group || mockGroup(`group-${id}`),
    api: {
      setActive: vi.fn(),
      close: vi.fn(),
      updateParameters: vi.fn(),
      setTitle: vi.fn(),
    },
  }
}

function mockDockApi(panelMap = {}, extras = {}) {
  return {
    getPanel: vi.fn((id) => panelMap[id] ?? null),
    addPanel: vi.fn((config) => {
      const group = mockGroup('new-group')
      return { id: config.id, group, api: { setActive: vi.fn() } }
    }),
    panels: extras.panels || [],
    activePanel: extras.activePanel || null,
  }
}

describe('useFileOperations', () => {
  let setTabs
  let setActiveDiffFile
  let centerGroupRef
  let panelMinRef
  let fetchMock

  beforeEach(() => {
    vi.clearAllMocks()
    setTabs = vi.fn()
    setActiveDiffFile = vi.fn()
    centerGroupRef = { current: null }
    panelMinRef = { current: { center: 200 } }
    fetchMock = vi.fn(() =>
      Promise.resolve({
        json: () => Promise.resolve({ content: 'file content' }),
      }),
    )
    global.fetch = fetchMock
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  function renderOps(dockApi, overrides = {}) {
    return renderHook(() =>
      useFileOperations({
        dockApi,
        setTabs,
        setActiveDiffFile,
        centerGroupRef,
        panelMinRef,
        ...overrides,
      }),
    )
  }

  it('returns all four operations', () => {
    const { result } = renderOps(null)
    expect(typeof result.current.openFile).toBe('function')
    expect(typeof result.current.openFileAtPosition).toBe('function')
    expect(typeof result.current.openFileToSide).toBe('function')
    expect(typeof result.current.openDiff).toBe('function')
  })

  describe('openFileAtPosition', () => {
    it('activates existing panel', () => {
      const panel = mockPanel('editor-a.js')
      const dockApi = mockDockApi({ 'editor-a.js': panel })
      const { result } = renderOps(dockApi)

      act(() => {
        result.current.openFileAtPosition('a.js', {})
      })

      expect(panel.api.setActive).toHaveBeenCalled()
      expect(fetchMock).not.toHaveBeenCalled()
    })

    it('updates initialMode on existing panel', () => {
      const panel = mockPanel('editor-a.js')
      const dockApi = mockDockApi({ 'editor-a.js': panel })
      const { result } = renderOps(dockApi)

      act(() => {
        result.current.openFileAtPosition('a.js', {}, { initialMode: 'git-diff' })
      })

      expect(panel.api.updateParameters).toHaveBeenCalledWith({
        initialMode: 'git-diff',
      })
    })

    it('fetches file content and creates panel', async () => {
      const dockApi = mockDockApi({})
      const { result } = renderOps(dockApi)

      await act(async () => {
        result.current.openFileAtPosition('src/app.js', { direction: 'right' })
        await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled())
      })

      expect(fetchMock).toHaveBeenCalledWith(
        '/api/file?path=src%2Fapp.js',
      )
    })

    it('is no-op when dockApi is null', () => {
      const { result } = renderOps(null)

      act(() => {
        result.current.openFileAtPosition('a.js', {})
      })

      expect(fetchMock).not.toHaveBeenCalled()
    })
  })

  describe('openFile', () => {
    it('activates existing editor panel', () => {
      const panel = mockPanel('editor-a.js')
      const dockApi = mockDockApi({ 'editor-a.js': panel })
      const { result } = renderOps(dockApi)

      let returned
      act(() => {
        returned = result.current.openFile('a.js')
      })

      expect(panel.api.setActive).toHaveBeenCalled()
      expect(returned).toBe(true)
    })

    it('returns false when dockApi is null', () => {
      const { result } = renderOps(null)

      let returned
      act(() => {
        returned = result.current.openFile('a.js')
      })

      expect(returned).toBe(false)
    })

    it('uses existing editor group for positioning', () => {
      const editorGroup = mockGroup('editor-group')
      const existingEditor = mockPanel('editor-old.js', editorGroup)
      const dockApi = mockDockApi({}, { panels: [existingEditor] })
      const { result } = renderOps(dockApi)

      act(() => {
        result.current.openFile('new.js')
      })

      // openFileAtPosition should be called with referenceGroup
      expect(fetchMock).toHaveBeenCalled()
    })

    it('falls back to right of filetree when no groups available', () => {
      const dockApi = mockDockApi({}, { panels: [] })
      const { result } = renderOps(dockApi)

      act(() => {
        result.current.openFile('new.js')
      })

      expect(fetchMock).toHaveBeenCalled()
    })
  })

  describe('openFileToSide', () => {
    it('activates existing panel', () => {
      const panel = mockPanel('editor-a.js')
      const dockApi = mockDockApi({ 'editor-a.js': panel })
      const { result } = renderOps(dockApi)

      act(() => {
        result.current.openFileToSide('a.js')
      })

      expect(panel.api.setActive).toHaveBeenCalled()
    })

    it('is no-op when dockApi is null', () => {
      const { result } = renderOps(null)

      act(() => {
        result.current.openFileToSide('a.js')
      })

      expect(fetchMock).not.toHaveBeenCalled()
    })

    it('splits right of active editor', () => {
      const activePanel = { id: 'editor-main.js' }
      const dockApi = mockDockApi({}, { activePanel })
      const { result } = renderOps(dockApi)

      act(() => {
        result.current.openFileToSide('new.js')
      })

      expect(fetchMock).toHaveBeenCalled()
    })
  })

  describe('openDiff', () => {
    it('updates existing panel to diff mode', () => {
      const panel = mockPanel('editor-a.js')
      const dockApi = mockDockApi({ 'editor-a.js': panel })
      const { result } = renderOps(dockApi)

      act(() => {
        result.current.openDiff('a.js')
      })

      expect(panel.api.updateParameters).toHaveBeenCalledWith({
        initialMode: 'git-diff',
      })
      expect(panel.api.setActive).toHaveBeenCalled()
      expect(setActiveDiffFile).toHaveBeenCalledWith('a.js')
    })

    it('opens new panel with diff mode', () => {
      const dockApi = mockDockApi({})
      const { result } = renderOps(dockApi)

      act(() => {
        result.current.openDiff('new.js')
      })

      expect(fetchMock).toHaveBeenCalled()
      expect(setActiveDiffFile).toHaveBeenCalledWith('new.js')
    })

    it('is no-op when dockApi is null', () => {
      const { result } = renderOps(null)

      act(() => {
        result.current.openDiff('a.js')
      })

      expect(fetchMock).not.toHaveBeenCalled()
      expect(setActiveDiffFile).not.toHaveBeenCalled()
    })

    it('uses empty panel group for positioning', () => {
      const emptyGroup = mockGroup('empty-group')
      const dockApi = mockDockApi({
        'empty-center': mockPanel('empty-center', emptyGroup),
      })
      const { result } = renderOps(dockApi)

      act(() => {
        result.current.openDiff('diff.js')
      })

      expect(fetchMock).toHaveBeenCalled()
    })
  })
})
