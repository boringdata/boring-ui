/**
 * Registry module exports.
 * @module registry
 */

export {
  PaneRegistry,
  createDefaultRegistry,
  registerPane,
  getPane,
  listPanes,
  listPaneIds,
  essentialPanes,
  isEssential,
  hasPane,
  getComponents,
  getKnownComponents,
  default as paneRegistry,
} from './panes'
