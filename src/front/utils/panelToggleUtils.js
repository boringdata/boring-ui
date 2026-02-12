/**
 * Utility helpers for panel collapse/expand behavior.
 */

/**
 * Captures the current panel size for a dockview group.
 *
 * @param {Object} dockApi - Dockview API instance.
 * @param {string} groupId - Dockview group id (for example `filetree-group`).
 * @param {'width'|'height'} dimension - Dimension to read from group API.
 * @returns {number|null} Captured size, or null when unavailable/invalid.
 */
export function capturePanelSize(dockApi, groupId, dimension = 'width') {
  if (!dockApi || !groupId) return null

  const group = dockApi.getGroup?.(groupId)
  const value = group?.api?.[dimension]

  if (typeof value !== 'number' || Number.isNaN(value)) {
    return null
  }

  return value
}

/**
 * Creates a toggle callback for a collapsible panel.
 *
 * @param {Object} options - Toggle behavior options.
 * @param {Object} options.dockApi - Dockview API instance.
 * @param {string} options.groupId - Group id for size capture.
 * @param {string} options.panelKey - Key in collapsed state (for example `filetree`).
 * @param {'width'|'height'} [options.dimension='width'] - Dimension to capture.
 * @param {Object<string, boolean>} options.collapsed - Current collapsed state.
 * @param {Function} options.setCollapsed - React state setter.
 * @param {Object} options.panelSizesRef - Mutable ref of panel sizes.
 * @param {number} options.collapsedSize - Collapsed threshold; smaller/equal values are ignored.
 * @param {Function} options.savePanelSizes - Persist sizes callback.
 *
 * @example
 * const toggleFiletree = createPanelToggle({
 *   dockApi,
 *   groupId: 'filetree-group',
 *   panelKey: 'filetree',
 *   dimension: 'width',
 *   collapsed,
 *   setCollapsed,
 *   panelSizesRef,
 *   collapsedSize: 48,
 *   savePanelSizes,
 * })
 */
export function createPanelToggle(options) {
  const {
    dockApi,
    groupId,
    panelKey,
    dimension = 'width',
    collapsed,
    setCollapsed,
    panelSizesRef,
    collapsedSize = 0,
    savePanelSizes,
  } = options || {}

  return () => {
    if (!dockApi || !groupId || !panelKey || typeof setCollapsed !== 'function') {
      return
    }

    if (!collapsed?.[panelKey]) {
      const currentSize = capturePanelSize(dockApi, groupId, dimension)
      if (currentSize !== null && currentSize > collapsedSize && panelSizesRef?.current) {
        panelSizesRef.current = {
          ...panelSizesRef.current,
          [panelKey]: currentSize,
        }
        if (typeof savePanelSizes === 'function') {
          savePanelSizes(panelSizesRef.current)
        }
      }
    }

    setCollapsed((prev) => ({
      ...prev,
      [panelKey]: !prev[panelKey],
    }))
  }
}
