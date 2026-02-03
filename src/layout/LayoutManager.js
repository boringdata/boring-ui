/**
 * Layout Manager - Handles Dockview layout persistence and restoration.
 *
 * This module extracts layout management logic from App.jsx to provide
 * a cleaner separation of concerns and enable future layout customization.
 *
 * @module layout/LayoutManager
 */

import { essentialPanes } from '../registry/panes'

// Layout version - increment to force layout reset on breaking changes
export const LAYOUT_VERSION = 22

// Default storage key prefix (can be overridden via config)
const DEFAULT_STORAGE_PREFIX = 'boring-ui'

/**
 * Generate a short hash from the project root path for localStorage keys.
 * @param {string} root - Project root path
 * @returns {string} Short hash string
 */
export const hashProjectRoot = (root) => {
  if (!root) return 'default'
  let hash = 0
  for (let i = 0; i < root.length; i++) {
    const char = root.charCodeAt(i)
    hash = ((hash << 5) - hash) + char
    hash = hash & hash // Convert to 32bit integer
  }
  return Math.abs(hash).toString(36)
}

/**
 * Generate storage key for project-specific data.
 * @param {string} prefix - Storage key prefix (from config)
 * @param {string} projectRoot - Project root path
 * @param {string} suffix - Key suffix (e.g., 'layout', 'tabs')
 * @returns {string} Full storage key
 */
export const getStorageKey = (prefix, projectRoot, suffix) =>
  `${prefix || DEFAULT_STORAGE_PREFIX}-${hashProjectRoot(projectRoot)}-${suffix}`

/**
 * Get shared storage key (UI preferences, not project-specific).
 * @param {string} prefix - Storage key prefix (from config)
 * @param {string} suffix - Key suffix
 * @returns {string} Full storage key
 */
export const getSharedStorageKey = (prefix, suffix) =>
  `${prefix || DEFAULT_STORAGE_PREFIX}-${suffix}`

// Legacy keys for backwards compatibility
export const SIDEBAR_COLLAPSED_KEY = `${DEFAULT_STORAGE_PREFIX}-sidebar-collapsed`
export const PANEL_SIZES_KEY = `${DEFAULT_STORAGE_PREFIX}-panel-sizes`

/**
 * Validate layout structure to detect drift from expected configuration.
 * Returns true if layout is valid, false if it has drifted.
 *
 * @param {Object} layout - Layout object from Dockview toJSON()
 * @returns {boolean} True if layout is valid
 */
export const validateLayoutStructure = (layout) => {
  if (!layout?.grid || !layout?.panels) return false

  const essentials = essentialPanes()
  const panels = layout.panels
  const panelIds = Object.keys(panels)

  // Check all essential panels exist
  for (const essentialId of essentials) {
    if (!panelIds.includes(essentialId)) {
      console.warn(`[Layout drift] Missing essential panel: ${essentialId}`)
      return false
    }
  }

  // Extract groups and their panels from the grid structure
  const groups = []
  const extractGroups = (node) => {
    if (!node) return
    if (node.type === 'leaf' && node.data?.views) {
      // This is a group - collect panel IDs
      const groupPanels = node.data.views.map((v) => v.id).filter(Boolean)
      groups.push(groupPanels)
    }
    // Recurse into branches
    if (node.data && Array.isArray(node.data)) {
      node.data.forEach(extractGroups)
    }
  }
  extractGroups(layout.grid.root)

  // Find which group each essential panel is in
  const panelToGroup = {}
  groups.forEach((groupPanels, groupIndex) => {
    groupPanels.forEach((panelId) => {
      panelToGroup[panelId] = groupIndex
    })
  })

  // Validate filetree is alone in its group (except for non-essential panels)
  const filetreeGroup = groups[panelToGroup['filetree']]
  if (filetreeGroup) {
    const otherInGroup = filetreeGroup.filter((p) => p !== 'filetree')
    const invalidInGroup = otherInGroup.some((p) => essentials.includes(p))
    if (invalidInGroup) {
      console.warn('[Layout drift] filetree group has invalid panels:', otherInGroup)
      return false
    }
  }

  // Validate terminal is alone in its group (except for non-essential panels)
  const terminalGroup = groups[panelToGroup['terminal']]
  if (terminalGroup) {
    const otherInGroup = terminalGroup.filter((p) => p !== 'terminal')
    const invalidInGroup = otherInGroup.some((p) => essentials.includes(p))
    if (invalidInGroup) {
      console.warn('[Layout drift] terminal group has invalid panels:', otherInGroup)
      return false
    }
  }

  // Validate shell is not mixed with filetree or terminal
  const shellGroupIdx = panelToGroup['shell']
  if (shellGroupIdx !== undefined) {
    const shellGroup = groups[shellGroupIdx]
    if (shellGroup.includes('filetree') || shellGroup.includes('terminal')) {
      console.warn('[Layout drift] shell is in wrong group with filetree/terminal')
      return false
    }
  }

  return true
}

/**
 * Load saved tabs from localStorage.
 * @param {string} prefix - Storage key prefix (from config)
 * @param {string} projectRoot - Project root path
 * @returns {string[]} Array of file paths
 */
export const loadSavedTabs = (prefix, projectRoot) => {
  try {
    const saved = localStorage.getItem(getStorageKey(prefix, projectRoot, 'tabs'))
    if (saved) {
      return JSON.parse(saved)
    }
  } catch {
    // Ignore parse errors
  }
  return []
}

/**
 * Save open tabs to localStorage.
 * @param {string} prefix - Storage key prefix (from config)
 * @param {string} projectRoot - Project root path
 * @param {string[]} paths - Array of file paths
 */
export const saveTabs = (prefix, projectRoot, paths) => {
  try {
    localStorage.setItem(getStorageKey(prefix, projectRoot, 'tabs'), JSON.stringify(paths))
  } catch {
    // Ignore storage errors
  }
}

/**
 * Load layout from localStorage.
 * Returns null if layout is invalid, outdated, or missing.
 *
 * @param {string} prefix - Storage key prefix (from config)
 * @param {string} projectRoot - Project root path
 * @param {Set<string>} [knownComponents] - Optional set of known component names
 * @returns {Object|null} Layout object or null
 */
export const loadLayout = (prefix, projectRoot, knownComponents) => {
  try {
    const raw = localStorage.getItem(getStorageKey(prefix, projectRoot, 'layout'))
    if (!raw) return null
    const parsed = JSON.parse(raw)

    // Check layout version - force reset if outdated
    if (!parsed?.version || parsed.version < LAYOUT_VERSION) {
      console.info('[Layout] Version outdated, resetting layout')
      localStorage.removeItem(getStorageKey(prefix, projectRoot, 'layout'))
      return null
    }

    // Check for unknown components if knownComponents provided
    if (knownComponents && parsed?.panels && typeof parsed.panels === 'object') {
      const panels = Object.values(parsed.panels)
      const hasUnknown = panels.some(
        (panel) =>
          panel?.contentComponent &&
          !knownComponents.has(panel.contentComponent),
      )
      if (hasUnknown) {
        console.info('[Layout] Unknown components found, resetting layout')
        localStorage.removeItem(getStorageKey(prefix, projectRoot, 'layout'))
        return null
      }
    }

    // Validate layout structure to detect drift
    if (!validateLayoutStructure(parsed)) {
      console.info('[Layout] Structure drift detected, resetting layout')
      localStorage.removeItem(getStorageKey(prefix, projectRoot, 'layout'))
      return null
    }

    return parsed
  } catch {
    return null
  }
}

/**
 * Save layout to localStorage.
 * @param {string} prefix - Storage key prefix (from config)
 * @param {string} projectRoot - Project root path
 * @param {Object} layout - Layout object from Dockview toJSON()
 */
export const saveLayout = (prefix, projectRoot, layout) => {
  try {
    const layoutWithVersion = { ...layout, version: LAYOUT_VERSION }
    localStorage.setItem(getStorageKey(prefix, projectRoot, 'layout'), JSON.stringify(layoutWithVersion))
  } catch {
    // Ignore storage errors
  }
}

/**
 * Load collapsed state from localStorage.
 * @param {string} [prefix] - Storage key prefix (from config)
 * @returns {Object} Collapsed state { filetree: boolean, terminal: boolean, shell: boolean }
 */
export const loadCollapsedState = (prefix) => {
  const key = prefix
    ? getSharedStorageKey(prefix, 'sidebar-collapsed')
    : SIDEBAR_COLLAPSED_KEY
  try {
    const saved = localStorage.getItem(key)
    if (saved) {
      return JSON.parse(saved)
    }
  } catch {
    // Ignore parse errors
  }
  return { filetree: false, terminal: false, shell: false }
}

/**
 * Save collapsed state to localStorage.
 * @param {Object} state - Collapsed state
 * @param {string} [prefix] - Storage key prefix (from config)
 */
export const saveCollapsedState = (state, prefix) => {
  const key = prefix
    ? getSharedStorageKey(prefix, 'sidebar-collapsed')
    : SIDEBAR_COLLAPSED_KEY
  try {
    localStorage.setItem(key, JSON.stringify(state))
  } catch {
    // Ignore storage errors
  }
}

/**
 * Load panel sizes from localStorage.
 * @param {string} [prefix] - Storage key prefix (from config)
 * @returns {Object} Panel sizes { filetree: number, terminal: number, shell: number }
 */
export const loadPanelSizes = (prefix) => {
  const key = prefix
    ? getSharedStorageKey(prefix, 'panel-sizes')
    : PANEL_SIZES_KEY
  try {
    const saved = localStorage.getItem(key)
    if (saved) {
      return JSON.parse(saved)
    }
  } catch {
    // Ignore parse errors
  }
  return { filetree: 280, terminal: 400, shell: 250 }
}

/**
 * Save panel sizes to localStorage.
 * @param {Object} sizes - Panel sizes
 * @param {string} [prefix] - Storage key prefix (from config)
 */
export const savePanelSizes = (sizes, prefix) => {
  const key = prefix
    ? getSharedStorageKey(prefix, 'panel-sizes')
    : PANEL_SIZES_KEY
  try {
    localStorage.setItem(key, JSON.stringify(sizes))
  } catch {
    // Ignore storage errors
  }
}

/**
 * Prune empty groups from Dockview layout.
 * @param {Object} api - Dockview API
 * @param {Set<string>} knownComponents - Set of known component names
 * @returns {boolean} True if any groups were removed
 */
export const pruneEmptyGroups = (api, knownComponents) => {
  if (!api || !Array.isArray(api.groups)) return false
  const groups = [...api.groups]
  let removed = false

  groups.forEach((group) => {
    const panels = Array.isArray(group?.panels) ? group.panels : []
    if (panels.length === 0) {
      api.removeGroup(group)
      removed = true
      return
    }
    const hasKnownPanel = panels.some((panel) =>
      knownComponents.has(panel?.api?.component),
    )
    if (!hasKnownPanel) {
      api.removeGroup(group)
      removed = true
    }
  })

  return removed
}

/**
 * Check if a saved layout exists in localStorage for a given prefix.
 * Used to determine if onReady should create panels or wait for layout restoration.
 *
 * @param {string} prefix - Storage key prefix (from config)
 * @returns {{ hasSaved: boolean, invalidFound: boolean }}
 */
export const checkForSavedLayout = (prefix) => {
  const storagePrefix = prefix || DEFAULT_STORAGE_PREFIX
  let hasSavedLayout = false
  let invalidLayoutFound = false

  try {
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)
      if (key && key.startsWith(`${storagePrefix}-`) && key.endsWith('-layout')) {
        const raw = localStorage.getItem(key)
        if (raw) {
          const parsed = JSON.parse(raw)
          const hasValidVersion = parsed?.version >= LAYOUT_VERSION
          const hasPanels = !!parsed?.panels
          const hasValidStructure = validateLayoutStructure(parsed)

          // Check if layout is valid
          if (hasValidVersion && hasPanels && hasValidStructure) {
            hasSavedLayout = true
            break
          }

          // Invalid layout detected - clean up
          if (!hasValidStructure || !hasValidVersion || !hasPanels) {
            console.warn('[Layout] Invalid layout detected, clearing:', key)
            localStorage.removeItem(key)
            // Clear related session storage
            const keyPrefix = key.replace('-layout', '')
            localStorage.removeItem(`${keyPrefix}-tabs`)
            localStorage.removeItem(`${storagePrefix}-terminal-sessions`)
            localStorage.removeItem(`${storagePrefix}-terminal-active`)
            localStorage.removeItem(`${storagePrefix}-terminal-chat-interface`)
            invalidLayoutFound = true
          }
        }
      }
    }
  } catch {
    // Ignore errors checking localStorage
  }

  return { hasSaved: hasSavedLayout, invalidFound: invalidLayoutFound }
}

/**
 * Get file name from path.
 * @param {string} path - File path
 * @returns {string} File name
 */
export const getFileName = (path) => {
  const parts = path.split('/')
  return parts[parts.length - 1]
}

/**
 * Default panel constraints for each panel type.
 */
export const DEFAULT_CONSTRAINTS = {
  filetree: { minimumWidth: 180, collapsedWidth: 48 },
  terminal: { minimumWidth: 250, collapsedWidth: 48 },
  shell: { minimumHeight: 100, collapsedHeight: 36 },
  center: { minimumHeight: 200 },
}

/**
 * Create the default layout configuration.
 * Layout goal: [filetree | [editor / shell] | terminal]
 *
 * @returns {Object} Default layout configuration
 */
export const getDefaultLayoutConfig = () => ({
  filetree: {
    position: null, // First panel, no position needed
    title: 'Files',
    locked: true,
    hideHeader: true,
  },
  terminal: {
    position: { direction: 'right', referencePanel: 'filetree' },
    title: 'Code Sessions',
    locked: true,
    hideHeader: true,
  },
  empty: {
    position: { direction: 'left', referencePanel: 'terminal' },
    title: '',
    hideHeader: true,
  },
  shell: {
    position: { direction: 'below', referenceGroup: 'empty' },
    title: 'Shell',
    locked: true,
    hideHeader: false,
    tabComponent: 'noClose',
  },
})
