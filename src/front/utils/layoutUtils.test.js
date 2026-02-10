/**
 * Tests for layout initialization utilities.
 */
import { describe, it, expect, vi } from 'vitest'
import {
  CORE_PANEL_IDS,
  applyLockedPanels,
  ensureCorePanels,
  validateCoreLayout,
} from './layoutUtils'

// ── Mock factory ──────────────────────────────────────────────────────────

function mockGroup(id) {
  return {
    id,
    locked: false,
    header: { hidden: false },
    panels: [],
    api: {
      setConstraints: vi.fn(),
    },
  }
}

function mockPanel(id, group) {
  return {
    id,
    group: group || mockGroup(`${id}-group`),
    api: {
      component: id,
      setActive: vi.fn(),
      setLocked: vi.fn(),
      setHidden: vi.fn(),
      group: group || mockGroup(`${id}-group`),
    },
  }
}

function mockDockApi({ panels = {}, allPanels = [] } = {}) {
  const addedPanels = []
  return {
    panels: allPanels,
    getPanel: vi.fn((id) => panels[id] ?? null),
    addPanel: vi.fn((opts) => {
      const group = mockGroup(`${opts.id}-group`)
      const panel = mockPanel(opts.id, group)
      addedPanels.push(panel)
      return panel
    }),
    _addedPanels: addedPanels,
  }
}

const PANEL_MIN = { filetree: 150, terminal: 100, shell: 80, center: 200 }

// ── CORE_PANEL_IDS ───────────────────────────────────────────────────────

describe('CORE_PANEL_IDS', () => {
  it('contains the four core panel IDs', () => {
    expect(CORE_PANEL_IDS).toEqual(['filetree', 'empty-center', 'shell', 'terminal'])
  })
})

// ── applyLockedPanels ────────────────────────────────────────────────────

describe('applyLockedPanels', () => {
  it('locks filetree and terminal groups, hides headers, sets constraints', () => {
    const filetreeGroup = mockGroup('ft')
    const terminalGroup = mockGroup('term')
    const shellGroup = mockGroup('sh')

    const api = mockDockApi({
      panels: {
        filetree: { group: filetreeGroup },
        terminal: { group: terminalGroup },
        shell: { group: shellGroup },
      },
    })

    applyLockedPanels(api, PANEL_MIN)

    expect(filetreeGroup.locked).toBe(true)
    expect(filetreeGroup.header.hidden).toBe(true)
    expect(filetreeGroup.api.setConstraints).toHaveBeenCalledWith({
      minimumWidth: 150,
      maximumWidth: Infinity,
    })

    expect(terminalGroup.locked).toBe(true)
    expect(terminalGroup.header.hidden).toBe(true)
    expect(terminalGroup.api.setConstraints).toHaveBeenCalledWith({
      minimumWidth: 100,
      maximumWidth: Infinity,
    })

    // Shell is NOT locked, header NOT hidden — only height-constrained
    expect(shellGroup.locked).toBe(false)
    expect(shellGroup.header.hidden).toBe(false)
    expect(shellGroup.api.setConstraints).toHaveBeenCalledWith({
      minimumHeight: 80,
      maximumHeight: Infinity,
    })
  })

  it('handles missing panels without crashing', () => {
    const api = mockDockApi({ panels: {} })
    expect(() => applyLockedPanels(api, PANEL_MIN)).not.toThrow()
    expect(api.getPanel).toHaveBeenCalledTimes(3)
  })

  it('works with only some panels present', () => {
    const filetreeGroup = mockGroup('ft')
    const api = mockDockApi({
      panels: { filetree: { group: filetreeGroup } },
    })

    applyLockedPanels(api, PANEL_MIN)
    expect(filetreeGroup.locked).toBe(true)
  })
})

// ── ensureCorePanels ─────────────────────────────────────────────────────

describe('ensureCorePanels', () => {
  it('creates all four core panels when none exist', () => {
    const api = mockDockApi()
    const centerGroup = ensureCorePanels(api, PANEL_MIN)

    expect(api.addPanel).toHaveBeenCalledTimes(4)

    const addedIds = api.addPanel.mock.calls.map((c) => c[0].id)
    expect(addedIds).toEqual(['filetree', 'terminal', 'empty-center', 'shell'])

    expect(centerGroup).not.toBeNull()
  })

  it('skips panels that already exist', () => {
    const filetreeGroup = mockGroup('ft')
    const filetree = mockPanel('filetree', filetreeGroup)
    const terminalGroup = mockGroup('term')
    const terminal = mockPanel('terminal', terminalGroup)

    const api = mockDockApi({
      panels: { filetree, terminal },
    })

    ensureCorePanels(api, PANEL_MIN)

    // Should only create empty-center and shell
    expect(api.addPanel).toHaveBeenCalledTimes(2)
    const addedIds = api.addPanel.mock.calls.map((c) => c[0].id)
    expect(addedIds).toEqual(['empty-center', 'shell'])
  })

  it('positions terminal right of filetree', () => {
    const api = mockDockApi()
    ensureCorePanels(api, PANEL_MIN)

    const terminalCall = api.addPanel.mock.calls.find((c) => c[0].id === 'terminal')
    expect(terminalCall[0].position).toEqual({
      direction: 'right',
      referencePanel: 'filetree',
    })
  })

  it('positions empty-center left of terminal', () => {
    const api = mockDockApi()
    ensureCorePanels(api, PANEL_MIN)

    const emptyCall = api.addPanel.mock.calls.find((c) => c[0].id === 'empty-center')
    expect(emptyCall[0].position).toEqual({
      direction: 'left',
      referencePanel: 'terminal',
    })
  })

  it('positions shell below empty-center group', () => {
    const api = mockDockApi()
    ensureCorePanels(api, PANEL_MIN)

    const shellCall = api.addPanel.mock.calls.find((c) => c[0].id === 'shell')
    expect(shellCall[0].position.direction).toBe('below')
    expect(shellCall[0].position.referenceGroup).toBeDefined()
  })

  it('hides empty-center header and sets center constraints', () => {
    const api = mockDockApi()
    const centerGroup = ensureCorePanels(api, PANEL_MIN)

    // The empty-center panel's group should have header hidden
    const emptyPanel = api._addedPanels.find((p) => p.id === 'empty-center')
    expect(emptyPanel.group.header.hidden).toBe(true)
    expect(emptyPanel.group.api.setConstraints).toHaveBeenCalledWith({
      minimumHeight: 200,
      maximumHeight: Infinity,
    })
  })

  it('locks shell group and shows its header', () => {
    const api = mockDockApi()
    ensureCorePanels(api, PANEL_MIN)

    const shellPanel = api._addedPanels.find((p) => p.id === 'shell')
    expect(shellPanel.group.header.hidden).toBe(false)
    expect(shellPanel.group.locked).toBe(true)
  })

  it('returns editor group as center when editors exist', () => {
    const editorGroup = mockGroup('editor-group')
    const editorPanel = mockPanel('editor-file.js', editorGroup)

    const api = mockDockApi({ allPanels: [editorPanel] })
    const centerGroup = ensureCorePanels(api, PANEL_MIN)

    expect(centerGroup).toBe(editorGroup)
  })

  it('does not create shell if empty-center has no group', () => {
    // Simulate addPanel returning a panel with null group for empty-center
    const api = mockDockApi()
    api.addPanel = vi.fn((opts) => {
      if (opts.id === 'empty-center') return { id: 'empty-center', group: null }
      const group = mockGroup(`${opts.id}-group`)
      return mockPanel(opts.id, group)
    })

    ensureCorePanels(api, PANEL_MIN)

    const shellCall = api.addPanel.mock.calls.find((c) => c[0].id === 'shell')
    expect(shellCall).toBeUndefined()
  })
})

// ── validateCoreLayout ───────────────────────────────────────────────────

describe('validateCoreLayout', () => {
  it('returns true when all core panels exist', () => {
    const api = mockDockApi({
      panels: {
        filetree: mockPanel('filetree'),
        'empty-center': mockPanel('empty-center'),
        shell: mockPanel('shell'),
        terminal: mockPanel('terminal'),
      },
    })

    expect(validateCoreLayout(api)).toBe(true)
  })

  it('returns false when a panel is missing', () => {
    const api = mockDockApi({
      panels: {
        filetree: mockPanel('filetree'),
        shell: mockPanel('shell'),
        terminal: mockPanel('terminal'),
        // missing empty-center
      },
    })

    expect(validateCoreLayout(api)).toBe(false)
  })

  it('returns false when no panels exist', () => {
    const api = mockDockApi()
    expect(validateCoreLayout(api)).toBe(false)
  })

  it('queries getPanel for each core ID', () => {
    const api = mockDockApi({
      panels: {
        filetree: mockPanel('filetree'),
        'empty-center': mockPanel('empty-center'),
        shell: mockPanel('shell'),
        terminal: mockPanel('terminal'),
      },
    })

    validateCoreLayout(api)

    const queriedIds = api.getPanel.mock.calls.map((c) => c[0])
    expect(queriedIds).toEqual(CORE_PANEL_IDS)
  })
})
