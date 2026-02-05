/**
 * Layout module exports.
 * @module layout
 */

export {
  LAYOUT_VERSION,
  hashProjectRoot,
  getStorageKey,
  getSharedStorageKey,
  SIDEBAR_COLLAPSED_KEY,
  PANEL_SIZES_KEY,
  validateLayoutStructure,
  loadSavedTabs,
  saveTabs,
  loadLayout,
  saveLayout,
  loadCollapsedState,
  saveCollapsedState,
  loadPanelSizes,
  savePanelSizes,
  pruneEmptyGroups,
  checkForSavedLayout,
  getFileName,
  DEFAULT_CONSTRAINTS,
  getDefaultLayoutConfig,
} from './LayoutManager'
