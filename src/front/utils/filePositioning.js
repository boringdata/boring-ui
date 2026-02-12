/**
 * Smart file panel placement logic for Dockview layouts.
 *
 * Extracted from App.jsx to enable reuse across openFile, openFileToSide,
 * and openDiff, and to make the positioning algorithm testable.
 *
 * All functions return Dockview-compatible position objects:
 *   { referenceGroup }
 *   { direction, referenceGroup }
 *   { direction, referencePanel }
 */

/**
 * Finds a group containing a panel whose ID starts with the given prefix.
 *
 * @param {Object} dockApi - Dockview API instance
 * @param {string} prefix - Panel ID prefix to match (e.g. 'editor-', 'review-')
 * @returns {Object|null} The containing group, or null
 */
export function findGroupByPanelPrefix(dockApi, prefix) {
  const allPanels = Array.isArray(dockApi.panels) ? dockApi.panels : []
  const match = allPanels.find((p) => p.id.startsWith(prefix))
  return match?.group ?? null
}

/**
 * Determines the optimal Dockview position for opening a new file panel.
 *
 * Priority order:
 * 1. Existing editor/review group (panel.id starts with 'editor-' or 'review-')
 * 2. Center group reference (for fresh layouts)
 * 3. Group containing 'empty-center' panel
 * 4. Shell group ('shell' panel) — position: above
 * 5. Fallback: right of filetree
 *
 * @param {Object} dockApi - Dockview API instance
 * @param {Object|null} centerGroupRef - React ref whose .current is the center group
 * @returns {Object} Dockview position object
 */
export function findFilePosition(dockApi, centerGroupRef) {
  // 1. Existing editor/review group
  const allPanels = Array.isArray(dockApi.panels) ? dockApi.panels : []
  const editorPanel = allPanels.find(
    (p) => p.id.startsWith('editor-') || p.id.startsWith('review-'),
  )
  if (editorPanel?.group) {
    return { referenceGroup: editorPanel.group }
  }

  // 2. Center group reference
  const centerGroup = centerGroupRef?.current
  if (centerGroup) {
    return { referenceGroup: centerGroup }
  }

  // 3. Empty panel's group
  const emptyPanel = dockApi.getPanel('empty-center')
  if (emptyPanel?.group) {
    return { referenceGroup: emptyPanel.group }
  }

  // 4. Shell group (above)
  const shellPanel = dockApi.getPanel('shell')
  if (shellPanel?.group) {
    return { direction: 'above', referenceGroup: shellPanel.group }
  }

  // 5. Fallback: right of filetree
  return { direction: 'right', referencePanel: 'filetree' }
}

/**
 * Determines the optimal position for opening a file side-by-side.
 *
 * Priority order:
 * 1. Right of active editor panel (if active panel is an editor)
 * 2. Right of center group
 * 3. Right of filetree (fallback)
 *
 * @param {Object} dockApi - Dockview API instance
 * @param {Object|null} centerGroupRef - React ref whose .current is the center group
 * @returns {Object} Dockview position object
 */
export function findSidePosition(dockApi, centerGroupRef) {
  const activePanel = dockApi.activePanel
  if (activePanel && activePanel.id.startsWith('editor-')) {
    return { direction: 'right', referencePanel: activePanel.id }
  }

  const centerGroup = centerGroupRef?.current
  if (centerGroup) {
    return { direction: 'right', referenceGroup: centerGroup }
  }

  return { direction: 'right', referencePanel: 'filetree' }
}

/**
 * Determines the optimal position for opening a diff panel.
 *
 * Diff panels prefer the empty/center slot since they're opened from
 * the git changes view, not from an existing editor tab.
 *
 * Priority order:
 * 1. Empty panel's group
 * 2. Center group reference
 * 3. Shell group (above)
 * 4. Fallback: right of filetree
 *
 * @param {Object} dockApi - Dockview API instance
 * @param {Object|null} centerGroupRef - React ref whose .current is the center group
 * @returns {Object} Dockview position object
 */
export function findDiffPosition(dockApi, centerGroupRef) {
  const emptyPanel = dockApi.getPanel('empty-center')
  if (emptyPanel?.group) {
    return { referenceGroup: emptyPanel.group }
  }

  const centerGroup = centerGroupRef?.current
  if (centerGroup) {
    return { referenceGroup: centerGroup }
  }

  const shellPanel = dockApi.getPanel('shell')
  if (shellPanel?.group) {
    return { direction: 'above', referenceGroup: shellPanel.group }
  }

  return { direction: 'right', referencePanel: 'filetree' }
}
