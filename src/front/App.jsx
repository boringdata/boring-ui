import { useCallback } from 'react'
import { DockviewReact, DockviewDefaultTab } from 'dockview-react'
import 'dockview-react/dist/styles/dockview.css'
import { ChevronDown, ChevronUp } from 'lucide-react'

import {
  ThemeProvider, useKeyboardShortcuts, useBrowserTitle,
  useApprovals, useApprovalPanels, useAppState, usePanelToggle,
  usePanelParams, useCollapsedState, useActivePanel, useDragDrop,
  useUrlSync, useTabManager, useFileOperations,
  useLayoutInit, useLayoutRestore,
} from './hooks'
import {
  normalizeApprovalPath as _normalizeApprovalPath,
  getReviewTitle as _getReviewTitle,
} from './utils/approvalUtils'
import ThemeToggle from './components/ThemeToggle'
import AppHeader from './components/AppHeader'
import CapabilityWarning from './components/CapabilityWarning'
import ClaudeStreamChat from './components/chat/ClaudeStreamChat'
import { CapabilitiesContext, createCapabilityGatedPane } from './components/CapabilityGate'
import {
  getGatedComponents,
} from './registry/panes'

// POC mode - add ?poc=chat, ?poc=diff, or ?poc=tiptap-diff to URL to test
const POC_MODE = new URLSearchParams(window.location.search).get('poc')

// Get capability-gated components from pane registry
// Components with requiresFeatures/requiresRouters will show error states when unavailable
const components = getGatedComponents(createCapabilityGatedPane)

// Custom tab component that hides close button (for shell tabs)
const TabWithoutClose = (props) => <DockviewDefaultTab {...props} hideClose />

const tabComponents = {
  noClose: TabWithoutClose,
}

export default function App() {
  // Core state from useAppState (config, capabilities, UI state, refs)
  const {
    config, storagePrefix, layoutVersion,
    panelMin, panelCollapsed,
    capabilities, unavailableEssentials,
    dockApi, setDockApi,
    tabs, setTabs,
    activeFile, setActiveFile,
    activeDiffFile, setActiveDiffFile,
    collapsed, setCollapsed,
    projectRoot, projectRootRef,
    panelSizesRef, collapsedEffectRan, centerGroupRef,
    isInitialized, layoutRestored, ensureCorePanelsRef,
    storagePrefixRef, layoutVersionRef,
    panelCollapsedRef, panelMinRef,
  } = useAppState()

  // Approval polling and decision handling
  const { approvals, approvalsLoaded, handleDecision } = useApprovals({ dockApi })

  // Panel collapse/expand toggles
  const { toggleFiletree, toggleTerminal, toggleShell } = usePanelToggle({
    dockApi, collapsed, setCollapsed,
    panelSizesRef, panelCollapsedRef, storagePrefixRef,
  })

  // Close active tab handler for keyboard shortcut
  const closeTab = useCallback(() => {
    if (!dockApi) return
    const activePanel = dockApi.activePanel
    // Only close editor tabs (not essential panels like filetree, terminal, shell)
    if (activePanel && activePanel.id.startsWith('editor-')) {
      activePanel.api.close()
    }
  }, [dockApi])

  // Toggle theme handler (dispatches event for ThemeProvider to handle)
  const toggleTheme = useCallback(() => {
    // Dispatch custom event that ThemeProvider listens to
    window.dispatchEvent(new CustomEvent('theme-toggle-request'))
  }, [])

  // Keyboard shortcuts
  useKeyboardShortcuts({
    toggleFiletree,
    toggleTerminal,
    toggleShell,
    closeTab,
    toggleTheme,
  })

  // Right header actions component - shows collapse button on shell group
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
    [collapsed.shell, toggleShell]
  )

  // Apply collapsed state to dockview groups
  useCollapsedState({
    dockApi, collapsed, panelSizesRef, panelMinRef, panelCollapsedRef, collapsedEffectRan,
  })

  // Git status polling removed - not currently used in UI

  const normalizeApprovalPath = useCallback(
    (approval) => _normalizeApprovalPath(approval, projectRoot),
    [projectRoot],
  )

  const getReviewTitle = useCallback(
    (approval) => _getReviewTitle(approval, projectRoot),
    [projectRoot],
  )

  // File opening operations (open, open-to-side, diff, drag-drop positioning)
  const { openFileAtPosition, openFile, openFileToSide, openDiff } = useFileOperations({
    dockApi, setTabs, setActiveDiffFile, centerGroupRef, panelMinRef,
  })

  useApprovalPanels({
    dockApi,
    approvals,
    approvalsLoaded,
    normalizeApprovalPath,
    getReviewTitle,
    handleDecision,
    openFile,
    centerGroupRef,
    panelMinRef,
  })

  // Dockview initialization handler (core panel creation, lifecycle, persistence)
  const { onReady } = useLayoutInit({
    setDockApi, setTabs, storagePrefix,
    panelSizesRef, panelMinRef, panelCollapsedRef,
    centerGroupRef, ensureCorePanelsRef,
    storagePrefixRef, projectRootRef, layoutVersionRef,
    isInitialized,
  })

  // Browser tab title management (extracted hook)
  useBrowserTitle(projectRoot, config.branding)

  // Layout restoration from localStorage (extracted hook)
  useLayoutRestore({
    dockApi, projectRoot, storagePrefix, layoutVersion,
    collapsed, openFile, openFileToSide, openDiff,
    activeFile, activeDiffFile, toggleFiletree, setTabs,
    centerGroupRef, panelSizesRef, panelMinRef, panelCollapsedRef,
    collapsedEffectRan, layoutRestored, ensureCorePanelsRef,
  })

  // Track active panel to highlight in file tree and sync URL
  useActivePanel({ dockApi, setActiveFile, setActiveDiffFile })

  // Keep panel params in sync with current callbacks and state
  usePanelParams({
    dockApi,
    collapsed,
    toggleFiletree,
    toggleTerminal,
    toggleShell,
    openFile,
    openFileToSide,
    openDiff,
    projectRoot,
    activeFile,
    activeDiffFile,
    approvals,
    handleDecision,
    normalizeApprovalPath,
  })

  // Tab save/restore (extracted hook)
  useTabManager({
    dockApi, projectRoot, storagePrefix, tabs, openFile,
    isInitialized, layoutRestored,
  })

  // Restore document from URL query param on load
  useUrlSync({ dockApi, projectRoot, openFile })

  // Drag and drop file handling (extracted hook)
  const { showDndOverlay, onDidDrop } = useDragDrop({ openFileAtPosition, centerGroupRef })

  if (POC_MODE === 'chat') {
    return (
      <ThemeProvider>
        <ClaudeStreamChat />
      </ThemeProvider>
    )
  }

  // Build className with collapsed state flags for CSS targeting
  const dockviewClassName = [
    'dockview-theme-abyss',
    collapsed.filetree && 'filetree-is-collapsed',
    collapsed.terminal && 'terminal-is-collapsed',
    collapsed.shell && 'shell-is-collapsed',
  ].filter(Boolean).join(' ')

  return (
    <ThemeProvider>
      <div className="app-container">
        <AppHeader config={config} projectRoot={projectRoot}>
          <ThemeToggle />
        </AppHeader>
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
