import { describe, it, expect } from 'vitest'
import {
  findGroupByPanelPrefix,
  findFilePosition,
  findSidePosition,
  findDiffPosition,
} from '../../utils/filePositioning'

/**
 * Helper: create a mock Dockview API with specified panels.
 * Each panel is { id, group? }.
 */
function mockDockApi({ panels = [], activePanel = null, getPanel = {} } = {}) {
  return {
    panels,
    activePanel,
    getPanel: (id) => getPanel[id] ?? null,
  }
}

function mockGroup(name) {
  return { id: name, _name: name }
}

function mockPanel(id, group = null) {
  return { id, group }
}

describe('findGroupByPanelPrefix', () => {
  it('returns group for matching panel prefix', () => {
    const group = mockGroup('center')
    const api = mockDockApi({
      panels: [mockPanel('editor-foo.js', group), mockPanel('filetree')],
    })
    expect(findGroupByPanelPrefix(api, 'editor-')).toBe(group)
  })

  it('returns null when no panels match', () => {
    const api = mockDockApi({
      panels: [mockPanel('filetree'), mockPanel('shell')],
    })
    expect(findGroupByPanelPrefix(api, 'editor-')).toBeNull()
  })

  it('returns null when panels array is empty', () => {
    const api = mockDockApi({ panels: [] })
    expect(findGroupByPanelPrefix(api, 'editor-')).toBeNull()
  })

  it('handles panels without group property', () => {
    const api = mockDockApi({
      panels: [{ id: 'editor-test', group: undefined }],
    })
    expect(findGroupByPanelPrefix(api, 'editor-')).toBeNull()
  })
})

describe('findFilePosition', () => {
  it('priority 1: uses existing editor group', () => {
    const editorGroup = mockGroup('editor-group')
    const centerGroup = mockGroup('center')
    const api = mockDockApi({
      panels: [mockPanel('editor-foo.js', editorGroup)],
      getPanel: { 'empty-center': mockPanel('empty-center', mockGroup('empty')), shell: mockPanel('shell', mockGroup('shell')) },
    })
    const ref = { current: centerGroup }
    const pos = findFilePosition(api, ref)
    expect(pos).toEqual({ referenceGroup: editorGroup })
  })

  it('priority 1: also matches review- prefix panels', () => {
    const reviewGroup = mockGroup('review-group')
    const api = mockDockApi({
      panels: [mockPanel('review-abc', reviewGroup)],
    })
    const pos = findFilePosition(api, null)
    expect(pos).toEqual({ referenceGroup: reviewGroup })
  })

  it('priority 2: falls back to centerGroupRef', () => {
    const centerGroup = mockGroup('center')
    const api = mockDockApi({
      panels: [mockPanel('filetree')],
      getPanel: {},
    })
    const ref = { current: centerGroup }
    const pos = findFilePosition(api, ref)
    expect(pos).toEqual({ referenceGroup: centerGroup })
  })

  it('priority 3: falls back to empty panel group', () => {
    const emptyGroup = mockGroup('empty-group')
    const api = mockDockApi({
      panels: [mockPanel('filetree')],
      getPanel: { 'empty-center': mockPanel('empty-center', emptyGroup) },
    })
    const pos = findFilePosition(api, { current: null })
    expect(pos).toEqual({ referenceGroup: emptyGroup })
  })

  it('priority 4: falls back to shell group (above)', () => {
    const shellGroup = mockGroup('shell-group')
    const api = mockDockApi({
      panels: [],
      getPanel: { shell: mockPanel('shell', shellGroup) },
    })
    const pos = findFilePosition(api, null)
    expect(pos).toEqual({ direction: 'above', referenceGroup: shellGroup })
  })

  it('priority 5: ultimate fallback is right of filetree', () => {
    const api = mockDockApi({ panels: [], getPanel: {} })
    const pos = findFilePosition(api, null)
    expect(pos).toEqual({ direction: 'right', referencePanel: 'filetree' })
  })

  it('handles null centerGroupRef', () => {
    const api = mockDockApi({ panels: [], getPanel: {} })
    const pos = findFilePosition(api, null)
    expect(pos).toEqual({ direction: 'right', referencePanel: 'filetree' })
  })
})

describe('findSidePosition', () => {
  it('priority 1: splits right of active editor', () => {
    const activePanel = { id: 'editor-main.js' }
    const api = mockDockApi({ activePanel })
    const pos = findSidePosition(api, null)
    expect(pos).toEqual({ direction: 'right', referencePanel: 'editor-main.js' })
  })

  it('ignores non-editor active panel', () => {
    const activePanel = { id: 'filetree' }
    const centerGroup = mockGroup('center')
    const api = mockDockApi({ activePanel })
    const pos = findSidePosition(api, { current: centerGroup })
    expect(pos).toEqual({ direction: 'right', referenceGroup: centerGroup })
  })

  it('priority 2: falls back to center group', () => {
    const centerGroup = mockGroup('center')
    const api = mockDockApi({ activePanel: null })
    const pos = findSidePosition(api, { current: centerGroup })
    expect(pos).toEqual({ direction: 'right', referenceGroup: centerGroup })
  })

  it('priority 3: fallback is right of filetree', () => {
    const api = mockDockApi({ activePanel: null })
    const pos = findSidePosition(api, { current: null })
    expect(pos).toEqual({ direction: 'right', referencePanel: 'filetree' })
  })
})

describe('findDiffPosition', () => {
  it('priority 1: uses empty panel group', () => {
    const emptyGroup = mockGroup('empty-group')
    const centerGroup = mockGroup('center')
    const api = mockDockApi({
      getPanel: { 'empty-center': mockPanel('empty-center', emptyGroup) },
    })
    const pos = findDiffPosition(api, { current: centerGroup })
    expect(pos).toEqual({ referenceGroup: emptyGroup })
  })

  it('priority 2: falls back to centerGroupRef', () => {
    const centerGroup = mockGroup('center')
    const api = mockDockApi({ getPanel: {} })
    const pos = findDiffPosition(api, { current: centerGroup })
    expect(pos).toEqual({ referenceGroup: centerGroup })
  })

  it('priority 3: falls back to shell group (above)', () => {
    const shellGroup = mockGroup('shell-group')
    const api = mockDockApi({
      getPanel: { shell: mockPanel('shell', shellGroup) },
    })
    const pos = findDiffPosition(api, { current: null })
    expect(pos).toEqual({ direction: 'above', referenceGroup: shellGroup })
  })

  it('priority 4: fallback is right of filetree', () => {
    const api = mockDockApi({ getPanel: {} })
    const pos = findDiffPosition(api, null)
    expect(pos).toEqual({ direction: 'right', referencePanel: 'filetree' })
  })
})
