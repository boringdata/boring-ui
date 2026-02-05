/**
 * Pane Registry - Manages panel component registration for Dockview layout.
 *
 * This module provides a centralized registry for all panel components,
 * allowing new panels to be added without touching core app code.
 *
 * @module registry/panes
 */

import FileTreePanel from '../panels/FileTreePanel'
import EditorPanel from '../panels/EditorPanel'
import TerminalPanel from '../panels/TerminalPanel'
import ShellTerminalPanel from '../panels/ShellTerminalPanel'
import EmptyPanel from '../panels/EmptyPanel'
import ReviewPanel from '../panels/ReviewPanel'

/**
 * @typedef {Object} PaneConfig
 * @property {string} id - Unique identifier for the pane
 * @property {React.ComponentType} component - The React component to render
 * @property {string} title - Default title for the pane
 * @property {string} [icon] - Optional icon name
 * @property {string} [placement] - Default placement ('left', 'center', 'right', 'bottom')
 * @property {boolean} [essential] - If true, pane must exist in layout
 * @property {boolean} [locked] - If true, pane group is locked (no close button)
 * @property {boolean} [hideHeader] - If true, group header is hidden
 * @property {Object} [constraints] - Size constraints { min, max } for width/height
 */

/**
 * Registry for pane components.
 */
class PaneRegistry {
  constructor() {
    /** @type {Map<string, PaneConfig>} */
    this._panes = new Map()
    /** @type {Set<string>} */
    this._essentials = new Set()
  }

  /**
   * Register a new pane.
   * @param {PaneConfig} config - Pane configuration
   */
  register(config) {
    if (!config.id || !config.component) {
      throw new Error('Pane config must have id and component')
    }
    this._panes.set(config.id, config)
    if (config.essential) {
      this._essentials.add(config.id)
    }
  }

  /**
   * Get a pane configuration by ID.
   * @param {string} id - Pane identifier
   * @returns {PaneConfig|undefined}
   */
  get(id) {
    return this._panes.get(id)
  }

  /**
   * Get all registered pane IDs.
   * @returns {string[]}
   */
  listIds() {
    return Array.from(this._panes.keys())
  }

  /**
   * Get all registered pane configurations.
   * @returns {PaneConfig[]}
   */
  list() {
    return Array.from(this._panes.values())
  }

  /**
   * Get IDs of essential panes (must exist in layout).
   * @returns {string[]}
   */
  essentials() {
    return Array.from(this._essentials)
  }

  /**
   * Check if a pane ID is essential.
   * @param {string} id - Pane identifier
   * @returns {boolean}
   */
  isEssential(id) {
    return this._essentials.has(id)
  }

  /**
   * Check if a pane ID is registered.
   * @param {string} id - Pane identifier
   * @returns {boolean}
   */
  has(id) {
    return this._panes.has(id)
  }

  /**
   * Get components object for Dockview (id -> component mapping).
   * @returns {Object<string, React.ComponentType>}
   */
  getComponents() {
    const components = {}
    for (const [id, config] of this._panes) {
      components[id] = config.component
    }
    return components
  }

  /**
   * Get set of known component names for validation.
   * @returns {Set<string>}
   */
  getKnownComponents() {
    return new Set(this._panes.keys())
  }
}

// Create default registry with standard panels
const createDefaultRegistry = () => {
  const registry = new PaneRegistry()

  // File tree - left sidebar
  registry.register({
    id: 'filetree',
    component: FileTreePanel,
    title: 'Files',
    placement: 'left',
    essential: true,
    locked: true,
    hideHeader: true,
    constraints: {
      minWidth: 180,
      collapsedWidth: 48,
    },
  })

  // Editor - center
  registry.register({
    id: 'editor',
    component: EditorPanel,
    title: 'Editor',
    placement: 'center',
    essential: false,
  })

  // Terminal (Claude sessions) - right sidebar
  registry.register({
    id: 'terminal',
    component: TerminalPanel,
    title: 'Code Sessions',
    placement: 'right',
    essential: true,
    locked: true,
    hideHeader: true,
    constraints: {
      minWidth: 250,
      collapsedWidth: 48,
    },
  })

  // Shell - bottom of center column
  registry.register({
    id: 'shell',
    component: ShellTerminalPanel,
    title: 'Shell',
    placement: 'bottom',
    essential: true,
    locked: true,
    hideHeader: false,
    constraints: {
      minHeight: 100,
      collapsedHeight: 36,
    },
  })

  // Empty placeholder - shown when no editors open
  registry.register({
    id: 'empty',
    component: EmptyPanel,
    title: '',
    placement: 'center',
    essential: false,
  })

  // Review panel - for approval requests
  registry.register({
    id: 'review',
    component: ReviewPanel,
    title: 'Review',
    placement: 'center',
    essential: false,
  })

  return registry
}

// Default singleton registry
const defaultRegistry = createDefaultRegistry()

// Export the registry and helper functions
export { PaneRegistry, createDefaultRegistry }

// Default exports for convenience
export default defaultRegistry

// Re-export commonly used functions from default registry
export const registerPane = (config) => defaultRegistry.register(config)
export const getPane = (id) => defaultRegistry.get(id)
export const listPanes = () => defaultRegistry.list()
export const listPaneIds = () => defaultRegistry.listIds()
export const essentialPanes = () => defaultRegistry.essentials()
export const isEssential = (id) => defaultRegistry.isEssential(id)
export const hasPane = (id) => defaultRegistry.has(id)
export const getComponents = () => defaultRegistry.getComponents()
export const getKnownComponents = () => defaultRegistry.getKnownComponents()
