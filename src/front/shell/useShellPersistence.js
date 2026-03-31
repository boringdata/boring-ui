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
} from './shellPersistence'

/**
 * @param {object} params
 * @param {boolean}       params.surfaceCollapsed   - Current collapsed state
 * @param {Function}      params.setSurfaceCollapsed - Setter for collapsed state
 * @param {number}        params.surfaceWidth       - Current surface width in px
 * @param {Function}      params.setSurfaceWidth    - Setter for surface width
 * @param {string|null}   params.activeDestination  - Active nav-rail destination
 * @param {Function}      params.setActiveDestination - Setter for active destination
 * @param {Map}           params.artifacts          - id -> SurfaceArtifact map
 * @param {string[]}      params.orderedIds         - Ordered artifact IDs
 * @param {string|null}   params.activeArtifactId   - Currently active artifact ID
 * @param {Function}      params.openArtifact       - Function to open/restore an artifact
 */
export function useShellPersistence({
  surfaceCollapsed,
  setSurfaceCollapsed,
  surfaceWidth,
  setSurfaceWidth,
  activeDestination,
  setActiveDestination,
  artifacts,
  orderedIds,
  activeArtifactId,
  openArtifact,
}) {
  const restoredRef = useRef(false)

  // Restore on mount (once)
  useEffect(() => {
    if (restoredRef.current) return
    restoredRef.current = true

    const shell = loadShellState()
    if (shell) {
      if (shell.surfaceCollapsed != null) setSurfaceCollapsed(shell.surfaceCollapsed)
      if (shell.surfaceWidth) setSurfaceWidth(shell.surfaceWidth)
      // Don't restore activeDestination (drawer should start closed)
    }

    const artifactState = loadArtifactState()
    if (artifactState?.artifacts) {
      for (const a of artifactState.artifacts) {
        openArtifact({ ...a, status: 'ready', createdAt: Date.now() })
      }
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Save shell layout on changes (debounced)
  useEffect(() => {
    const timer = setTimeout(() => {
      saveShellState({ surfaceCollapsed, surfaceWidth, activeDestination })
    }, 500)
    return () => clearTimeout(timer)
  }, [surfaceCollapsed, surfaceWidth, activeDestination])

  // Save artifact metadata on changes (debounced)
  useEffect(() => {
    const timer = setTimeout(() => {
      saveArtifactState(artifacts, orderedIds, activeArtifactId)
    }, 500)
    return () => clearTimeout(timer)
  }, [artifacts, orderedIds, activeArtifactId])
}
