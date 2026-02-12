import { describe, it, expect, vi } from 'vitest'
import {
  CORE_PANEL_IDS,
  applyLockedPanels,
  ensureCorePanels,
  validateCoreLayout,
  countEmptyGroups,
} from '../../utils/layoutUtils'

/**
 * Creates a mock Dockview API for testing.
 */
function createMockApi({ panels = {}, groups = [] } = {}) {
  const addedPanels = []

  const api = {
    panels: Object.values(panels),
    groups,
    getPanel: (id) => panels[id] ?? null,
    addPanel: vi.fn((config) => {
      const group = mockGroup(`group-${config.id}`)
      const panel = mockPanel(config.id, group)
      panels[config.id] = panel
      api.panels = Object.values(panels)
      addedPanels.push(config)
      return panel
    }),
    _addedPanels: addedPanels,
  }
  return api
}

function mockGroup(id) {
  return {
    id,
    locked: false,
    header: { hidden: false },
    panels: [],
    api: {
      setConstraints: vi.fn(),
      setSize: vi.fn(),
    },
  }
}

function mockPanel(id, group = null) {
  return {
    id,
    group: group || mockGroup(`group-${id}`),
    api: {
      setActive: vi.fn(),
      setLocked: vi.fn(),
      setHidden: vi.fn(),
      close: vi.fn(),
    },
  }
}

const DEFAULT_MINS = { filetree: 150, terminal: 200, shell: 80, center: 100 }

describe('CORE_PANEL_IDS', () => {
  it('contains expected panel IDs', () => {
    expect(CORE_PANEL_IDS).toContain('filetree')
    expect(CORE_PANEL_IDS).toContain('terminal')
    expect(CORE_PANEL_IDS).toContain('empty-center')
    expect(CORE_PANEL_IDS).toContain('shell')
  })
})

describe('applyLockedPanels', () => {
  it('locks and hides filetree group', () => {
    const filetreeGroup = mockGroup('ft-group')
    const api = createMockApi({
      panels: {
        filetree: mockPanel('filetree', filetreeGroup),
        terminal: mockPanel('terminal'),
        shell: mockPanel('shell'),
      },
    })

    applyLockedPanels(api, DEFAULT_MINS)

    expect(filetreeGroup.locked).toBe(true)
    expect(filetreeGroup.header.hidden).toBe(true)
    expect(filetreeGroup.api.setConstraints).toHaveBeenCalledWith({
      minimumWidth: 150,
      maximumWidth: Infinity,
    })
  })

  it('locks and hides terminal group', () => {
    const terminalGroup = mockGroup('term-group')
    const api = createMockApi({
      panels: {
        filetree: mockPanel('filetree'),
        terminal: mockPanel('terminal', terminalGroup),
        shell: mockPanel('shell'),
      },
    })

    applyLockedPanels(api, DEFAULT_MINS)

    expect(terminalGroup.locked).toBe(true)
    expect(terminalGroup.header.hidden).toBe(true)
    expect(terminalGroup.api.setConstraints).toHaveBeenCalledWith({
      minimumWidth: 200,
      maximumWidth: Infinity,
    })
  })

  it('applies height constraint to shell (not locked)', () => {
    const shellGroup = mockGroup('shell-group')
    const api = createMockApi({
      panels: {
        filetree: mockPanel('filetree'),
        terminal: mockPanel('terminal'),
        shell: mockPanel('shell', shellGroup),
      },
    })

    applyLockedPanels(api, DEFAULT_MINS)

    // Shell group should NOT be locked (has collapse button)
    expect(shellGroup.locked).toBe(false)
    expect(shellGroup.api.setConstraints).toHaveBeenCalledWith({
      minimumHeight: 80,
      maximumHeight: Infinity,
    })
  })

  it('handles missing panels gracefully', () => {
    const api = createMockApi({ panels: {} })
    // Should not throw
    expect(() => applyLockedPanels(api, DEFAULT_MINS)).not.toThrow()
  })
})

describe('ensureCorePanels', () => {
  it('creates all missing core panels', () => {
    const api = createMockApi()

    ensureCorePanels(api, DEFAULT_MINS)

    expect(api.addPanel).toHaveBeenCalledTimes(4) // filetree, terminal, empty-center, shell
    const addedIds = api._addedPanels.map((c) => c.id)
    expect(addedIds).toContain('filetree')
    expect(addedIds).toContain('terminal')
    expect(addedIds).toContain('empty-center')
    expect(addedIds).toContain('shell')
  })

  it('does not re-create existing panels', () => {
    const api = createMockApi({
      panels: {
        filetree: mockPanel('filetree'),
        terminal: mockPanel('terminal'),
        'empty-center': mockPanel('empty-center'),
        shell: mockPanel('shell'),
      },
    })

    ensureCorePanels(api, DEFAULT_MINS)

    expect(api.addPanel).not.toHaveBeenCalled()
  })

  it('returns center group', () => {
    const api = createMockApi()
    const centerGroup = ensureCorePanels(api, DEFAULT_MINS)
    expect(centerGroup).not.toBeNull()
  })

  it('prefers editor group as center reference', () => {
    const editorGroup = mockGroup('editor-group')
    const api = createMockApi({
      panels: {
        filetree: mockPanel('filetree'),
        terminal: mockPanel('terminal'),
        'empty-center': mockPanel('empty-center'),
        shell: mockPanel('shell'),
        'editor-foo.js': mockPanel('editor-foo.js', editorGroup),
      },
    })

    const centerGroup = ensureCorePanels(api, DEFAULT_MINS)
    expect(centerGroup).toBe(editorGroup)
  })

  it('creates panels in correct order for layout hierarchy', () => {
    const api = createMockApi()
    ensureCorePanels(api, DEFAULT_MINS)

    const addedIds = api._addedPanels.map((c) => c.id)
    expect(addedIds[0]).toBe('filetree')
    expect(addedIds[1]).toBe('terminal')
    expect(addedIds[2]).toBe('empty-center')
    expect(addedIds[3]).toBe('shell')
  })

  it('positions terminal right of filetree', () => {
    const api = createMockApi()
    ensureCorePanels(api, DEFAULT_MINS)

    const termConfig = api._addedPanels.find((c) => c.id === 'terminal')
    expect(termConfig.position).toEqual({
      direction: 'right',
      referencePanel: 'filetree',
    })
  })

  it('positions empty-center left of terminal', () => {
    const api = createMockApi()
    ensureCorePanels(api, DEFAULT_MINS)

    const emptyConfig = api._addedPanels.find((c) => c.id === 'empty-center')
    expect(emptyConfig.position).toEqual({
      direction: 'left',
      referencePanel: 'terminal',
    })
  })
})

describe('validateCoreLayout', () => {
  it('returns true when all core panels exist', () => {
    const api = createMockApi({
      panels: {
        filetree: mockPanel('filetree'),
        terminal: mockPanel('terminal'),
        shell: mockPanel('shell'),
      },
    })
    expect(validateCoreLayout(api)).toBe(true)
  })

  it('returns false when filetree is missing', () => {
    const api = createMockApi({
      panels: {
        terminal: mockPanel('terminal'),
        shell: mockPanel('shell'),
      },
    })
    expect(validateCoreLayout(api)).toBe(false)
  })

  it('returns false when terminal is missing', () => {
    const api = createMockApi({
      panels: {
        filetree: mockPanel('filetree'),
        shell: mockPanel('shell'),
      },
    })
    expect(validateCoreLayout(api)).toBe(false)
  })

  it('returns false when shell is missing', () => {
    const api = createMockApi({
      panels: {
        filetree: mockPanel('filetree'),
        terminal: mockPanel('terminal'),
      },
    })
    expect(validateCoreLayout(api)).toBe(false)
  })

  it('returns false when all panels missing', () => {
    const api = createMockApi()
    expect(validateCoreLayout(api)).toBe(false)
  })
})

describe('countEmptyGroups', () => {
  it('returns 0 when all groups have panels', () => {
    const api = createMockApi({
      groups: [
        { panels: [mockPanel('a')] },
        { panels: [mockPanel('b')] },
      ],
    })
    expect(countEmptyGroups(api)).toBe(0)
  })

  it('counts groups with no panels', () => {
    const api = createMockApi({
      groups: [
        { panels: [] },
        { panels: [mockPanel('a')] },
        { panels: [] },
      ],
    })
    expect(countEmptyGroups(api)).toBe(2)
  })

  it('returns 0 for empty groups array', () => {
    const api = createMockApi({ groups: [] })
    expect(countEmptyGroups(api)).toBe(0)
  })
})
