/**
 * Core application state for the IDE interface.
 *
 * Consolidates all top-level state from App.jsx into a single hook:
 * - Configuration (from useConfig)
 * - Capabilities (from useCapabilities)
 * - Dockview API reference
 * - Collapsed panel states (persisted)
 * - Panel size references (persisted)
 * - Tab state, active file, active diff file
 * - Approvals state
 * - Project root
 * - Stable refs for callbacks
 */

import { useState, useRef } from 'react'
import { useConfig } from '../config'
import { useCapabilities } from './useCapabilities'
import { loadCollapsedState, loadPanelSizes } from '../layout'
import { getUnavailableEssentialPanes } from '../registry/panes'

const DEFAULT_PANEL_DEFAULTS = { filetree: 280, terminal: 400, shell: 250 }
const DEFAULT_PANEL_MIN = { filetree: 180, terminal: 250, shell: 100, center: 200 }
const DEFAULT_PANEL_COLLAPSED = { filetree: 48, terminal: 48, shell: 36 }

export { DEFAULT_PANEL_DEFAULTS, DEFAULT_PANEL_MIN, DEFAULT_PANEL_COLLAPSED }

/**
 * Core application state hook.
 *
 * @returns {Object} All application state values, setters, and refs
 */
export function useAppState() {
  // Config
  const config = useConfig()
  const storagePrefix = config.storage?.prefix || 'kurt-web'
  const layoutVersion = config.storage?.layoutVersion || 1

  const panelDefaults = config.panels?.defaults || DEFAULT_PANEL_DEFAULTS
  const panelMin = config.panels?.min || DEFAULT_PANEL_MIN
  const panelCollapsed = config.panels?.collapsed || DEFAULT_PANEL_COLLAPSED

  // Capabilities
  const { capabilities, loading: capabilitiesLoading } = useCapabilities()
  const unavailableEssentials = capabilities
    ? getUnavailableEssentialPanes(capabilities)
    : []

  // Dockview
  const [dockApi, setDockApi] = useState(null)

  // Tabs and files
  const [tabs, setTabs] = useState({})
  const [activeFile, setActiveFile] = useState(null)
  const [activeDiffFile, setActiveDiffFile] = useState(null)

  // Approvals
  const [approvals, setApprovals] = useState([])
  const [approvalsLoaded, setApprovalsLoaded] = useState(false)

  // Collapsed state (persisted to localStorage)
  const [collapsed, setCollapsed] = useState(() =>
    loadCollapsedState(storagePrefix),
  )
  const panelSizesRef = useRef(
    loadPanelSizes(storagePrefix) || panelDefaults,
  )

  // Project root
  const [projectRoot, setProjectRoot] = useState(null)

  // Stable refs for callbacks
  const projectRootRef = useRef(null)
  const storagePrefixRef = useRef(storagePrefix)
  storagePrefixRef.current = storagePrefix
  const layoutVersionRef = useRef(layoutVersion)
  layoutVersionRef.current = layoutVersion
  const panelCollapsedRef = useRef(panelCollapsed)
  panelCollapsedRef.current = panelCollapsed
  const panelMinRef = useRef(panelMin)
  panelMinRef.current = panelMin
  const collapsedEffectRan = useRef(false)
  const dismissedApprovalsRef = useRef(new Set())
  const centerGroupRef = useRef(null)
  const isInitialized = useRef(false)
  const layoutRestored = useRef(false)
  const ensureCorePanelsRef = useRef(null)

  return {
    // Config
    config,
    storagePrefix,
    layoutVersion,
    panelDefaults,
    panelMin,
    panelCollapsed,

    // Capabilities
    capabilities,
    capabilitiesLoading,
    unavailableEssentials,

    // Dockview
    dockApi,
    setDockApi,

    // Tabs / files
    tabs,
    setTabs,
    activeFile,
    setActiveFile,
    activeDiffFile,
    setActiveDiffFile,

    // Approvals
    approvals,
    setApprovals,
    approvalsLoaded,
    setApprovalsLoaded,

    // Collapsed
    collapsed,
    setCollapsed,
    panelSizesRef,

    // Project
    projectRoot,
    setProjectRoot,

    // Refs
    projectRootRef,
    storagePrefixRef,
    layoutVersionRef,
    panelCollapsedRef,
    panelMinRef,
    collapsedEffectRan,
    dismissedApprovalsRef,
    centerGroupRef,
    isInitialized,
    layoutRestored,
    ensureCorePanelsRef,
  }
}
