/**
 * Panel initialization and constraint helpers for Dockview layouts.
 *
 * Extracted from App.jsx onReady callback to enable reuse and testing.
 * These utilities work with the Dockview API directly.
 */

/**
 * Core panel IDs that define the application structure.
 */
export const CORE_PANEL_IDS = ['filetree', 'terminal', 'empty-center', 'shell']

/**
 * Applies locked state and size constraints to core panels.
 *
 * - filetree: locked, header hidden, width constrained
 * - terminal: locked, header hidden, width constrained
 * - shell: not locked, height constrained (has collapse button)
 *
 * @param {Object} api - Dockview API instance
 * @param {Object} panelMins - Minimum sizes keyed by panel name
 * @param {number} panelMins.filetree - Min width for filetree group
 * @param {number} panelMins.terminal - Min width for terminal group
 * @param {number} panelMins.shell - Min height for shell group
 */
export function applyLockedPanels(api, panelMins) {
  const filetreePanel = api.getPanel('filetree')
  const filetreeGroup = filetreePanel?.group
  if (filetreeGroup) {
    filetreeGroup.locked = true
    filetreeGroup.header.hidden = true
    filetreeGroup.api.setConstraints({
      minimumWidth: panelMins.filetree,
      maximumWidth: Infinity,
    })
  }

  const terminalPanel = api.getPanel('terminal')
  const terminalGroup = terminalPanel?.group
  if (terminalGroup) {
    terminalGroup.locked = true
    terminalGroup.header.hidden = true
    terminalGroup.api.setConstraints({
      minimumWidth: panelMins.terminal,
      maximumWidth: Infinity,
    })
  }

  const shellPanel = api.getPanel('shell')
  const shellGroup = shellPanel?.group
  if (shellGroup) {
    shellGroup.api.setConstraints({
      minimumHeight: panelMins.shell,
      maximumHeight: Infinity,
    })
  }
}

/**
 * Creates the core panel structure for a fresh layout.
 *
 * Layout: [filetree | [empty-center / shell] | terminal]
 *
 * Panels are created in order to establish correct hierarchy:
 * 1. filetree (leftmost)
 * 2. terminal (rightmost)
 * 3. empty-center (center, left of terminal)
 * 4. shell (bottom of center, below empty-center)
 *
 * @param {Object} api - Dockview API instance
 * @param {Object} panelMins - Minimum sizes for constraint application
 * @returns {Object|null} The center group (from empty-center or first editor)
 */
export function ensureCorePanels(api, panelMins) {
  let filetreePanel = api.getPanel('filetree')
  if (!filetreePanel) {
    filetreePanel = api.addPanel({
      id: 'filetree',
      component: 'filetree',
      title: 'Files',
      params: { onOpenFile: () => {} },
    })
  }

  let terminalPanel = api.getPanel('terminal')
  if (!terminalPanel) {
    terminalPanel = api.addPanel({
      id: 'terminal',
      component: 'terminal',
      title: 'Code Sessions',
      position: { direction: 'right', referencePanel: 'filetree' },
    })
  }

  let emptyPanel = api.getPanel('empty-center')
  if (!emptyPanel) {
    emptyPanel = api.addPanel({
      id: 'empty-center',
      component: 'empty',
      title: '',
      position: { direction: 'left', referencePanel: 'terminal' },
    })
  }

  let centerGroup = null
  if (emptyPanel?.group) {
    emptyPanel.group.header.hidden = true
    centerGroup = emptyPanel.group
    emptyPanel.group.api.setConstraints({
      minimumHeight: panelMins.center,
      maximumHeight: Infinity,
    })
  }

  let shellPanel = api.getPanel('shell')
  if (!shellPanel && emptyPanel?.group) {
    shellPanel = api.addPanel({
      id: 'shell',
      component: 'shell',
      tabComponent: 'noClose',
      title: 'Shell',
      position: { direction: 'below', referenceGroup: emptyPanel.group },
      params: {
        collapsed: false,
        onToggleCollapse: () => {},
      },
    })
  }

  if (shellPanel?.group) {
    shellPanel.group.header.hidden = false
    shellPanel.group.locked = true
  }

  // Prefer editor group as center reference if editors exist
  const panels = Array.isArray(api.panels)
    ? api.panels
    : typeof api.getPanels === 'function'
      ? api.getPanels()
      : []
  const editorPanels = panels.filter((p) => p.id.startsWith('editor-'))
  if (editorPanels.length > 0) {
    centerGroup = editorPanels[0].group
  }

  applyLockedPanels(api, panelMins)

  return centerGroup
}

/**
 * Validates that a layout has the expected core panels.
 *
 * @param {Object} api - Dockview API instance
 * @returns {boolean} True if all required core panels exist
 */
export function validateCoreLayout(api) {
  const requiredPanels = ['filetree', 'terminal', 'shell']
  return requiredPanels.every((id) => api.getPanel(id) != null)
}

/**
 * Counts groups that have no panels.
 *
 * @param {Object} api - Dockview API instance
 * @returns {number} Count of empty groups
 */
export function countEmptyGroups(api) {
  const groups = Array.isArray(api.groups) ? api.groups : []
  return groups.filter((g) => {
    const panels = Array.isArray(g.panels) ? g.panels : []
    return panels.length === 0
  }).length
}
