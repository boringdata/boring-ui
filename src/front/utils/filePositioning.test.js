/**
 * Tests for file panel positioning utilities.
 *
 * Covers all priority fallback levels for each positioning function.
 */
import { describe, it, expect, vi } from 'vitest'
import {
  findEditorPosition,
  findSidePosition,
  findDiffPosition,
} from './filePositioning'

// ── Mock factory ──────────────────────────────────────────────────────────

function mockDockApi({ panels = [], activePanel = null, getPanel = {} } = {}) {
  return {
    panels,
    activePanel,
    getPanel: vi.fn((id) => getPanel[id] ?? null),
  }
}

const mockGroup = (id) => ({ id })

// ── findEditorPosition ────────────────────────────────────────────────────

describe('findEditorPosition', () => {
  it('returns existing editor group when editor panel exists', () => {
    const group = mockGroup('editor-group')
    const api = mockDockApi({
      panels: [{ id: 'editor-file.js', group }],
    })

    const result = findEditorPosition(api, null)
    expect(result).toEqual({ referenceGroup: group })
  })

  it('returns existing review group when review panel exists', () => {
    const group = mockGroup('review-group')
    const api = mockDockApi({
      panels: [{ id: 'review-pr123', group }],
    })

    const result = findEditorPosition(api, null)
    expect(result).toEqual({ referenceGroup: group })
  })

  it('falls back to center group when no editor panels', () => {
    const centerGroup = mockGroup('center')
    const api = mockDockApi({ panels: [] })

    const result = findEditorPosition(api, centerGroup)
    expect(result).toEqual({ referenceGroup: centerGroup })
  })

  it('falls back to empty panel group when no center group', () => {
    const group = mockGroup('empty-group')
    const api = mockDockApi({
      panels: [],
      getPanel: { 'empty-center': { group } },
    })

    const result = findEditorPosition(api, null)
    expect(result).toEqual({ referenceGroup: group })
  })

  it('falls back to above shell when no empty panel', () => {
    const group = mockGroup('shell-group')
    const api = mockDockApi({
      panels: [],
      getPanel: { shell: { group } },
    })

    const result = findEditorPosition(api, null)
    expect(result).toEqual({ direction: 'above', referenceGroup: group })
  })

  it('falls back to right of filetree as last resort', () => {
    const api = mockDockApi({ panels: [] })

    const result = findEditorPosition(api, null)
    expect(result).toEqual({ direction: 'right', referencePanel: 'filetree' })
  })

  it('prefers editor panel over center group', () => {
    const editorGroup = mockGroup('editor-group')
    const centerGroup = mockGroup('center')
    const api = mockDockApi({
      panels: [{ id: 'editor-main.jsx', group: editorGroup }],
    })

    const result = findEditorPosition(api, centerGroup)
    expect(result).toEqual({ referenceGroup: editorGroup })
  })
})

// ── findSidePosition ──────────────────────────────────────────────────────

describe('findSidePosition', () => {
  it('returns right of active editor panel', () => {
    const activePanel = { id: 'editor-file.js' }
    const api = mockDockApi({ activePanel })

    const result = findSidePosition(api, null)
    expect(result).toEqual({
      direction: 'right',
      referencePanel: 'editor-file.js',
    })
  })

  it('ignores non-editor active panel', () => {
    const activePanel = { id: 'shell' }
    const centerGroup = mockGroup('center')
    const api = mockDockApi({ activePanel })

    const result = findSidePosition(api, centerGroup)
    expect(result).toEqual({ direction: 'right', referenceGroup: centerGroup })
  })

  it('falls back to center group when no active editor', () => {
    const centerGroup = mockGroup('center')
    const api = mockDockApi()

    const result = findSidePosition(api, centerGroup)
    expect(result).toEqual({ direction: 'right', referenceGroup: centerGroup })
  })

  it('falls back to right of filetree as last resort', () => {
    const api = mockDockApi()

    const result = findSidePosition(api, null)
    expect(result).toEqual({ direction: 'right', referencePanel: 'filetree' })
  })
})

// ── findDiffPosition ──────────────────────────────────────────────────────

describe('findDiffPosition', () => {
  it('returns empty panel group when available', () => {
    const group = mockGroup('empty-group')
    const api = mockDockApi({
      getPanel: { 'empty-center': { group } },
    })

    const result = findDiffPosition(api, null)
    expect(result).toEqual({ referenceGroup: group })
  })

  it('falls back to center group when no empty panel', () => {
    const centerGroup = mockGroup('center')
    const api = mockDockApi()

    const result = findDiffPosition(api, centerGroup)
    expect(result).toEqual({ referenceGroup: centerGroup })
  })

  it('falls back to above shell when no center group', () => {
    const group = mockGroup('shell-group')
    const api = mockDockApi({
      getPanel: { shell: { group } },
    })

    const result = findDiffPosition(api, null)
    expect(result).toEqual({ direction: 'above', referenceGroup: group })
  })

  it('falls back to right of filetree as last resort', () => {
    const api = mockDockApi()

    const result = findDiffPosition(api, null)
    expect(result).toEqual({ direction: 'right', referencePanel: 'filetree' })
  })

  it('prefers empty panel over center group', () => {
    const emptyGroup = mockGroup('empty-group')
    const centerGroup = mockGroup('center')
    const api = mockDockApi({
      getPanel: { 'empty-center': { group: emptyGroup } },
    })

    const result = findDiffPosition(api, centerGroup)
    expect(result).toEqual({ referenceGroup: emptyGroup })
  })
})
