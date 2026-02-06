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
  loadLastKnownGoodLayout,
  clearLastKnownGoodLayout,
  loadCollapsedState,
  saveCollapsedState,
  loadPanelSizes,
  savePanelSizes,
  pruneEmptyGroups,
  checkForSavedLayout,
  getFileName,
  DEFAULT_CONSTRAINTS,
  getDefaultLayoutConfig,
  // Migration support
  registerLayoutMigration,
  migrateLayout,
} from './LayoutManager'
