import { useState, useEffect, useCallback, useRef } from 'react'
import { DockviewReact, DockviewDefaultTab } from 'dockview-react'
import 'dockview-react/dist/styles/dockview.css'
import { ChevronDown, ChevronUp } from 'lucide-react'

import { ThemeProvider } from './hooks/useTheme'
import { useConfig } from './config'
import { buildApiUrl } from './utils/apiBase'
import ThemeToggle from './components/ThemeToggle'
import ClaudeStreamChat from './components/chat/ClaudeStreamChat'
import {
  getComponents,
  getKnownComponents,
  essentialPanes,
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

// Get components and known component IDs from pane registry
const components = getComponents()
const KNOWN_COMPONENTS = getKnownComponents()

// Get essential panel IDs from pane registry
const ESSENTIAL_PANELS = essentialPanes()

// Validate layout structure to detect drift
// Returns true if layout is valid, false if it has drifted
const validateLayoutStructure = (layout) => {
  if (!layout?.grid || !layout?.panels) return false

  const panels = layout.panels
  const panelIds = Object.keys(panels)

  // Check all essential panels exist
  for (const essentialId of ESSENTIAL_PANELS) {
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

  // Validate filetree is alone in its group
  const filetreeGroup = groups[panelToGroup['filetree']]
  if (filetreeGroup) {
    const otherInGroup = filetreeGroup.filter((p) => p !== 'filetree')
    const invalidInGroup = otherInGroup.some((p) => ESSENTIAL_PANELS.includes(p))
    if (invalidInGroup) {
      console.warn('[Layout drift] filetree group has invalid panels:', otherInGroup)
      return false
    }
  }

  // Validate terminal is alone in its group
  const terminalGroup = groups[panelToGroup['terminal']]
  if (terminalGroup) {
    const otherInGroup = terminalGroup.filter((p) => p !== 'terminal')
    const invalidInGroup = otherInGroup.some((p) => ESSENTIAL_PANELS.includes(p))
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

// Custom tab component that hides close button (for shell tabs)
const TabWithoutClose = (props) => <DockviewDefaultTab {...props} hideClose />

const tabComponents = {
  noClose: TabWithoutClose,
}

const getFileName = (path) => {
  const parts = path.split('/')
  return parts[parts.length - 1]
}

const LAYOUT_VERSION = 22 // Increment to force layout reset after removing workflows

// Generate a short hash from the project root path for localStorage keys
const hashProjectRoot = (root) => {
  if (!root) return 'default'
  let hash = 0
  for (let i = 0; i < root.length; i++) {
    const char = root.charCodeAt(i)
    hash = ((hash << 5) - hash) + char
    hash = hash & hash // Convert to 32bit integer
  }
  return Math.abs(hash).toString(36)
}

// Storage key generators (project-specific)
// prefix defaults to 'kurt-web' for backwards compatibility
const getStorageKey = (prefix, projectRoot, suffix) => `${prefix}-${hashProjectRoot(projectRoot)}-${suffix}`

// Load saved tabs from localStorage
const loadSavedTabs = (prefix, projectRoot) => {
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

// Save open tabs to localStorage
const saveTabs = (prefix, projectRoot, paths) => {
  try {
    localStorage.setItem(getStorageKey(prefix, projectRoot, 'tabs'), JSON.stringify(paths))
  } catch {
    // Ignore storage errors
  }
}

const loadLayout = (prefix, projectRoot, configLayoutVersion) => {
  try {
    const raw = localStorage.getItem(getStorageKey(prefix, projectRoot, 'layout'))
    if (!raw) return null
    const parsed = JSON.parse(raw)

    // Check internal format version - force reset if outdated
    if (!parsed?.version || parsed.version < LAYOUT_VERSION) {
      console.info('[Layout] Format version outdated, resetting layout')
      localStorage.removeItem(getStorageKey(prefix, projectRoot, 'layout'))
      return null
    }

    // Check config layout version - force reset if user bumped their layoutVersion
    // Treat missing configVersion as version 1 (default) for backwards compatibility
    const savedConfigVersion = parsed?.configVersion ?? 1
    if (configLayoutVersion && savedConfigVersion !== configLayoutVersion) {
      console.info('[Layout] Config version changed, resetting layout')
      localStorage.removeItem(getStorageKey(prefix, projectRoot, 'layout'))
      return null
    }

    if (parsed?.panels && typeof parsed.panels === 'object') {
      const panels = Object.values(parsed.panels)
      const hasUnknown = panels.some(
        (panel) =>
          panel?.contentComponent &&
          !KNOWN_COMPONENTS.has(panel.contentComponent),
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

const pruneEmptyGroups = (api) => {
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
      KNOWN_COMPONENTS.has(panel?.api?.component),
    )
    if (!hasKnownPanel) {
      api.removeGroup(group)
      removed = true
    }
  })

  return removed
}

const saveLayout = (prefix, projectRoot, layout, configLayoutVersion) => {
  try {
    const layoutWithVersion = {
      ...layout,
      version: LAYOUT_VERSION,
      configVersion: configLayoutVersion || 1,
    }
    localStorage.setItem(getStorageKey(prefix, projectRoot, 'layout'), JSON.stringify(layoutWithVersion))
  } catch {
    // Ignore storage errors
  }
}

// Collapsed state and panel sizes are shared across projects (UI preference)
const getCollapsedKey = (prefix) => `${prefix}-sidebar-collapsed`
const getPanelSizesKey = (prefix) => `${prefix}-panel-sizes`

const loadCollapsedState = (prefix, defaults) => {
  try {
    const saved = localStorage.getItem(getCollapsedKey(prefix))
    if (saved) {
      return JSON.parse(saved)
    }
  } catch {
    // Ignore parse errors
  }
  return defaults || { filetree: false, terminal: false }
}

const saveCollapsedState = (prefix, state) => {
  try {
    localStorage.setItem(getCollapsedKey(prefix), JSON.stringify(state))
  } catch {
    // Ignore storage errors
  }
}

const loadPanelSizes = (prefix, defaults) => {
  try {
    const saved = localStorage.getItem(getPanelSizesKey(prefix))
    if (saved) {
      return JSON.parse(saved)
    }
  } catch {
    // Ignore parse errors
  }
  return defaults || { filetree: 280, terminal: 400, shell: 250 }
}

const savePanelSizes = (prefix, sizes) => {
  try {
    localStorage.setItem(getPanelSizesKey(prefix), JSON.stringify(sizes))
  } catch {
    // Ignore storage errors
  }
}

export default function App() {
  // Get config (defaults are used until async load completes)
  const config = useConfig()
  const storagePrefix = config.storage?.prefix || 'kurt-web'
  const layoutVersion = config.storage?.layoutVersion || 1

  const [dockApi, setDockApi] = useState(null)
  const [tabs, setTabs] = useState({}) // path -> { content, isDirty }
  const [approvals, setApprovals] = useState([])
  const [approvalsLoaded, setApprovalsLoaded] = useState(false)
  const [activeFile, setActiveFile] = useState(null)
  const [activeDiffFile, setActiveDiffFile] = useState(null)
  const [collapsed, setCollapsed] = useState(() =>
    loadCollapsedState(storagePrefix, { filetree: false, terminal: false })
  )
  const panelSizesRef = useRef(
    loadPanelSizes(storagePrefix, config.panels?.defaults || { filetree: 280, terminal: 400, shell: 250 })
  )
  const collapsedEffectRan = useRef(false)
  const dismissedApprovalsRef = useRef(new Set())
  const centerGroupRef = useRef(null)
  const isInitialized = useRef(false)
  const layoutRestored = useRef(false)
  const ensureCorePanelsRef = useRef(null)
  const [projectRoot, setProjectRoot] = useState(null) // null = not loaded yet, '' = loaded but empty
  const projectRootRef = useRef(null) // Stable ref for callbacks
  const storagePrefixRef = useRef(storagePrefix) // Stable ref for callbacks
  storagePrefixRef.current = storagePrefix
  const layoutVersionRef = useRef(layoutVersion) // Stable ref for callbacks
  layoutVersionRef.current = layoutVersion

  // Toggle sidebar collapse - capture size before collapsing
  const toggleFiletree = useCallback(() => {
    if (!collapsed.filetree && dockApi) {
      // Capture current size before collapsing
      const filetreePanel = dockApi.getPanel('filetree')
      const filetreeGroup = filetreePanel?.group
      if (filetreeGroup) {
        const currentWidth = filetreeGroup.api.width
        if (currentWidth > 48) {
          panelSizesRef.current = { ...panelSizesRef.current, filetree: currentWidth }
          savePanelSizes(storagePrefixRef.current, panelSizesRef.current)
        }
      }
    }
    setCollapsed((prev) => {
      const next = { ...prev, filetree: !prev.filetree }
      saveCollapsedState(storagePrefixRef.current, next)
      return next
    })
  }, [collapsed.filetree, dockApi])

  const toggleTerminal = useCallback(() => {
    if (!collapsed.terminal && dockApi) {
      // Capture current size before collapsing
      const terminalPanel = dockApi.getPanel('terminal')
      const terminalGroup = terminalPanel?.group
      if (terminalGroup) {
        const currentWidth = terminalGroup.api.width
        if (currentWidth > 48) {
          panelSizesRef.current = { ...panelSizesRef.current, terminal: currentWidth }
          savePanelSizes(storagePrefixRef.current, panelSizesRef.current)
        }
      }
    }
    setCollapsed((prev) => {
      const next = { ...prev, terminal: !prev.terminal }
      saveCollapsedState(storagePrefixRef.current, next)
      return next
    })
  }, [collapsed.terminal, dockApi])

  const toggleShell = useCallback(() => {
    if (!collapsed.shell && dockApi) {
      // Capture current size before collapsing
      const shellPanel = dockApi.getPanel('shell')
      const shellGroup = shellPanel?.group
      if (shellGroup) {
        const currentHeight = shellGroup.api.height
        if (currentHeight > 36) {
          panelSizesRef.current = { ...panelSizesRef.current, shell: currentHeight }
          savePanelSizes(storagePrefixRef.current, panelSizesRef.current)
        }
      }
    }
    setCollapsed((prev) => {
      const next = { ...prev, shell: !prev.shell }
      saveCollapsedState(storagePrefixRef.current, next)
      return next
    })
  }, [collapsed.shell, dockApi])

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
          minimumWidth: 48,
          maximumWidth: 48,
        })
        filetreeGroup.api.setSize({ width: 48 })
      } else {
        // Use Infinity to explicitly clear max constraint and allow resizing
        filetreeGroup.api.setConstraints({
          minimumWidth: 180,
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
          minimumWidth: 48,
          maximumWidth: 48,
        })
        terminalGroup.api.setSize({ width: 48 })
      } else {
        // Use Infinity to explicitly clear max constraint and allow resizing
        terminalGroup.api.setConstraints({
          minimumWidth: 250,
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
          minimumHeight: 36,
          maximumHeight: 36,
        })
        shellGroup.api.setSize({ height: 36 })
      } else {
        // Clear height constraints to allow resizing (use Infinity to explicitly remove max)
        shellGroup.api.setConstraints({
          minimumHeight: 100,
          maximumHeight: Infinity,
        })
        // Only set size on subsequent runs (user toggled), not on initial load
        if (!isFirstRun) {
          shellGroup.api.setSize({ height: panelSizesRef.current.shell })
        }
      }
    }
  }, [dockApi, collapsed])

  // Git status polling removed - not currently used in UI

  // Fetch approvals
  useEffect(() => {
    let isActive = true

    const fetchApprovals = () => {
      fetch(buildApiUrl('/api/approval/pending'))
        .then((r) => r.json())
        .then((data) => {
          if (!isActive) return
          const requests = Array.isArray(data.requests) ? data.requests : []
          const filtered = requests.filter(
            (req) => !dismissedApprovalsRef.current.has(req.id),
          )
          setApprovals(filtered)
          setApprovalsLoaded(true)
        })
        .catch(() => {})
    }

    fetchApprovals()
    const interval = setInterval(fetchApprovals, 1000)

    return () => {
      isActive = false
      clearInterval(interval)
    }
  }, [])

  const handleDecision = useCallback(
    async (requestId, decision, reason) => {
      if (requestId) {
        dismissedApprovalsRef.current.add(requestId)
        setApprovals((prev) => prev.filter((req) => req.id !== requestId))
        if (dockApi) {
          const panel = dockApi.getPanel(`review-${requestId}`)
          if (panel) {
            panel.api.close()
          }
        }
      } else {
        setApprovals([])
      }
      try {
        await fetch(buildApiUrl('/api/approval/decision'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ request_id: requestId, decision, reason }),
        })
      } catch {
        // Ignore decision errors; UI already dismissed.
      }
    },
    [dockApi]
  )

  const normalizeApprovalPath = useCallback(
    (approval) => {
      if (!approval) return ''
      if (approval.project_path) return approval.project_path
      const filePath = approval.file_path || ''
      if (!filePath) return ''
      if (projectRoot) {
        const root = projectRoot.endsWith('/') ? projectRoot : `${projectRoot}/`
        if (filePath.startsWith(root)) {
          return filePath.slice(root.length)
        }
      }
      return filePath
    },
    [projectRoot],
  )

  const getReviewTitle = useCallback(
    (approval) => {
      const approvalPath = normalizeApprovalPath(approval)
      if (approvalPath) {
        return `Review: ${getFileName(approvalPath)}`
      }
      if (approval?.tool_name) {
        return `Review: ${approval.tool_name}`
      }
      return 'Review'
    },
    [normalizeApprovalPath],
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
            minimumHeight: 200,
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

      // Priority: existing editor group > centerGroupRef > empty panel > shell > fallback
      const emptyPanel = dockApi.getPanel('empty-center')
      const shellPanel = dockApi.getPanel('shell')
      const centerGroup = centerGroupRef.current

      // Find existing editor panels to add as sibling tab
      const allPanels = Array.isArray(dockApi.panels) ? dockApi.panels : []
      const existingEditorPanel = allPanels.find(p => p.id.startsWith('editor-') || p.id.startsWith('review-'))

      let position
      if (existingEditorPanel?.group) {
        // Add as tab next to existing editors/reviews
        position = { referenceGroup: existingEditorPanel.group }
      } else if (centerGroup) {
        position = { referenceGroup: centerGroup }
      } else if (emptyPanel?.group) {
        position = { referenceGroup: emptyPanel.group }
      } else if (shellPanel?.group) {
        // Add above shell to maintain center column structure
        position = { direction: 'above', referenceGroup: shellPanel.group }
      } else {
        position = { direction: 'right', referencePanel: 'filetree' }
      }

      openFileAtPosition(path, position)
      return true
    },
    [dockApi, openFileAtPosition]
  )

  const openFileToSide = useCallback(
    (path) => {
      if (!dockApi) return

      const panelId = `editor-${path}`
      const existingPanel = dockApi.getPanel(panelId)

      if (existingPanel) {
        existingPanel.api.setActive()
        return
      }

      // Find the active editor panel to split from (not terminal/filetree)
      const activePanel = dockApi.activePanel
      let position

      if (activePanel && activePanel.id.startsWith('editor-')) {
        // Split to the right of the current editor
        position = { direction: 'right', referencePanel: activePanel.id }
      } else if (centerGroupRef.current) {
        // Use center group if no editor is active
        position = { direction: 'right', referenceGroup: centerGroupRef.current }
      } else {
        // Fallback: to the right of filetree (but will be left of terminal)
        position = { direction: 'right', referencePanel: 'filetree' }
      }

      openFileAtPosition(path, position)
    },
    [dockApi, openFileAtPosition]
  )

  const openDiff = useCallback(
    (path, _status) => {
      if (!dockApi) return

      const panelId = `editor-${path}`
      const existingPanel = dockApi.getPanel(panelId)

      if (existingPanel) {
        // Update to diff mode and activate
        existingPanel.api.updateParameters({ initialMode: 'git-diff' })
        existingPanel.api.setActive()
        setActiveDiffFile(path)
        return
      }

      // Use empty panel's group first to maintain layout hierarchy
      const emptyPanel = dockApi.getPanel('empty-center')
      const shellPanel = dockApi.getPanel('shell')
      const centerGroup = centerGroupRef.current

      let position
      if (emptyPanel?.group) {
        position = { referenceGroup: emptyPanel.group }
      } else if (centerGroup) {
        position = { referenceGroup: centerGroup }
      } else if (shellPanel?.group) {
        position = { direction: 'above', referenceGroup: shellPanel.group }
      } else {
        position = { direction: 'right', referencePanel: 'filetree' }
      }

      // Open regular editor with diff mode enabled
      openFileAtPosition(path, position, { initialMode: 'git-diff' })
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
          minimumHeight: 200,
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

    const applyLockedPanels = () => {
      const filetreePanel = api.getPanel('filetree')
      const terminalPanel = api.getPanel('terminal')

      const filetreeGroup = filetreePanel?.group
      if (filetreeGroup) {
        filetreeGroup.locked = true
        filetreeGroup.header.hidden = true
        filetreeGroup.api.setConstraints({
          minimumWidth: 180,
          maximumWidth: Infinity,
        })
      }

      const terminalGroup = terminalPanel?.group
      if (terminalGroup) {
        terminalGroup.locked = true
        terminalGroup.header.hidden = true
        terminalGroup.api.setConstraints({
          minimumWidth: 250,
          maximumWidth: Infinity,
        })
      }

      const shellPanel = api.getPanel('shell')
      const shellGroup = shellPanel?.group
      if (shellGroup) {
        // Don't lock or hide header - shell has collapse button
        shellGroup.api.setConstraints({
          minimumHeight: 100,
          maximumHeight: Infinity,
        })
      }
    }

    const ensureCorePanels = () => {
      // Layout goal: [filetree | [editor / shell] | terminal]
      //
      // Strategy: Create in order that establishes correct hierarchy
      // 1. filetree (left)
      // 2. terminal (right) - agent sessions column
      // 3. empty-center (left of terminal) - center column for editors
      // 4. shell (below empty-center) - bottom of center

      let filetreePanel = api.getPanel('filetree')
      if (!filetreePanel) {
        filetreePanel = api.addPanel({
          id: 'filetree',
          component: 'filetree',
          title: 'Files',
          params: { onOpenFile: () => {} },
        })
      }

      // Add terminal (right of filetree) - establishes rightmost column
      let terminalPanel = api.getPanel('terminal')
      if (!terminalPanel) {
        terminalPanel = api.addPanel({
          id: 'terminal',
          component: 'terminal',
          title: 'Code Sessions',
          position: { direction: 'right', referencePanel: 'filetree' },
        })
      }

      // Add empty panel LEFT of terminal - creates center column
      let emptyPanel = api.getPanel('empty-center')
      if (!emptyPanel) {
        emptyPanel = api.addPanel({
          id: 'empty-center',
          component: 'empty',
          title: '',
          position: { direction: 'left', referencePanel: 'terminal' },
        })
      }
      // Always set centerGroupRef from empty panel if it exists
      if (emptyPanel?.group) {
        emptyPanel.group.header.hidden = true
        centerGroupRef.current = emptyPanel.group
        // Set minimum height for the center group (use Infinity to allow resize)
        emptyPanel.group.api.setConstraints({
          minimumHeight: 200,
          maximumHeight: Infinity,
        })
      }

      // Add shell panel BELOW the center group - splits only center column
      let shellPanel = api.getPanel('shell')
      if (!shellPanel && emptyPanel?.group) {
        shellPanel = api.addPanel({
          id: 'shell',
          component: 'shell',
          tabComponent: 'noClose',
          title: 'Shell',
          position: { direction: 'below', referenceGroup: emptyPanel.group },
          params: {
            collapsed: false,
            onToggleCollapse: () => {},
          },
        })
      }

      // Show tabs for the shell group
      if (shellPanel?.group) {
        shellPanel.group.header.hidden = false
        shellPanel.group.locked = true // Lock group to prevent closing tabs
      }

      // Set centerGroupRef from editor panels if any exist
      const panels = Array.isArray(api.panels)
        ? api.panels
        : typeof api.getPanels === 'function'
          ? api.getPanels()
          : []
      const editorPanels = panels.filter((panel) =>
        panel.id.startsWith('editor-'),
      )
      if (editorPanels.length > 0) {
        centerGroupRef.current = editorPanels[0].group
      }
      // centerGroupRef was already set above when creating empty-center if no editors

      applyLockedPanels()
    }

    // Check if there's a saved layout - if so, DON'T create panels here
    // Let the layout restoration effect handle it to avoid creating->destroying->recreating
    // We check localStorage directly since projectRoot isn't available yet
    let hasSavedLayout = false
    let invalidLayoutFound = false
    try {
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i)
        if (key && key.startsWith('kurt-web-') && key.endsWith('-layout')) {
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
              localStorage.removeItem('kurt-web-terminal-sessions')
              localStorage.removeItem('kurt-web-terminal-active')
              localStorage.removeItem('kurt-web-terminal-chat-interface')
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
        api.getGroup(shellGroup.id)?.api.setSize({ height: panelSizesRef.current.shell })
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
          minimumHeight: 200,
          maximumHeight: Infinity,
        })
      }
    })

    const saveLayoutNow = () => {
      if (typeof api.toJSON !== 'function') return
      // Use refs for stable access in event handlers
      saveLayout(storagePrefixRef.current, projectRootRef.current, api.toJSON(), layoutVersionRef.current)
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

      // Only save if not collapsed (width > 48 for sidebars, height > 36 for shell)
      if (filetreeGroup && filetreeGroup.api.width > 48) {
        if (newSizes.filetree !== filetreeGroup.api.width) {
          newSizes.filetree = filetreeGroup.api.width
          changed = true
        }
      }
      if (terminalGroup && terminalGroup.api.width > 48) {
        if (newSizes.terminal !== terminalGroup.api.width) {
          newSizes.terminal = terminalGroup.api.width
          changed = true
        }
      }
      if (shellGroup && shellGroup.api.height > 36) {
        if (newSizes.shell !== shellGroup.api.height) {
          newSizes.shell = shellGroup.api.height
          changed = true
        }
      }

      if (changed) {
        panelSizesRef.current = newSizes
        savePanelSizes(storagePrefixRef.current, newSizes)
      }
    }

    // Debounce layout saves to avoid excessive writes during drag operations
    const debouncedSaveLayout = debounce(saveLayoutNow, 300)
    const debouncedSavePanelSizes = debounce(savePanelSizesNow, 300)

    if (typeof api.onDidLayoutChange === 'function') {
      api.onDidLayoutChange(() => {
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

  // Fetch project root for copy path feature and project-specific storage
  useEffect(() => {
    const fetchProjectRoot = () => {
      fetch(buildApiUrl('/api/project'))
        .then((r) => r.json())
        .then((data) => {
          const root = data.root || ''
          projectRootRef.current = root
          setProjectRoot(root)
        })
        .catch(() => {
          // Retry on failure - server might not be ready yet
          setTimeout(fetchProjectRoot, 500)
        })
    }
    fetchProjectRoot()
  }, [])

  // Set browser tab title using config titleFormat
  useEffect(() => {
    const folderName = projectRoot ? projectRoot.split('/').filter(Boolean).pop() : null
    const titleFormat = config.branding?.titleFormat
    if (typeof titleFormat === 'function') {
      document.title = titleFormat({ folder: folderName, workspace: folderName })
    } else {
      // Fallback if titleFormat is not a function
      document.title = folderName
        ? `${folderName} - ${config.branding?.name || 'Boring UI'}`
        : config.branding?.name || 'Boring UI'
    }
  }, [projectRoot, config.branding])

  // Restore layout once projectRoot is loaded and dockApi is available
  const layoutRestorationRan = useRef(false)
  useEffect(() => {
    // Wait for both dockApi and projectRoot to be available
    // projectRoot === null means not loaded yet
    if (!dockApi || projectRoot === null || layoutRestorationRan.current) return
    layoutRestorationRan.current = true

    const savedLayout = loadLayout(storagePrefix, projectRoot, layoutVersion)
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
                ftApi.setConstraints({ minimumWidth: 48, maximumWidth: 48 })
                ftApi.setSize({ width: 48 })
              } else {
                ftApi.setConstraints({ minimumWidth: 180, maximumWidth: Infinity })
                ftApi.setSize({ width: panelSizesRef.current.filetree })
              }
            }
          }
          if (tGroup) {
            const tApi = dockApi.getGroup(tGroup.id)?.api
            if (tApi) {
              if (collapsed.terminal) {
                tApi.setConstraints({ minimumWidth: 48, maximumWidth: 48 })
                tApi.setSize({ width: 48 })
              } else {
                tApi.setConstraints({ minimumWidth: 250, maximumWidth: Infinity })
                tApi.setSize({ width: panelSizesRef.current.terminal })
              }
            }
          }
          if (sGroup) {
            const sApi = dockApi.getGroup(sGroup.id)?.api
            if (sApi) {
              if (collapsed.shell) {
                sApi.setConstraints({ minimumHeight: 36, maximumHeight: 36 })
                sApi.setSize({ height: 36 })
              } else {
                sApi.setConstraints({ minimumHeight: 100, maximumHeight: Infinity })
                sApi.setSize({ height: panelSizesRef.current.shell })
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
            minimumHeight: 100,
            maximumHeight: Infinity,
          })
        }

        // If layout has editor panels, close empty-center
        const panels = Array.isArray(dockApi.panels)
          ? dockApi.panels
          : typeof dockApi.getPanels === 'function'
            ? dockApi.getPanels()
            : []
        const hasEditors = panels.some((p) => p.id.startsWith('editor-'))
        const hasReviews = panels.some((p) => p.id.startsWith('review-'))
        if (hasEditors || hasReviews) {
          const emptyPanel = dockApi.getPanel('empty-center')
          if (emptyPanel) {
            const editorPanel = panels.find((p) => p.id.startsWith('editor-') || p.id.startsWith('review-'))
            if (editorPanel?.group) {
              centerGroupRef.current = editorPanel.group
            }
            emptyPanel.api.close()
          }
        }

        // Update centerGroupRef if there's an empty-center panel
        const emptyPanel = dockApi.getPanel('empty-center')
        if (emptyPanel?.group) {
          centerGroupRef.current = emptyPanel.group
          // Set minimum height for the center group (use Infinity to allow resize)
          emptyPanel.group.api.setConstraints({
            minimumHeight: 200,
            maximumHeight: Infinity,
          })
        }

        // Prune empty groups
        const pruned = pruneEmptyGroups(dockApi)
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
                ftApi.setConstraints({ minimumWidth: 48, maximumWidth: 48 })
                ftApi.setSize({ width: 48 })
              } else {
                ftApi.setConstraints({ minimumWidth: 180, maximumWidth: Infinity })
                ftApi.setSize({ width: panelSizesRef.current.filetree })
              }
            }
          }
          if (tGroup) {
            const tApi = dockApi.getGroup(tGroup.id)?.api
            if (tApi) {
              if (collapsed.terminal) {
                tApi.setConstraints({ minimumWidth: 48, maximumWidth: 48 })
                tApi.setSize({ width: 48 })
              } else {
                tApi.setConstraints({ minimumWidth: 250, maximumWidth: Infinity })
                tApi.setSize({ width: panelSizesRef.current.terminal })
              }
            }
          }
          if (sGroup) {
            const sApi = dockApi.getGroup(sGroup.id)?.api
            if (sApi) {
              if (collapsed.shell) {
                sApi.setConstraints({ minimumHeight: 36, maximumHeight: 36 })
                sApi.setSize({ height: 36 })
              } else {
                sApi.setConstraints({ minimumHeight: 100, maximumHeight: Infinity })
                sApi.setSize({ height: panelSizesRef.current.shell })
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
  }, [dockApi, projectRoot, storagePrefix, collapsed.filetree, collapsed.terminal, collapsed.shell])

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
    </ThemeProvider>
  )
}
