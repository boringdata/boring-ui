/**
 * useShellStatePublisher — Publishes the chat-centered shell state to the
 * existing frontend-state system on every change.
 *
 * Currently dispatches a CustomEvent on `window` so that any listener
 * (including the backend-state sync layer) can pick up the latest shell
 * snapshot without tight coupling. A follow-up phase will wire this into
 * the formal `frontendState.js` reporting pipeline.
 *
 * @module shell/useShellStatePublisher
 */

import { useEffect } from 'react'
import { createShellStateSnapshot } from './shellStateReporter'

/**
 * Publishes the current shell state as a `boring-ui:shell-state` CustomEvent
 * whenever any of the tracked values change.
 *
 * @param {object} params
 * @param {string|null}  params.activeDestination - Current nav-rail destination
 * @param {boolean}      params.drawerOpen        - Whether the browse drawer is visible
 * @param {boolean}      params.surfaceCollapsed  - Whether the surface panel is collapsed
 * @param {string|null}  params.activeArtifactId  - ID of the currently-focused artifact
 * @param {string[]}     params.orderedIds        - Ordered list of open artifact IDs
 * @param {string|null}  params.activeSessionId   - Current chat session ID
 */
export function useShellStatePublisher({
  activeDestination,
  drawerOpen,
  surfaceCollapsed,
  activeArtifactId,
  orderedIds,
  activeSessionId,
}) {
  useEffect(() => {
    // Build the snapshot from current shell state
    const snapshot = createShellStateSnapshot({
      activeDestination,
      drawerOpen,
      drawerMode: 'sessions',
      surfaceCollapsed,
      activeArtifactId,
      orderedArtifactIds: orderedIds,
      activeSessionId,
    })

    // Backward compat: dispatch as CustomEvent for loose coupling
    try {
      const event = new CustomEvent('boring-ui:shell-state', { detail: snapshot })
      window.dispatchEvent(event)
    } catch {
      // Swallow — dispatching is best-effort
    }
  }, [activeDestination, drawerOpen, surfaceCollapsed, activeArtifactId, orderedIds, activeSessionId])
}
