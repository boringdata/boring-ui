import { useCallback, useRef, useEffect } from 'react'
import { DockviewReact, DockviewDefaultTab } from 'dockview-react'
import 'dockview-react/dist/styles/dockview.css'
import { ChevronDown, ChevronUp } from 'lucide-react'

import {
  ThemeProvider,
  useKeyboardShortcuts,
  useAppState,
  usePanelToggle,
  useCollapsedEffect,
  useApprovals,
  useBrowserTitle,
  useFileOperations,
  useLayoutInit,
  useLayoutRestore,
  useActivePanel,
  usePanelParams,
  useApprovalPanels,
  useUrlSync,
  useDragDrop,
} from './hooks'
import { useProjectRoot } from './hooks/useProjectRoot'
import { normalizeApprovalPath as normalizeApprovalPathUtil } from './utils/approvalUtils'
import { loadSavedTabs, saveTabs } from './layout'
import { AppHeader } from './components/AppHeader'
import { CapabilityWarning } from './components/CapabilityWarning'
import ClaudeStreamChat from './components/chat/ClaudeStreamChat'
import { CapabilitiesContext, createCapabilityGatedPane } from './components/CapabilityGate'
import {
  getGatedComponents,
  getKnownComponents,
} from './registry/panes'

// POC mode - add ?poc=chat to URL to test
const POC_MODE = new URLSearchParams(window.location.search).get('poc')

// Get capability-gated components from pane registry
const components = getGatedComponents(createCapabilityGatedPane)
const KNOWN_COMPONENTS = getKnownComponents()

// Custom tab component that hides close button (for shell tabs)
const TabWithoutClose = (props) => <DockviewDefaultTab {...props} hideClose />
const tabComponents = { noClose: TabWithoutClose }

export default function App() {
  // ── Core State ──
  const {
    config,
    storagePrefix,
    layoutVersion,
    panelDefaults,
    panelMin,
    panelCollapsed,
    capabilities,
    capabilitiesLoading,
    unavailableEssentials,
    dockApi, setDockApi,
    tabs, setTabs,
    activeFile, setActiveFile,
    activeDiffFile, setActiveDiffFile,
    collapsed, setCollapsed,
    panelSizesRef,
    projectRootRef,
    storagePrefixRef,
    layoutVersionRef,
    panelCollapsedRef,
    panelMinRef,
    collapsedEffectRan,
    centerGroupRef,
    isInitialized,
    layoutRestored,
    ensureCorePanelsRef,
  } = useAppState()

  // ── Project Root ──
  // useProjectRoot manages its own projectRoot state with retry/fallback.
  // We sync it to the ref from useAppState so callbacks can access it.
  const { projectRoot } = useProjectRoot()
  projectRootRef.current = projectRoot

  // ── Panel Toggles ──
  const toggles = usePanelToggle({
    dockApi,
    collapsed,
    setCollapsed,
    panelSizesRef,
    panelCollapsedRef,
    storagePrefixRef,
  })
  const { filetree: toggleFiletree, terminal: toggleTerminal, shell: toggleShell } = toggles

  // Close active tab handler for keyboard shortcut
  const closeTab = useCallback(() => {
    if (!dockApi) return
    const activePanel = dockApi.activePanel
    if (activePanel && activePanel.id.startsWith('editor-')) {
      activePanel.api.close()
    }
  }, [dockApi])

  // Toggle theme handler
  const toggleTheme = useCallback(() => {
    window.dispatchEvent(new CustomEvent('theme-toggle-request'))
  }, [])

  // ── Keyboard Shortcuts ──
  useKeyboardShortcuts({
    toggleFiletree,
    toggleTerminal,
    toggleShell,
    closeTab,
    toggleTheme,
  })

  // ── Collapsed State Effect ──
  useCollapsedEffect({
    dockApi,
    collapsed,
    collapsedEffectRan,
    panelCollapsedRef,
    panelMinRef,
    panelSizesRef,
  })

  // ── Approvals ──
  const {
    approvals,
    approvalsLoaded,
    handleDecision,
  } = useApprovals({ dockApi })

  // Normalize approval path (bound to projectRoot)
  const normalizeApprovalPath = useCallback(
    (approval) => normalizeApprovalPathUtil(approval, projectRoot),
    [projectRoot],
  )

  // ── File Operations ──
  const { openFile, openFileToSide, openDiff, openFileAtPosition } = useFileOperations({
    dockApi,
    setTabs,
    setActiveDiffFile,
    centerGroupRef,
    panelMinRef,
  })

  // ── Approval Panels ──
  useApprovalPanels({
    dockApi,
    approvals,
    approvalsLoaded,
    projectRoot,
    handleDecision,
    openFile,
    normalizeApprovalPath,
    centerGroupRef,
    panelMinRef,
  })

  // ── Right Header Actions ──
  const RightHeaderActions = useCallback(
    (props) => {
      const panels = props.group?.panels || []
      const hasShellPanel = panels.some((p) => p.id === 'shell')
      if (!hasShellPanel) return null

      return (
        <button
          type="button"
          className="tab-collapse-btn"
          onClick={toggleShell}
          title={collapsed.shell ? 'Expand panel' : 'Collapse panel'}
          aria-label={collapsed.shell ? 'Expand panel' : 'Collapse panel'}
        >
          {collapsed.shell ? (
            <ChevronDown size={14} />
          ) : (
            <ChevronUp size={14} />
          )}
        </button>
      )
    },
    [collapsed.shell, toggleShell],
  )

  // ── Layout Init (onReady) ──
  const onReady = useLayoutInit({
    setDockApi,
    setTabs,
    storagePrefix,
    panelMinRef,
    panelCollapsedRef,
    panelSizesRef,
    centerGroupRef,
    isInitialized,
    ensureCorePanelsRef,
    storagePrefixRef,
    projectRootRef,
    layoutVersionRef,
  })

  // ── Browser Title ──
  useBrowserTitle({ projectRoot, config })

  // ── Layout Restore ──
  useLayoutRestore({
    dockApi,
    projectRoot,
    storagePrefix,
    layoutVersion,
    knownComponents: KNOWN_COMPONENTS,
    collapsed,
    panelCollapsedRef,
    panelMinRef,
    panelSizesRef,
    centerGroupRef,
    layoutRestored,
    collapsedEffectRan,
    ensureCorePanelsRef,
    openFile,
    openFileToSide,
    openDiff,
    activeFile,
    activeDiffFile,
    toggleFiletree,
    setTabs,
  })

  // ── Active Panel Tracking ──
  useActivePanel({ dockApi, setActiveFile, setActiveDiffFile })

  // ── Panel Parameter Sync ──
  const { focusReviewPanel } = usePanelParams({
    dockApi,
    fileOps: { openFile, openFileToSide, openDiff },
    toggles: { filetree: toggleFiletree, terminal: toggleTerminal, shell: toggleShell },
    collapsed,
    projectRoot,
    activeFile,
    activeDiffFile,
    approvals,
    handleDecision,
    normalizeApprovalPath,
  })

  // ── Tab Restoration ──
  const hasRestoredTabs = useRef(false)
  useEffect(() => {
    if (!dockApi || projectRoot === null || hasRestoredTabs.current) return
    hasRestoredTabs.current = true
    if (layoutRestored.current) return
    const savedPaths = loadSavedTabs(storagePrefix, projectRoot)
    if (savedPaths.length > 0) {
      setTimeout(() => savedPaths.forEach((path) => openFile(path)), 50)
    }
  }, [dockApi, projectRoot, openFile, storagePrefix, layoutRestored])

  // ── Tab Persistence ──
  useEffect(() => {
    if (!isInitialized.current || projectRoot === null) return
    saveTabs(storagePrefix, projectRoot, Object.keys(tabs))
  }, [tabs, projectRoot, storagePrefix, isInitialized])

  // ── URL Sync ──
  useUrlSync({ dockApi, projectRoot, openFile })

  // ── Drag and Drop ──
  const { showDndOverlay, onDidDrop } = useDragDrop({
    openFileAtPosition,
    centerGroupRef,
  })

  // ── POC Mode ──
  if (POC_MODE === 'chat') {
    return (
      <ThemeProvider>
        <ClaudeStreamChat />
      </ThemeProvider>
    )
  }

  // ── Render ──
  const dockviewClassName = [
    'dockview-theme-abyss',
    collapsed.filetree && 'filetree-is-collapsed',
    collapsed.terminal && 'terminal-is-collapsed',
    collapsed.shell && 'shell-is-collapsed',
  ].filter(Boolean).join(' ')

  return (
    <ThemeProvider>
      <div className="app-container">
        <AppHeader config={config} projectRoot={projectRoot} />
        <CapabilityWarning unavailableEssentials={unavailableEssentials} />
        <CapabilitiesContext.Provider value={capabilities}>
          <div data-testid="dockview" style={{ flex: 1, display: 'flex', minHeight: 0 }}>
            <DockviewReact
              className={dockviewClassName}
              components={components}
              tabComponents={tabComponents}
              rightHeaderActionsComponent={RightHeaderActions}
              onReady={onReady}
              showDndOverlay={showDndOverlay}
              onDidDrop={onDidDrop}
            />
          </div>
        </CapabilitiesContext.Provider>
      </div>
    </ThemeProvider>
  )
}
