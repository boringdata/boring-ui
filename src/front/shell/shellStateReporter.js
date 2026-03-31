/**
 * shellStateReporter — Produces a flat snapshot of the chat-centered shell
 * state for the backend / agent frontend-state system.
 *
 * The snapshot mirrors the key signals the agent needs to understand the
 * current UI layout: which rail destination is active, whether the browse
 * drawer is open, whether the surface is expanded/collapsed, and which
 * artifacts / session are active.
 *
 * @module shell/shellStateReporter
 */

/**
 * Build a flat key/value snapshot from the current shell state.
 *
 * @param {object} shellState
 * @param {string|null}  shellState.activeDestination  - Current nav-rail destination (e.g. 'sessions', 'workspace') or null
 * @param {boolean}      shellState.drawerOpen         - Whether the browse drawer is visible
 * @param {string}       shellState.drawerMode         - Drawer content mode ('sessions' | 'workspace')
 * @param {boolean}      shellState.surfaceCollapsed   - Whether the surface panel is collapsed
 * @param {string|null}  shellState.activeArtifactId   - ID of the currently-focused artifact
 * @param {string[]}     shellState.orderedArtifactIds - Ordered list of open artifact IDs
 * @param {string|null}  shellState.activeSessionId    - Current chat session ID
 * @returns {Record<string, unknown>}
 */
export function createShellStateSnapshot(shellState) {
  return {
    'shell.mode': 'chat-centered',
    'shell.rail_destination': shellState.activeDestination || 'none',
    'browse.open': shellState.drawerOpen,
    'browse.mode': shellState.drawerMode || 'sessions',
    'surface.open': !shellState.surfaceCollapsed,
    'surface.collapsed': shellState.surfaceCollapsed,
    'surface.active_artifact_id': shellState.activeArtifactId,
    'surface.open_artifacts': shellState.orderedArtifactIds,
    'chat.active_session_id': shellState.activeSessionId,
  }
}
