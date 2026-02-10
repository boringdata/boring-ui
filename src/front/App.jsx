import { useState, useEffect, useCallback, useRef } from 'react'
import { DockviewReact, DockviewDefaultTab } from 'dockview-react'
import 'dockview-react/dist/styles/dockview.css'
import { ChevronDown, ChevronUp } from 'lucide-react'

import { ThemeProvider, useCapabilities, useKeyboardShortcuts, useProjectRoot, useBrowserTitle, useApprovals } from './hooks'
import { useConfig } from './config'
import { buildApiUrl } from './utils/apiBase'
import { createPanelToggle } from './utils/panelToggleUtils'
import {
  normalizeApprovalPath as _normalizeApprovalPath,
  getReviewTitle as _getReviewTitle,
} from './utils/approvalUtils'
import { findEditorPosition, findSidePosition, findDiffPosition } from './utils/filePositioning'
import { applyLockedPanels as applyLockedPanelsUtil, ensureCorePanels as ensureCorePanelsUtil } from './utils/layoutUtils'
import {
  LAYOUT_VERSION,
  validateLayoutStructure,
  loadSavedTabs,
  saveTabs,
  loadLayout,
  saveLayout,
  loadCollapsedState,
  loadPanelSizes,
  savePanelSizes,
  pruneEmptyGroups,
  checkForSavedLayout,
  getFileName,
} from './layout'
import ThemeToggle from './components/ThemeToggle'
import ClaudeStreamChat from './components/chat/ClaudeStreamChat'
import { CapabilitiesContext, createCapabilityGatedPane } from './components/CapabilityGate'
import {
  getGatedComponents,
  getKnownComponents,
  essentialPanes,
  checkRequirements,
  getUnavailableEssentialPanes,
} from './registry/panes'

// POC mode - add ?poc=chat, ?poc=diff, or ?poc=tiptap-diff to URL to test
const POC_MODE = new URLSearchParams(window.location.search).get('poc')

// Debounce helper - delays function execution until after wait ms of inactivity
const debounce = (fn, wait) => {
  let timeoutId = null
  const debounced = (...args) => {
    if (timeoutId) clearTimeout(timeoutId)
    timeoutId = setTimeout(() => {
      timeoutId = null
      fn(...args)
    }, wait)
  }
  // Allow immediate flush (for beforeunload)
  debounced.flush = () => {
    if (timeoutId) {
      clearTimeout(timeoutId)
      timeoutId = null
      fn()
    }
  }
  debounced.cancel = () => {
    if (timeoutId) {
      clearTimeout(timeoutId)
      timeoutId = null
    }
  }
  return debounced
}

// Get capability-gated components from pane registry
// Components with requiresFeatures/requiresRouters will show error states when unavailable
const components = getGatedComponents(createCapabilityGatedPane)
const KNOWN_COMPONENTS = getKnownComponents()

// Get essential panel IDs from pane registry
const ESSENTIAL_PANELS = essentialPanes()

// Custom tab component that hides close button (for shell tabs)
const TabWithoutClose = (props) => <DockviewDefaultTab {...props} hideClose />

const tabComponents = {
  noClose: TabWithoutClose,
}

export default function App() {
  // Get config (defaults are used until async load completes)
  const config = useConfig()
  const storagePrefix = config.storage?.prefix || 'kurt-web'
  const layoutVersion = config.storage?.layoutVersion || 1

  // Panel sizing configuration from config
  const panelDefaults = config.panels?.defaults || { filetree: 280, terminal: 400, shell: 250 }
  const panelMin = config.panels?.min || { filetree: 180, terminal: 250, shell: 100, center: 200 }
  const panelCollapsed = config.panels?.collapsed || { filetree: 48, terminal: 48, shell: 36 }

  // Fetch backend capabilities for feature gating
  const { capabilities, loading: capabilitiesLoading } = useCapabilities()

  // Check for unavailable essential panes
  const unavailableEssentials = capabilities
    ? getUnavailableEssentialPanes(capabilities)
    : []

  const [dockApi, setDockApi] = useState(null)
  const [tabs, setTabs] = useState({}) // path -> { content, isDirty }
  const [activeFile, setActiveFile] = useState(null)
  const [activeDiffFile, setActiveDiffFile] = useState(null)
  const [collapsed, setCollapsed] = useState(() =>
    loadCollapsedState(storagePrefix)
  )
  const panelSizesRef = useRef(
    loadPanelSizes(storagePrefix) || panelDefaults
  )
  const collapsedEffectRan = useRef(false)
  const centerGroupRef = useRef(null)
  const isInitialized = useRef(false)
  const layoutRestored = useRef(false)
  const ensureCorePanelsRef = useRef(null)
  const { projectRoot, projectRootRef } = useProjectRoot()
  const storagePrefixRef = useRef(storagePrefix) // Stable ref for callbacks
  storagePrefixRef.current = storagePrefix
  const layoutVersionRef = useRef(layoutVersion) // Stable ref for callbacks
  layoutVersionRef.current = layoutVersion

  // Refs for panel config (used in callbacks)
  const panelCollapsedRef = useRef(panelCollapsed)
  panelCollapsedRef.current = panelCollapsed
  const panelMinRef = useRef(panelMin)
  panelMinRef.current = panelMin

  // Approval polling and decision handling
  const { approvals, approvalsLoaded, handleDecision } = useApprovals({ dockApi })

  // Toggle sidebar/panel collapse - uses extracted utility
  const toggleFiletree = useCallback(
    () => createPanelToggle({
      panelId: 'filetree', panelKey: 'filetree', dimension: 'width',
      dockApi, isCollapsed: collapsed.filetree, setCollapsed,
      panelSizesRef, collapsedThreshold: panelCollapsedRef.current.filetree,
      storagePrefix: storagePrefixRef.current,
    })(),
    [collapsed.filetree, dockApi],
  )

  const toggleTerminal = useCallback(
    () => createPanelToggle({
      panelId: 'terminal', panelKey: 'terminal', dimension: 'width',
      dockApi, isCollapsed: collapsed.terminal, setCollapsed,
      panelSizesRef, collapsedThreshold: panelCollapsedRef.current.terminal,
      storagePrefix: storagePrefixRef.current,
    })(),
    [collapsed.terminal, dockApi],
  )

  const toggleShell = useCallback(
    () => createPanelToggle({
      panelId: 'shell', panelKey: 'shell', dimension: 'height',
      dockApi, isCollapsed: collapsed.shell, setCollapsed,
      panelSizesRef, collapsedThreshold: panelCollapsedRef.current.shell,
      storagePrefix: storagePrefixRef.current,
    })(),
    [collapsed.shell, dockApi],
  )

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
  useEffect(() => {
    if (!dockApi) return

    // On first run, only apply constraints and collapsed sizes, not expanded sizes
    // (layout restore already set the correct expanded sizes)
    const isFirstRun = !collapsedEffectRan.current
    if (isFirstRun) {
      collapsedEffectRan.current = true
    }

    const filetreePanel = dockApi.getPanel('filetree')
    const terminalPanel = dockApi.getPanel('terminal')

    const filetreeGroup = filetreePanel?.group
    if (filetreeGroup) {
      if (collapsed.filetree) {
        filetreeGroup.api.setConstraints({
          minimumWidth: panelCollapsedRef.current.filetree,
          maximumWidth: panelCollapsedRef.current.filetree,
        })
        filetreeGroup.api.setSize({ width: panelCollapsedRef.current.filetree })
      } else {
        // Use Infinity to explicitly clear max constraint and allow resizing
        filetreeGroup.api.setConstraints({
          minimumWidth: panelMinRef.current.filetree,
          maximumWidth: Infinity,
        })
        // Only set size on subsequent runs (user toggled), not on initial load
        if (!isFirstRun) {
          filetreeGroup.api.setSize({ width: panelSizesRef.current.filetree })
        }
      }
    }

    const terminalGroup = terminalPanel?.group
    if (terminalGroup) {
      if (collapsed.terminal) {
        terminalGroup.api.setConstraints({
          minimumWidth: panelCollapsedRef.current.terminal,
          maximumWidth: panelCollapsedRef.current.terminal,
        })
        terminalGroup.api.setSize({ width: panelCollapsedRef.current.terminal })
      } else {
        // Use Infinity to explicitly clear max constraint and allow resizing
        terminalGroup.api.setConstraints({
          minimumWidth: panelMinRef.current.terminal,
          maximumWidth: Infinity,
        })
        if (!isFirstRun) {
          terminalGroup.api.setSize({ width: panelSizesRef.current.terminal })
        }
      }
    }

    const shellPanel = dockApi.getPanel('shell')
    const shellGroup = shellPanel?.group

    // Apply constraints to shell group
    if (shellGroup) {
      if (collapsed.shell) {
        shellGroup.api.setConstraints({
          minimumHeight: panelCollapsedRef.current.shell,
          maximumHeight: panelCollapsedRef.current.shell,
        })
        shellGroup.api.setSize({ height: panelCollapsedRef.current.shell })
      } else {
        // Clear height constraints to allow resizing (use Infinity to explicitly remove max)
        shellGroup.api.setConstraints({
          minimumHeight: panelMinRef.current.shell,
          maximumHeight: Infinity,
        })
        // Only set size on subsequent runs (user toggled), not on initial load
        if (!isFirstRun) {
          // Ensure saved size respects minimum constraint
          const savedHeight = panelSizesRef.current.shell
          const minHeight = panelMinRef.current.shell
          shellGroup.api.setSize({ height: Math.max(savedHeight, minHeight) })
        }
      }
    }
  }, [dockApi, collapsed])

  // Git status polling removed - not currently used in UI

  const normalizeApprovalPath = useCallback(
    (approval) => _normalizeApprovalPath(approval, projectRoot),
    [projectRoot],
  )

  const getReviewTitle = useCallback(
    (approval) => _getReviewTitle(approval, projectRoot),
    [projectRoot],
  )

  // Open file in a specific position (used for drag-drop)
  const openFileAtPosition = useCallback(
    (path, position, extraParams = {}) => {
      if (!dockApi) return

      const panelId = `editor-${path}`
      const existingPanel = dockApi.getPanel(panelId)

      if (existingPanel) {
        // If opening with initialMode, update the panel params
        if (extraParams.initialMode) {
          existingPanel.api.updateParameters({ initialMode: extraParams.initialMode })
        }
        existingPanel.api.setActive()
        return
      }

      const emptyPanel = dockApi.getPanel('empty-center')
      const centerGroup = centerGroupRef.current
      if (centerGroup) {
        centerGroup.header.hidden = false
      }

      const addEditorPanel = (content) => {
        setTabs((prev) => ({
          ...prev,
          [path]: { content, isDirty: false },
        }))

        const panel = dockApi.addPanel({
          id: panelId,
          component: 'editor',
          title: getFileName(path),
          position,
          params: {
            path,
            initialContent: content,
            contentVersion: 1,
            ...extraParams,
            onContentChange: (p, newContent) => {
              setTabs((prev) => ({
                ...prev,
                [p]: { ...prev[p], content: newContent },
              }))
            },
            onDirtyChange: (p, dirty) => {
              setTabs((prev) => ({
                ...prev,
                [p]: { ...prev[p], isDirty: dirty },
              }))
              const panel = dockApi.getPanel(`editor-${p}`)
              if (panel) {
                panel.api.setTitle(getFileName(p) + (dirty ? ' *' : ''))
              }
            },
          },
        })

        if (emptyPanel) {
          emptyPanel.api.close()
        }
        if (panel?.group) {
          panel.group.header.hidden = false
          centerGroupRef.current = panel.group
          // Apply minimum height constraint to center group (use Infinity to allow resize)
          panel.group.api.setConstraints({
            minimumHeight: panelMinRef.current.center,
            maximumHeight: Infinity,
          })
        }
      }

      fetch(buildApiUrl(`/api/file?path=${encodeURIComponent(path)}`))
        .then((r) => r.json())
        .then((data) => {
          addEditorPanel(data.content || '')
        })
        .catch(() => {
          addEditorPanel('')
        })
    },
    [dockApi]
  )

  const openFile = useCallback(
    (path) => {
      if (!dockApi) return false

      const panelId = `editor-${path}`
      const existingPanel = dockApi.getPanel(panelId)

      if (existingPanel) {
        existingPanel.api.setActive()
        return true
      }

      openFileAtPosition(path, findEditorPosition(dockApi, centerGroupRef.current))
      return true
    },
    [dockApi, openFileAtPosition]
  )

  const openFileToSide = useCallback(
    (path) => {
      if (!dockApi) return

      const existingPanel = dockApi.getPanel(`editor-${path}`)
      if (existingPanel) {
        existingPanel.api.setActive()
        return
      }

      openFileAtPosition(path, findSidePosition(dockApi, centerGroupRef.current))
    },
    [dockApi, openFileAtPosition]
  )

  const openDiff = useCallback(
    (path, _status) => {
      if (!dockApi) return

      const existingPanel = dockApi.getPanel(`editor-${path}`)
      if (existingPanel) {
        existingPanel.api.updateParameters({ initialMode: 'git-diff' })
        existingPanel.api.setActive()
        setActiveDiffFile(path)
        return
      }

      openFileAtPosition(path, findDiffPosition(dockApi, centerGroupRef.current), { initialMode: 'git-diff' })
      setActiveDiffFile(path)
    },
    [dockApi, openFileAtPosition]
  )

  useEffect(() => {
    if (!dockApi || !approvalsLoaded) return
    const pendingIds = new Set(approvals.map((req) => req.id))
    const panels = Array.isArray(dockApi.panels)
      ? dockApi.panels
      : typeof dockApi.getPanels === 'function'
        ? dockApi.getPanels()
        : []

    panels.forEach((panel) => {
      if (!panel?.id?.startsWith('review-')) return
      const requestId = panel.id.replace('review-', '')
      if (!pendingIds.has(requestId)) {
        panel.api.close()
      }
    })

    approvals.forEach((approval) => {
      const panelId = `review-${approval.id}`
      const approvalPath = normalizeApprovalPath(approval)
      const existingPanel = dockApi.getPanel(panelId)
      const params = {
        request: approval,
        filePath: approvalPath,
        onDecision: handleDecision,
        onOpenFile: openFile,
      }

      if (existingPanel) {
        existingPanel.api.updateParameters(params)
        existingPanel.api.setTitle(getReviewTitle(approval))
        return
      }

      // Get panel references for positioning
      const emptyPanel = dockApi.getPanel('empty-center')
      const shellPanel = dockApi.getPanel('shell')

      // Find existing editor/review panels to add as sibling tab
      const allPanels = Array.isArray(dockApi.panels) ? dockApi.panels : []
      const existingEditorPanel = allPanels.find(p => p.id.startsWith('editor-') || p.id.startsWith('review-'))

      // Priority: existing editor group > centerGroupRef > empty panel > shell > fallback
      let position
      if (existingEditorPanel?.group) {
        // Add as tab next to existing editors/reviews
        position = { referenceGroup: existingEditorPanel.group }
      } else if (centerGroupRef.current) {
        position = { referenceGroup: centerGroupRef.current }
      } else if (emptyPanel?.group) {
        position = { referenceGroup: emptyPanel.group }
      } else if (shellPanel?.group) {
        // Add above shell to maintain center column structure
        position = { direction: 'above', referenceGroup: shellPanel.group }
      } else {
        position = { direction: 'right', referencePanel: 'filetree' }
      }

      const panel = dockApi.addPanel({
        id: panelId,
        component: 'review',
        title: getReviewTitle(approval),
        position,
        params,
      })

      // Close empty panel AFTER adding review to its group
      if (emptyPanel) {
        emptyPanel.api.close()
      }

      if (panel?.group) {
        panel.group.header.hidden = false
        centerGroupRef.current = panel.group
        // Apply minimum height constraint to center group (use Infinity to allow resize)
        panel.group.api.setConstraints({
          minimumHeight: panelMinRef.current.center,
          maximumHeight: Infinity,
        })
      }
    })
  }, [
    approvals,
    approvalsLoaded,
    dockApi,
    getReviewTitle,
    handleDecision,
    normalizeApprovalPath,
    openFile,
  ])

  const onReady = (event) => {
    const api = event.api
    setDockApi(api)

    const applyLockedPanels = () => applyLockedPanelsUtil(api, panelMinRef.current)

    const ensureCorePanels = () => {
      centerGroupRef.current = ensureCorePanelsUtil(api, panelMinRef.current)
      applyLockedPanels()
    }

    // Check if there's a saved layout - if so, DON'T create panels here
    // Let the layout restoration effect handle it to avoid creating->destroying->recreating
    // We check localStorage directly since projectRoot isn't available yet
    let hasSavedLayout = false
    let invalidLayoutFound = false
    try {
      // Use storagePrefix from config (available via closure from outer scope)
      const layoutKeyPrefix = `${storagePrefix}-`
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i)
        if (key && key.startsWith(layoutKeyPrefix) && key.endsWith('-layout')) {
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

            // Invalid layout detected - clean up and reload
            if (!hasValidStructure || !hasValidVersion || !hasPanels) {
              console.warn('[Layout] Invalid layout detected in onReady, clearing and reloading:', key)
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

    // Only create fresh panels if no saved layout exists
    // Otherwise, layout restoration will handle panel creation
    if (!hasSavedLayout || invalidLayoutFound) {
      ensureCorePanels()
    }
    ensureCorePanelsRef.current = () => {
      ensureCorePanels()
      applyLockedPanels()
    }

    // Apply initial panel sizes for fresh layout
    // (Restored layouts will have sizes reapplied in the layout restoration effect)
    requestAnimationFrame(() => {
      const filetreeGroup = api.getPanel('filetree')?.group
      const terminalGroup = api.getPanel('terminal')?.group
      const shellGroup = api.getPanel('shell')?.group
      if (filetreeGroup) {
        api.getGroup(filetreeGroup.id)?.api.setSize({ width: panelSizesRef.current.filetree })
      }
      if (terminalGroup) {
        api.getGroup(terminalGroup.id)?.api.setSize({ width: panelSizesRef.current.terminal })
      }
      if (shellGroup) {
        // Ensure shell height respects minimum constraint
        const shellHeight = Math.max(panelSizesRef.current.shell, panelMinRef.current.shell)
        api.getGroup(shellGroup.id)?.api.setSize({ height: shellHeight })
      }
    })

    // Handle panel close to clean up tabs state
    api.onDidRemovePanel((e) => {
      if (e.id.startsWith('editor-')) {
        const path = e.id.replace('editor-', '')
        setTabs((prev) => {
          const next = { ...prev }
          delete next[path]
          return next
        })
      }
    })


    // When all editors are closed, show the empty panel again
    api.onDidRemovePanel(() => {
      // Check if empty panel already exists
      const existingEmpty = api.getPanel('empty-center')
      if (existingEmpty) return

      // Check if there are any editor or review panels left anywhere
      const allPanels = Array.isArray(api.panels) ? api.panels : []
      const hasEditors = allPanels.some(p => p.id.startsWith('editor-'))
      const hasReviews = allPanels.some(p => p.id.startsWith('review-'))

      // If there are still editors or reviews, don't add empty panel
      if (hasEditors || hasReviews) return

      // Need to add empty panel - find the right position
      // Try to use centerGroupRef if it still exists and has panels
      let centerGroup = centerGroupRef.current
      const groupStillExists = centerGroup && api.groups?.includes(centerGroup)

      // Get shell panel to position relative to it
      const shellPanel = api.getPanel('shell')

      let emptyPanel
      if (groupStillExists && centerGroup.panels?.length > 0) {
        // Group still exists with panels, add to it
        emptyPanel = api.addPanel({
          id: 'empty-center',
          component: 'empty',
          title: '',
          position: { referenceGroup: centerGroup },
        })
      } else if (shellPanel?.group) {
        // Center group is gone, add above shell panel
        emptyPanel = api.addPanel({
          id: 'empty-center',
          component: 'empty',
          title: '',
          position: { direction: 'above', referenceGroup: shellPanel.group },
        })
      } else {
        // Fallback: add to the right of filetree
        emptyPanel = api.addPanel({
          id: 'empty-center',
          component: 'empty',
          title: '',
          position: { direction: 'right', referencePanel: 'filetree' },
        })
      }

      // Update centerGroupRef and apply constraints
      if (emptyPanel?.group) {
        centerGroupRef.current = emptyPanel.group
        emptyPanel.group.header.hidden = true
        emptyPanel.group.api.setConstraints({
          minimumHeight: panelMinRef.current.center,
          maximumHeight: Infinity,
        })
      }
    })

    const saveLayoutNow = () => {
      if (typeof api.toJSON !== 'function') return
      // Use refs for stable access in event handlers
      saveLayout(storagePrefixRef.current, projectRootRef.current, api.toJSON(), layoutVersionRef.current)
    }

    // Enforce minimum constraints on panels (workaround for dockview not enforcing during drag)
    const enforceMinimumConstraints = () => {
      const shellPanel = api.getPanel('shell')
      const shellGroup = shellPanel?.group
      if (shellGroup) {
        const height = shellGroup.api.height
        const minHeight = panelMinRef.current.shell
        const collapsedHeight = panelCollapsedRef.current.shell
        // If height is below minimum but not collapsed, enforce minimum
        if (height < minHeight && height > collapsedHeight) {
          shellGroup.api.setSize({ height: minHeight })
        }
      }
    }

    // Save panel sizes when layout changes (user resizes via drag)
    const savePanelSizesNow = () => {
      const filetreePanel = api.getPanel('filetree')
      const terminalPanel = api.getPanel('terminal')
      const shellPanel = api.getPanel('shell')

      const filetreeGroup = filetreePanel?.group
      const terminalGroup = terminalPanel?.group
      const shellGroup = shellPanel?.group

      const newSizes = { ...panelSizesRef.current }
      let changed = false

      // Only save if not collapsed (width/height > collapsed size)
      if (filetreeGroup && filetreeGroup.api.width > panelCollapsedRef.current.filetree) {
        if (newSizes.filetree !== filetreeGroup.api.width) {
          newSizes.filetree = filetreeGroup.api.width
          changed = true
        }
      }
      if (terminalGroup && terminalGroup.api.width > panelCollapsedRef.current.terminal) {
        if (newSizes.terminal !== terminalGroup.api.width) {
          newSizes.terminal = terminalGroup.api.width
          changed = true
        }
      }
      if (shellGroup && shellGroup.api.height > panelCollapsedRef.current.shell) {
        // Enforce minimum height before saving
        const height = Math.max(shellGroup.api.height, panelMinRef.current.shell)
        if (newSizes.shell !== height) {
          newSizes.shell = height
          changed = true
        }
      }

      if (changed) {
        panelSizesRef.current = newSizes
        savePanelSizes(newSizes, storagePrefixRef.current)
      }
    }

    // Debounce layout saves to avoid excessive writes during drag operations
    const debouncedSaveLayout = debounce(saveLayoutNow, 300)
    const debouncedSavePanelSizes = debounce(savePanelSizesNow, 300)

    if (typeof api.onDidLayoutChange === 'function') {
      api.onDidLayoutChange(() => {
        // Enforce minimum constraints after resize (workaround for dockview)
        enforceMinimumConstraints()
        debouncedSaveLayout()
        debouncedSavePanelSizes()
      })
    }

    // Flush pending saves before page unload to avoid data loss
    window.addEventListener('beforeunload', () => {
      debouncedSaveLayout.flush()
      debouncedSavePanelSizes.flush()
    })

    // Mark as initialized immediately - tabs will be restored via useEffect
    isInitialized.current = true
  }

  // Browser tab title management (extracted hook)
  useBrowserTitle(projectRoot, config.branding)

  // Restore layout once projectRoot is loaded and dockApi is available
  const layoutRestorationRan = useRef(false)
  useEffect(() => {
    // Wait for both dockApi and projectRoot to be available
    // projectRoot === null means not loaded yet
    if (!dockApi || projectRoot === null || layoutRestorationRan.current) return
    layoutRestorationRan.current = true

    const savedLayout = loadLayout(storagePrefix, projectRoot, KNOWN_COMPONENTS, layoutVersion)
    if (!savedLayout) {
      if (ensureCorePanelsRef.current) {
        ensureCorePanelsRef.current()
        layoutRestored.current = true
        requestAnimationFrame(() => {
          const ftGroup = dockApi.getPanel('filetree')?.group
          const tGroup = dockApi.getPanel('terminal')?.group
          const sGroup = dockApi.getPanel('shell')?.group

          if (ftGroup) {
            const ftApi = dockApi.getGroup(ftGroup.id)?.api
            if (ftApi) {
              if (collapsed.filetree) {
                ftApi.setConstraints({ minimumWidth: panelCollapsedRef.current.filetree, maximumWidth: panelCollapsedRef.current.filetree })
                ftApi.setSize({ width: panelCollapsedRef.current.filetree })
              } else {
                ftApi.setConstraints({ minimumWidth: panelMinRef.current.filetree, maximumWidth: Infinity })
                ftApi.setSize({ width: panelSizesRef.current.filetree })
              }
            }
          }
          if (tGroup) {
            const tApi = dockApi.getGroup(tGroup.id)?.api
            if (tApi) {
              if (collapsed.terminal) {
                tApi.setConstraints({ minimumWidth: panelCollapsedRef.current.terminal, maximumWidth: panelCollapsedRef.current.terminal })
                tApi.setSize({ width: panelCollapsedRef.current.terminal })
              } else {
                tApi.setConstraints({ minimumWidth: panelMinRef.current.terminal, maximumWidth: Infinity })
                tApi.setSize({ width: panelSizesRef.current.terminal })
              }
            }
          }
          if (sGroup) {
            const sApi = dockApi.getGroup(sGroup.id)?.api
            if (sApi) {
              if (collapsed.shell) {
                sApi.setConstraints({ minimumHeight: panelCollapsedRef.current.shell, maximumHeight: panelCollapsedRef.current.shell })
                sApi.setSize({ height: panelCollapsedRef.current.shell })
              } else {
                sApi.setConstraints({ minimumHeight: panelMinRef.current.shell, maximumHeight: Infinity })
                // Ensure shell height respects minimum constraint
                const shellHeight = Math.max(panelSizesRef.current.shell, panelMinRef.current.shell)
                sApi.setSize({ height: shellHeight })
              }
            }
          }

          collapsedEffectRan.current = true
        })
      }
      return
    }
    if (savedLayout && typeof dockApi.fromJSON === 'function') {
      // Since onReady skips panel creation when a saved layout exists,
      // we can directly call fromJSON without clearing first
      // This avoids the create->destroy->recreate race condition
      try {
        dockApi.fromJSON(savedLayout)
        layoutRestored.current = true

        // After restoring, apply locked panels and cleanup
        const filetreePanel = dockApi.getPanel('filetree')
        const terminalPanel = dockApi.getPanel('terminal')
        const shellPanel = dockApi.getPanel('shell')

        const filetreeGroup = filetreePanel?.group
        if (filetreeGroup) {
          filetreeGroup.locked = true
          filetreeGroup.header.hidden = true
        }

        // Update filetree params with callbacks (callbacks can't be serialized in layout JSON)
        if (filetreePanel) {
          filetreePanel.api.updateParameters({
            onOpenFile: openFile,
            onOpenFileToSide: openFileToSide,
            onOpenDiff: openDiff,
            projectRoot,
            activeFile,
            activeDiffFile,
            collapsed: collapsed.filetree,
            onToggleCollapse: toggleFiletree,
          })
        }

        const terminalGroup = terminalPanel?.group
        if (terminalGroup) {
          terminalGroup.locked = true
          terminalGroup.header.hidden = true
        }

        const shellGroup = shellPanel?.group
        if (shellGroup) {
          // Lock group to prevent closing tabs, but show header
          shellGroup.locked = true
          shellGroup.header.hidden = false
          shellGroup.api.setConstraints({
            minimumHeight: panelMinRef.current.shell,
            maximumHeight: Infinity,
          })
          // Enforce minimum height if saved layout has invalid dimensions
          // (between collapsed 36px and minimum 100px)
          const currentHeight = shellGroup.api.height
          const minHeight = panelMinRef.current.shell
          const collapsedHeight = panelCollapsedRef.current.shell
          if (currentHeight < minHeight && currentHeight > collapsedHeight) {
            shellGroup.api.setSize({ height: minHeight })
          }
        }

        // If layout has editor panels, set constraints and close empty-center
        const panels = Array.isArray(dockApi.panels)
          ? dockApi.panels
          : typeof dockApi.getPanels === 'function'
            ? dockApi.getPanels()
            : []
        const editorPanels = panels.filter((p) => p.id.startsWith('editor-'))
        const hasReviews = panels.some((p) => p.id.startsWith('review-'))
        if (editorPanels.length > 0 || hasReviews) {
          // Apply minimum height constraint to editor group (prevents shell from taking all space)
          // This must happen regardless of whether empty-center exists, since saved layouts
          // with open editors won't have the empty-center panel
          const editorPanel = panels.find((p) => p.id.startsWith('editor-') || p.id.startsWith('review-'))
          if (editorPanel?.group) {
            centerGroupRef.current = editorPanel.group
            editorPanel.group.api.setConstraints({
              minimumHeight: panelMinRef.current.center,
              maximumHeight: Infinity,
            })
          }
          // Close empty-center if it exists
          const emptyPanel = dockApi.getPanel('empty-center')
          if (emptyPanel) {
            emptyPanel.api.close()
          }
        }

        // Update editor panels with callbacks (callbacks can't be serialized in layout JSON)
        editorPanels.forEach((panel) => {
          const path = panel.id.replace('editor-', '')
          panel.api.updateParameters({
            onContentChange: (p, newContent) => {
              setTabs((prev) => ({
                ...prev,
                [p]: { ...prev[p], content: newContent },
              }))
            },
            onDirtyChange: (p, dirty) => {
              setTabs((prev) => ({
                ...prev,
                [p]: { ...prev[p], isDirty: dirty },
              }))
              const editorPanel = dockApi.getPanel(`editor-${p}`)
              if (editorPanel) {
                editorPanel.api.setTitle(getFileName(p) + (dirty ? ' *' : ''))
              }
            },
          })
        })

        // Update centerGroupRef if there's an empty-center panel
        const emptyPanel = dockApi.getPanel('empty-center')
        if (emptyPanel?.group) {
          centerGroupRef.current = emptyPanel.group
          // Set minimum height for the center group (use Infinity to allow resize)
          emptyPanel.group.api.setConstraints({
            minimumHeight: panelMinRef.current.center,
            maximumHeight: Infinity,
          })
        }

        // Prune empty groups
        const pruned = pruneEmptyGroups(dockApi, KNOWN_COMPONENTS)
        if (pruned && typeof dockApi.toJSON === 'function') {
          saveLayout(storagePrefix, projectRoot, dockApi.toJSON(), layoutVersion)
        }

        // Apply saved panel sizes, respecting collapsed state
        // collapsed state is loaded from localStorage at init, so we can check it here
        requestAnimationFrame(() => {
          const ftGroup = dockApi.getPanel('filetree')?.group
          const tGroup = dockApi.getPanel('terminal')?.group
          const sGroup = dockApi.getPanel('shell')?.group

          // For collapsed panels, set collapsed size; for expanded, use saved size
          if (ftGroup) {
            const ftApi = dockApi.getGroup(ftGroup.id)?.api
            if (ftApi) {
              if (collapsed.filetree) {
                ftApi.setConstraints({ minimumWidth: panelCollapsedRef.current.filetree, maximumWidth: panelCollapsedRef.current.filetree })
                ftApi.setSize({ width: panelCollapsedRef.current.filetree })
              } else {
                ftApi.setConstraints({ minimumWidth: panelMinRef.current.filetree, maximumWidth: Infinity })
                ftApi.setSize({ width: panelSizesRef.current.filetree })
              }
            }
          }
          if (tGroup) {
            const tApi = dockApi.getGroup(tGroup.id)?.api
            if (tApi) {
              if (collapsed.terminal) {
                tApi.setConstraints({ minimumWidth: panelCollapsedRef.current.terminal, maximumWidth: panelCollapsedRef.current.terminal })
                tApi.setSize({ width: panelCollapsedRef.current.terminal })
              } else {
                tApi.setConstraints({ minimumWidth: panelMinRef.current.terminal, maximumWidth: Infinity })
                tApi.setSize({ width: panelSizesRef.current.terminal })
              }
            }
          }
          if (sGroup) {
            const sApi = dockApi.getGroup(sGroup.id)?.api
            if (sApi) {
              if (collapsed.shell) {
                sApi.setConstraints({ minimumHeight: panelCollapsedRef.current.shell, maximumHeight: panelCollapsedRef.current.shell })
                sApi.setSize({ height: panelCollapsedRef.current.shell })
              } else {
                sApi.setConstraints({ minimumHeight: panelMinRef.current.shell, maximumHeight: Infinity })
                // Ensure shell height respects minimum constraint
                const shellHeight = Math.max(panelSizesRef.current.shell, panelMinRef.current.shell)
                sApi.setSize({ height: shellHeight })
              }
            }
          }

          // Reset the collapsed effect flag so it doesn't override on first toggle
          collapsedEffectRan.current = true
        })
      } catch {
        layoutRestored.current = false
      }
    }
  }, [dockApi, projectRoot, storagePrefix, collapsed.filetree, collapsed.terminal, collapsed.shell, openFile, openFileToSide, openDiff, activeFile, activeDiffFile, toggleFiletree])

  // Track active panel to highlight in file tree and sync URL
  useEffect(() => {
    if (!dockApi) return
    const disposable = dockApi.onDidActivePanelChange((panel) => {
      if (panel && panel.id && panel.id.startsWith('editor-')) {
        const path = panel.id.replace('editor-', '')
        setActiveFile(path)
        // Also set activeDiffFile if this file is in git changes
        setActiveDiffFile(path)
        // Sync URL for easy sharing/reload
        const url = new URL(window.location.href)
        url.searchParams.set('doc', path)
        window.history.replaceState({}, '', url)
      } else {
        setActiveFile(null)
        setActiveDiffFile(null)
        // Clear doc param when not on an editor
        const url = new URL(window.location.href)
        url.searchParams.delete('doc')
        window.history.replaceState({}, '', url)
      }
    })
    return () => disposable.dispose()
  }, [dockApi])

  // Update filetree panel params when openFile changes
  useEffect(() => {
    if (!dockApi) return
    const filetreePanel = dockApi.getPanel('filetree')
    if (filetreePanel) {
      filetreePanel.api.updateParameters({
        onOpenFile: openFile,
        onOpenFileToSide: openFileToSide,
        onOpenDiff: openDiff,
        projectRoot,
        activeFile,
        activeDiffFile,
        collapsed: collapsed.filetree,
        onToggleCollapse: toggleFiletree,
      })
    }
  }, [dockApi, openFile, openFileToSide, openDiff, projectRoot, activeFile, activeDiffFile, collapsed.filetree, toggleFiletree])

  // Helper to focus a review panel
  const focusReviewPanel = useCallback(
    (requestId) => {
      if (!dockApi) return
      const panel = dockApi.getPanel(`review-${requestId}`)
      if (panel) {
        panel.api.setActive()
      }
    },
    [dockApi]
  )

  // Update terminal panel params
  useEffect(() => {
    if (!dockApi) return
    const terminalPanel = dockApi.getPanel('terminal')
    if (terminalPanel) {
      terminalPanel.api.updateParameters({
        collapsed: collapsed.terminal,
        onToggleCollapse: toggleTerminal,
        approvals,
        onFocusReview: focusReviewPanel,
        onDecision: handleDecision,
        normalizeApprovalPath,
      })
    }
  }, [dockApi, collapsed.terminal, toggleTerminal, approvals, focusReviewPanel, handleDecision, normalizeApprovalPath])

  // Update shell panel params
  // projectRoot dependency ensures this runs after layout restoration
  useEffect(() => {
    if (!dockApi) return
    const shellPanel = dockApi.getPanel('shell')
    if (shellPanel) {
      shellPanel.api.updateParameters({
        collapsed: collapsed.shell,
        onToggleCollapse: toggleShell,
      })
    }
  }, [dockApi, collapsed.shell, toggleShell, projectRoot])

  // Restore saved tabs when dockApi and projectRoot become available
  const hasRestoredTabs = useRef(false)
  useEffect(() => {
    // Wait for projectRoot to be loaded (null = not loaded yet)
    if (!dockApi || projectRoot === null || hasRestoredTabs.current) return
    hasRestoredTabs.current = true

    if (layoutRestored.current) {
      return
    }

    const savedPaths = loadSavedTabs(storagePrefix, projectRoot)
    if (savedPaths.length > 0) {
      // Small delay to ensure layout is ready
      setTimeout(() => {
        savedPaths.forEach((path) => {
          openFile(path)
        })
      }, 50)
    }
  }, [dockApi, projectRoot, openFile, storagePrefix])

  // Save open tabs to localStorage whenever tabs change (but not on initial empty state)
  useEffect(() => {
    // Wait for projectRoot to be loaded
    if (!isInitialized.current || projectRoot === null) return
    const paths = Object.keys(tabs)
    saveTabs(storagePrefix, projectRoot, paths)
  }, [tabs, projectRoot, storagePrefix])

  // Restore document from URL query param on load
  const hasRestoredFromUrl = useRef(false)
  useEffect(() => {
    if (!dockApi || projectRoot === null || hasRestoredFromUrl.current) return

    // Wait for core panels to exist before opening files
    const filetreePanel = dockApi.getPanel('filetree')
    if (!filetreePanel) return

    hasRestoredFromUrl.current = true

    const docPath = new URLSearchParams(window.location.search).get('doc')
    if (docPath) {
      // Small delay to ensure layout is fully ready
      setTimeout(() => {
        openFile(docPath)
      }, 150)
    }
  }, [dockApi, projectRoot, openFile])

  // Handle external drag events (files from FileTree)
  const showDndOverlay = (event) => {
    // Check if this is a file drag from our FileTree
    const hasFileData = event.dataTransfer.types.includes('application/x-kurt-file')
    return hasFileData
  }

  const onDidDrop = (event) => {
    const { dataTransfer, position, group } = event
    const fileDataStr = dataTransfer.getData('application/x-kurt-file')

    if (!fileDataStr) return

    try {
      const fileData = JSON.parse(fileDataStr)
      const path = fileData.path

      // Determine position based on drop location
      let dropPosition
      if (group) {
        // Dropped on a group - add to that group
        dropPosition = { referenceGroup: group }
      } else if (position) {
        // Dropped to create a new split
        dropPosition = position
      } else {
        // Fallback to center group
        const centerGroup = centerGroupRef.current
        dropPosition = centerGroup
          ? { referenceGroup: centerGroup }
          : { direction: 'right', referencePanel: 'filetree' }
      }

      openFileAtPosition(path, dropPosition)
    } catch {
      // Ignore parse errors
    }
  }

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
        <header className="app-header">
          <div className="app-header-brand">
            <div className="app-header-logo" aria-hidden="true">
              {config.branding?.logo || 'B'}
            </div>
            <div className="app-header-title">
              {projectRoot?.split('/').pop() || config.branding?.name || 'Workspace'}
            </div>
          </div>
          <div className="app-header-controls">
            <ThemeToggle />
          </div>
        </header>
        {unavailableEssentials.length > 0 && (
          <div className="capability-warning">
            <strong>Warning:</strong> Some features are unavailable.
            Missing capabilities for: {unavailableEssentials.map(p => p.title || p.id).join(', ')}.
          </div>
        )}
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
