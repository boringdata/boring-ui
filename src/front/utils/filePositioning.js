/**
 * File panel positioning utilities.
 *
 * Determines where to place new editor panels in the Dockview layout
 * using a priority-based fallback algorithm.
 */

/**
 * Find the best position for a new editor panel.
 *
 * Priority order:
 * 1. Existing editor/review group (add as sibling tab)
 * 2. Center group ref
 * 3. Empty panel's group
 * 4. Above shell group (maintains center column)
 * 5. Right of filetree (final fallback)
 *
 * @param {Object} dockApi - Dockview API instance
 * @param {Object|null} centerGroup - Center group ref value
 * @returns {Object} Dockview position descriptor
 */
export function findEditorPosition(dockApi, centerGroup) {
  const emptyPanel = dockApi.getPanel('empty-center')
  const shellPanel = dockApi.getPanel('shell')

  const allPanels = Array.isArray(dockApi.panels) ? dockApi.panels : []
  const existingEditorPanel = allPanels.find(
    (p) => p.id.startsWith('editor-') || p.id.startsWith('review-'),
  )

  if (existingEditorPanel?.group) {
    return { referenceGroup: existingEditorPanel.group }
  }
  if (centerGroup) {
    return { referenceGroup: centerGroup }
  }
  if (emptyPanel?.group) {
    return { referenceGroup: emptyPanel.group }
  }
  if (shellPanel?.group) {
    return { direction: 'above', referenceGroup: shellPanel.group }
  }
  return { direction: 'right', referencePanel: 'filetree' }
}

/**
 * Find the best position for a "split to side" editor panel.
 *
 * Priority order:
 * 1. Right of active editor panel
 * 2. Right of center group
 * 3. Right of filetree
 *
 * @param {Object} dockApi - Dockview API instance
 * @param {Object|null} centerGroup - Center group ref value
 * @returns {Object} Dockview position descriptor
 */
export function findSidePosition(dockApi, centerGroup) {
  const activePanel = dockApi.activePanel

  if (activePanel && activePanel.id.startsWith('editor-')) {
    return { direction: 'right', referencePanel: activePanel.id }
  }
  if (centerGroup) {
    return { direction: 'right', referenceGroup: centerGroup }
  }
  return { direction: 'right', referencePanel: 'filetree' }
}

/**
 * Find the best position for a diff view panel.
 *
 * Priority order:
 * 1. Empty panel's group
 * 2. Center group
 * 3. Above shell group
 * 4. Right of filetree
 *
 * @param {Object} dockApi - Dockview API instance
 * @param {Object|null} centerGroup - Center group ref value
 * @returns {Object} Dockview position descriptor
 */
export function findDiffPosition(dockApi, centerGroup) {
  const emptyPanel = dockApi.getPanel('empty-center')
  const shellPanel = dockApi.getPanel('shell')

  if (emptyPanel?.group) {
    return { referenceGroup: emptyPanel.group }
  }
  if (centerGroup) {
    return { referenceGroup: centerGroup }
  }
  if (shellPanel?.group) {
    return { direction: 'above', referenceGroup: shellPanel.group }
  }
  return { direction: 'right', referencePanel: 'filetree' }
}
