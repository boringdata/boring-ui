import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react'
import { DockviewReact } from 'dockview-react'
import 'dockview-react/dist/styles/dockview.css'
import { UnifiedDockTab, tabComponents } from '../../shared/components/DockTab'

// Lazy-load EditorPanel to avoid pulling in heavy deps at Surface mount time
const EditorPanel = React.lazy(() => import('../../shared/panels/EditorPanel'))

/**
 * EditorPanelWrapper — Adapts DockviewReact panel props to EditorPanel props.
 *
 * DockviewReact passes { params, api } where `params` is the user-supplied
 * params object from addPanel.  EditorPanel expects the same shape.
 */
function EditorPanelWrapper({ params, api }) {
  return (
    <React.Suspense fallback={<div className="sf-panel-loading">Loading...</div>}>
      <EditorPanel params={params} api={api} />
    </React.Suspense>
  )
}

const DOCKVIEW_COMPONENTS = {
  editor: EditorPanelWrapper,
}

function collectDockPanelIds(api) {
  const panelCollection = api?.panels

  if (Array.isArray(panelCollection)) {
    return panelCollection
      .map((panel) => panel?.id)
      .filter((id) => typeof id === 'string' && id.length > 0)
  }

  if (panelCollection instanceof Map) {
    return Array.from(panelCollection.keys()).filter((id) => typeof id === 'string' && id.length > 0)
  }

  return []
}

/**
 * SurfaceDockview — Wraps a DockviewReact instance inside the Surface island.
 *
 * Responsibilities:
 * - Mount DockviewReact with suppressed native chrome (our SurfaceShell top bar
 *   handles tabs; Dockview's native tab bar is hidden via CSS).
 * - Each artifact gets a panel with EditorPanel as its component.
 * - Sync artifact open/focus/close with Dockview addPanel/setActivePanel/removePanel.
 * - When user drags tabs to split inside Dockview, it creates side-by-side views.
 * - Emit onLayoutChange when the layout serialization changes.
 *
 * Props:
 *   artifacts         - array of SurfaceArtifact objects
 *   activeArtifactId  - currently active artifact ID
 *   onSelectArtifact  - (id: string) => void
 *   onCloseArtifact   - (id: string) => void
 *   onLayoutChange    - (layout: object) => void  (optional, for persistence)
 */
export default function SurfaceDockview({
  artifacts = [],
  activeArtifactId = null,
  onSelectArtifact,
  onCloseArtifact,
  layout = null,
  onLayoutChange,
}) {
  // Use state (not ref) so that setting the API triggers re-render and
  // the artifact-sync effect runs once the API is available.
  const [dockApi, setDockApi] = useState(null)
  // Track which artifact IDs are currently represented as Dockview panels
  const panelIdsRef = useRef(new Set())
  // Suppress callbacks during programmatic sync
  const syncingRef = useRef(false)
  const restoredLayoutRef = useRef(false)

  // Build a stable set of artifact IDs for diffing
  const artifactIds = useMemo(() => artifacts.map((a) => a.id), [artifacts])
  const artifactMap = useMemo(() => {
    const m = new Map()
    for (const a of artifacts) m.set(a.id, a)
    return m
  }, [artifacts])

  // Store callback refs so event listeners can use latest values
  const onSelectRef = useRef(onSelectArtifact)
  const onCloseRef = useRef(onCloseArtifact)
  const onLayoutRef = useRef(onLayoutChange)
  useEffect(() => { onSelectRef.current = onSelectArtifact }, [onSelectArtifact])
  useEffect(() => { onCloseRef.current = onCloseArtifact }, [onCloseArtifact])
  useEffect(() => { onLayoutRef.current = onLayoutChange }, [onLayoutChange])

  // --- Restore persisted Dockview split layout once after ready ---
  useEffect(() => {
    if (!dockApi || !layout || restoredLayoutRef.current) return
    if (typeof dockApi.fromJSON !== 'function') return

    syncingRef.current = true
    try {
      dockApi.fromJSON(layout)
      panelIdsRef.current = new Set(collectDockPanelIds(dockApi))
      restoredLayoutRef.current = true
    } catch {
      // Ignore malformed layout snapshots and let artifact sync rebuild a safe default.
    } finally {
      syncingRef.current = false
    }
  }, [dockApi, layout])

  // --- Dockview ready handler ---
  const handleReady = useCallback((event) => {
    const api = event.api

    // Listen for active panel changes originating from user interaction
    api.onDidActivePanelChange(() => {
      if (syncingRef.current) return
      const active = api.activePanel
      if (active && onSelectRef.current) {
        onSelectRef.current(active.id)
      }
    })

    // Listen for panel removal from Dockview (e.g., drag-close)
    api.onDidRemovePanel((panel) => {
      panelIdsRef.current.delete(panel.id)
      if (!syncingRef.current && onCloseRef.current) {
        onCloseRef.current(panel.id)
      }
    })

    // Listen for layout changes (for persistence)
    api.onDidLayoutChange(() => {
      if (syncingRef.current) return
      try {
        const layout = api.toJSON()
        if (onLayoutRef.current) onLayoutRef.current(layout)
      } catch {
        // toJSON can throw if layout is mid-update
      }
    })

    // Setting state triggers re-render so artifact-sync effects can run
    setDockApi(api)
  }, [])

  // --- Sync artifacts -> Dockview panels ---
  useEffect(() => {
    if (!dockApi) return

    syncingRef.current = true

    try {
      const currentPanelIds = panelIdsRef.current
      const desiredIds = new Set(artifactIds)

      // Add new panels for artifacts not yet in Dockview
      for (const id of artifactIds) {
        if (!currentPanelIds.has(id)) {
          const artifact = artifactMap.get(id)
          if (!artifact) continue

          try {
            dockApi.addPanel({
              id,
              component: 'editor',
              title: artifact.title || 'Untitled',
              params: {
                path: artifact.params?.path || '',
                ...artifact.params,
              },
            })
            currentPanelIds.add(id)
          } catch {
            // Panel already exists (race condition guard)
          }
        }
      }

      // Remove panels that are no longer in the artifact list
      for (const id of currentPanelIds) {
        if (!desiredIds.has(id)) {
          try {
            const panel = dockApi.getPanel(id)
            if (panel) {
              dockApi.removePanel(panel)
            }
          } catch {
            // Panel already removed
          }
          currentPanelIds.delete(id)
        }
      }
    } finally {
      syncingRef.current = false
    }
  }, [dockApi, artifactIds, artifactMap])

  // --- Sync active artifact -> Dockview focus ---
  useEffect(() => {
    if (!dockApi || !activeArtifactId) return

    syncingRef.current = true
    try {
      const panel = dockApi.getPanel(activeArtifactId)
      if (panel) {
        panel.api.setActive()
      }
    } catch {
      // Panel not yet added
    } finally {
      syncingRef.current = false
    }
  }, [dockApi, activeArtifactId])

  return (
    <div className="surface-dockview" data-testid="surface-dockview">
      <DockviewReact
        components={DOCKVIEW_COMPONENTS}
        tabComponents={tabComponents}
        defaultTabComponent={UnifiedDockTab}
        onReady={handleReady}
        className="dockview-theme-abyss surface-dockview-instance"
      />
    </div>
  )
}
