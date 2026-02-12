/**
 * Panel toggle utilities for collapsible sidebar/bottom panels.
 *
 * Extracts the repeated toggle pattern from App.jsx into a reusable helper.
 */

import { savePanelSizes, saveCollapsedState } from '../layout'

/**
 * Create a toggle handler for a collapsible panel.
 *
 * Before collapsing, captures the current panel size so it can be restored
 * when expanding. Persists both panel sizes and collapsed state.
 *
 * @param {Object} options
 * @param {string} options.panelId - Dockview panel ID (e.g. 'filetree')
 * @param {string} options.panelKey - Key in collapsed state (e.g. 'filetree')
 * @param {'width'|'height'} options.dimension - Which dimension to capture
 * @param {Object} options.dockApi - Dockview API instance
 * @param {boolean} options.isCollapsed - Current collapsed state for this panel
 * @param {Function} options.setCollapsed - React state setter for collapsed map
 * @param {Object} options.panelSizesRef - Ref to mutable panel sizes object
 * @param {number} options.collapsedThreshold - Size below which panel is considered collapsed
 * @param {string} options.storagePrefix - Storage key prefix
 * @returns {Function} Toggle callback
 */
export function createPanelToggle({
  panelId,
  panelKey,
  dimension = 'width',
  dockApi,
  isCollapsed,
  setCollapsed,
  panelSizesRef,
  collapsedThreshold,
  storagePrefix,
}) {
  return () => {
    if (!isCollapsed && dockApi) {
      const panel = dockApi.getPanel(panelId)
      const group = panel?.group
      if (group) {
        const currentSize = group.api[dimension]
        if (currentSize > collapsedThreshold) {
          panelSizesRef.current = { ...panelSizesRef.current, [panelKey]: currentSize }
          savePanelSizes(panelSizesRef.current, storagePrefix)
        }
      }
    }
    setCollapsed((prev) => {
      const next = { ...prev, [panelKey]: !prev[panelKey] }
      saveCollapsedState(next, storagePrefix)
      return next
    })
  }
}
