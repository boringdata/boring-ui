/**
 * Core application state hook.
 *
 * Bundles config-derived sizing values, core UI state (dockApi, tabs,
 * activeFile, collapsed), and refs that other hooks consume.
 *
 * @module hooks/useAppState
 */

import { useState, useRef } from 'react'
import { useConfig } from '../config'
import { useCapabilities } from './useCapabilities'
import { useProjectRoot } from './useProjectRoot'
import { loadCollapsedState, loadPanelSizes } from '../layout'
import { getUnavailableEssentialPanes } from '../registry/panes'

/** Default panel widths/heights when no saved or configured value exists. */
const DEFAULT_PANEL_DEFAULTS = { filetree: 280, terminal: 400, shell: 250 }
/** Default minimum panel sizes. */
const DEFAULT_PANEL_MIN = { filetree: 180, terminal: 250, shell: 100, center: 200 }
/** Default collapsed-panel thresholds (px). */
const DEFAULT_PANEL_COLLAPSED = { filetree: 48, terminal: 48, shell: 36 }

/**
 * Initializes core application state from config, capabilities, and localStorage.
 *
 * @returns {Object} state bag consumed by App.jsx and downstream hooks
 */
export function useAppState() {
  // ── Config ───────────────────────────────────────────────────────────
  const config = useConfig()
  const storagePrefix = config.storage?.prefix || 'kurt-web'
  const layoutVersion = config.storage?.layoutVersion || 1

  const panelDefaults = config.panels?.defaults || DEFAULT_PANEL_DEFAULTS
  const panelMin = config.panels?.min || DEFAULT_PANEL_MIN
  const panelCollapsed = config.panels?.collapsed || DEFAULT_PANEL_COLLAPSED

  // ── Capabilities ─────────────────────────────────────────────────────
  const { capabilities, loading: capabilitiesLoading } = useCapabilities()
  const unavailableEssentials = capabilities
    ? getUnavailableEssentialPanes(capabilities)
    : []

  // ── Core UI state ────────────────────────────────────────────────────
  const [dockApi, setDockApi] = useState(null)
  const [tabs, setTabs] = useState({})
  const [activeFile, setActiveFile] = useState(null)
  const [activeDiffFile, setActiveDiffFile] = useState(null)
  const [collapsed, setCollapsed] = useState(() =>
    loadCollapsedState(storagePrefix),
  )

  // ── Refs ──────────────────────────────────────────────────────────────
  const panelSizesRef = useRef(
    loadPanelSizes(storagePrefix) || panelDefaults,
  )
  const collapsedEffectRan = useRef(false)
  const centerGroupRef = useRef(null)
  const isInitialized = useRef(false)
  const layoutRestored = useRef(false)
  const ensureCorePanelsRef = useRef(null)

  const storagePrefixRef = useRef(storagePrefix)
  storagePrefixRef.current = storagePrefix
  const layoutVersionRef = useRef(layoutVersion)
  layoutVersionRef.current = layoutVersion

  const panelCollapsedRef = useRef(panelCollapsed)
  panelCollapsedRef.current = panelCollapsed
  const panelMinRef = useRef(panelMin)
  panelMinRef.current = panelMin

  // ── Project root (separate hook) ─────────────────────────────────────
  const { projectRoot, projectRootRef } = useProjectRoot()

  return {
    // Config-derived
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

    // Core state + setters
    dockApi, setDockApi,
    tabs, setTabs,
    activeFile, setActiveFile,
    activeDiffFile, setActiveDiffFile,
    collapsed, setCollapsed,

    // Project
    projectRoot,
    projectRootRef,

    // Refs
    panelSizesRef,
    collapsedEffectRan,
    centerGroupRef,
    isInitialized,
    layoutRestored,
    ensureCorePanelsRef,
    storagePrefixRef,
    layoutVersionRef,
    panelCollapsedRef,
    panelMinRef,
  }
}
