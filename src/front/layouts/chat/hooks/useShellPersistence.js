/**
 * useShellPersistence — Auto-saves shell state on change and restores
 * on mount, using the shellPersistence localStorage layer.
 *
 * Restoration runs exactly once (guarded by a ref). Saves are debounced
 * at 500ms to avoid thrashing localStorage on rapid resize / toggle events.
 *
 * NOTE: activeDestination is intentionally NOT restored — the browse
 * drawer should always start closed on page load.
 *
 * @module shell/useShellPersistence
 */

import { useEffect, useRef } from 'react'
import {
  saveShellState,
  loadShellState,
  saveArtifactState,
  loadArtifactState,
  saveSurfaceLayout,
  loadSurfaceLayout,
} from '../utils/shellPersistence'

/**
 * @param {object} params
 * @param {boolean}       params.surfaceCollapsed   - Current collapsed state
 * @param {Function}      params.setSurfaceCollapsed - Setter for collapsed state
 * @param {number}        params.surfaceWidth       - Current surface width in px
 * @param {Function}      params.setSurfaceWidth    - Setter for surface width
 * @param {number}        params.surfaceSidebarWidth - Current workbench sidebar width in px
 * @param {Function}      params.setSurfaceSidebarWidth - Setter for sidebar width
 * @param {string|null}   params.activeDestination  - Active nav-rail destination
 * @param {Map}           params.artifacts          - id -> SurfaceArtifact map
 * @param {string[]}      params.orderedIds         - Ordered artifact IDs
 * @param {string|null}   params.activeArtifactId   - Currently active artifact ID
 * @param {Function}      params.openArtifact       - Function to open/restore an artifact
 * @param {Function}      [params.focusArtifact]    - Function to focus a restored artifact
 * @param {object|null}   [params.surfaceLayout]    - Serialized Dockview layout
 * @param {Function}      [params.setSurfaceLayout] - Setter for restored layout
 */
export function useShellPersistence({
  surfaceCollapsed,
  setSurfaceCollapsed,
  surfaceWidth,
  setSurfaceWidth,
  surfaceSidebarWidth,
  setSurfaceSidebarWidth,
  activeDestination,
  artifacts,
  orderedIds,
  activeArtifactId,
  openArtifact,
  focusArtifact,
  surfaceLayout,
  setSurfaceLayout,
}) {
  const restoredRef = useRef(false)

  // Restore on mount (once)
  useEffect(() => {
    if (restoredRef.current) return
    restoredRef.current = true

    const shell = loadShellState()
    if (shell) {
      if (shell.surfaceCollapsed != null) setSurfaceCollapsed(shell.surfaceCollapsed)
      const restoredSurfaceWidth = Number.isFinite(shell.surfaceWidth)
        ? shell.surfaceWidth
        : surfaceWidth
      if (Number.isFinite(shell.surfaceWidth)) setSurfaceWidth(shell.surfaceWidth)
      if (Number.isFinite(shell.surfaceSidebarWidth)) {
        const maxSidebarWidth = Math.max(240, Math.min(420, restoredSurfaceWidth - 260))
        setSurfaceSidebarWidth(
          Math.min(maxSidebarWidth, Math.max(240, shell.surfaceSidebarWidth)),
        )
      }
      // Don't restore activeDestination (drawer should start closed)
    }

    const artifactState = loadArtifactState()
    if (artifactState?.artifacts) {
      for (const a of artifactState.artifacts) {
        openArtifact({ ...a, status: 'ready', createdAt: Date.now() })
      }
      if (artifactState.activeId && typeof focusArtifact === 'function') {
        focusArtifact(artifactState.activeId)
      }
    }

    if (typeof setSurfaceLayout === 'function') {
      const savedSurfaceLayout = loadSurfaceLayout()
      if (savedSurfaceLayout) {
        setSurfaceLayout(savedSurfaceLayout)
      }
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Save shell layout on changes (debounced)
  useEffect(() => {
    const timer = setTimeout(() => {
      saveShellState({
        surfaceCollapsed,
        surfaceWidth,
        surfaceSidebarWidth,
        activeDestination,
      })
    }, 500)
    return () => clearTimeout(timer)
  }, [surfaceCollapsed, surfaceWidth, surfaceSidebarWidth, activeDestination])

  // Save artifact metadata on changes (debounced)
  useEffect(() => {
    const timer = setTimeout(() => {
      saveArtifactState(artifacts, orderedIds, activeArtifactId)
    }, 500)
    return () => clearTimeout(timer)
  }, [artifacts, orderedIds, activeArtifactId])

  // Save surface split/tab layout on changes (debounced)
  useEffect(() => {
    const timer = setTimeout(() => {
      saveSurfaceLayout(surfaceLayout)
    }, 500)
    return () => clearTimeout(timer)
  }, [surfaceLayout])
}
