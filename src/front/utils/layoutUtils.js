/**
 * Layout initialization utilities.
 *
 * Extracted from App.jsx onReady callback for clarity and reuse.
 * Handles core panel creation and constraint application.
 */

/** IDs of the four core panels that form the base layout. */
export const CORE_PANEL_IDS = ['filetree', 'empty-center', 'shell', 'terminal']

/**
 * Apply locked state and size constraints to core panels.
 *
 * - filetree: locked, header hidden, width-constrained
 * - terminal: locked, header hidden, width-constrained
 * - shell: width unconstrained, height-constrained (keeps collapse button)
 *
 * @param {Object} api - Dockview API
 * @param {Object} panelMin - Minimum sizes { filetree, terminal, shell }
 */
export function applyLockedPanels(api, panelMin) {
  const filetreeGroup = api.getPanel('filetree')?.group
  if (filetreeGroup) {
    filetreeGroup.locked = true
    filetreeGroup.header.hidden = true
    filetreeGroup.api.setConstraints({
      minimumWidth: panelMin.filetree,
      maximumWidth: Infinity,
    })
  }

  const terminalGroup = api.getPanel('terminal')?.group
  if (terminalGroup) {
    terminalGroup.locked = true
    terminalGroup.header.hidden = true
    terminalGroup.api.setConstraints({
      minimumWidth: panelMin.terminal,
      maximumWidth: Infinity,
    })
  }

  const shellGroup = api.getPanel('shell')?.group
  if (shellGroup) {
    shellGroup.api.setConstraints({
      minimumHeight: panelMin.shell,
      maximumHeight: Infinity,
    })
  }
}

/**
 * Create the core panel structure for a fresh layout.
 *
 * Layout: [filetree | [empty-center / shell] | terminal]
 *
 * Order matters — panels are positioned relative to each other:
 * 1. filetree (first, becomes leftmost)
 * 2. terminal (right of filetree, becomes rightmost)
 * 3. empty-center (left of terminal, creates center column)
 * 4. shell (below empty-center, splits center vertically)
 *
 * @param {Object} api - Dockview API
 * @param {Object} panelMin - Minimum sizes { center }
 * @returns {Object|null} Center group reference
 */
export function ensureCorePanels(api, panelMin) {
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
      minimumHeight: panelMin.center,
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

  // Prefer editor group as center if editors already exist
  const panels = Array.isArray(api.panels)
    ? api.panels
    : typeof api.getPanels === 'function'
      ? api.getPanels()
      : []
  const editorPanel = panels.find((p) => p.id.startsWith('editor-'))
  if (editorPanel?.group) {
    centerGroup = editorPanel.group
  }

  return centerGroup
}

/**
 * Check whether all core panels exist in the layout.
 *
 * @param {Object} api - Dockview API
 * @returns {boolean} True if every core panel is present
 */
export function validateCoreLayout(api) {
  return CORE_PANEL_IDS.every((id) => api.getPanel(id) != null)
}
