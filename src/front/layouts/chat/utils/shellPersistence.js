/**
 * shellPersistence — Persist and restore chat-centered shell state via
 * localStorage.
 *
 * Uses its own storage keys, completely separate from the legacy DockView
 * layout persistence in LayoutManager.js. This ensures the two systems
 * cannot interfere with each other during the migration period.
 *
 * Artifact persistence saves metadata only (kind, title, renderer, params).
 * File content is always fetched live from the file API — we never cache
 * file bodies in localStorage.
 *
 * @module shell/shellPersistence
 */

const SHELL_KEY = 'boring-ui:chat-shell:v1'
const ARTIFACT_KEY = 'boring-ui:chat-shell-artifacts:v1'
const SURFACE_LAYOUT_KEY = 'boring-ui:chat-shell-surface-layout:v1'

/**
 * Save core shell layout state to localStorage.
 *
 * @param {object} state
 * @param {boolean}      state.surfaceCollapsed   - Whether surface is collapsed
 * @param {number}       state.surfaceWidth       - Current surface panel width in px
 * @param {number}       state.surfaceSidebarWidth - Current workbench sidebar width in px
 * @param {string|null}  state.activeDestination  - Active nav-rail destination
 */
export function saveShellState(state) {
  try {
    localStorage.setItem(SHELL_KEY, JSON.stringify({
      surfaceCollapsed: state.surfaceCollapsed,
      surfaceWidth: state.surfaceWidth,
      surfaceSidebarWidth: state.surfaceSidebarWidth,
      activeDestination: state.activeDestination,
    }))
  } catch {
    // Swallow — persistence is best-effort
  }
}

/**
 * Load previously saved shell layout state.
 *
 * @returns {object|null} The saved state, or null if nothing was stored / parse failed.
 */
export function loadShellState() {
  try {
    const raw = localStorage.getItem(SHELL_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

/**
 * Save artifact metadata (tab state) to localStorage.
 *
 * Only serializes the metadata needed to reconstruct tabs — not file content.
 *
 * @param {Map}      artifacts  - id -> SurfaceArtifact map
 * @param {string[]} orderedIds - Ordered artifact IDs (tab order)
 * @param {string|null} activeId - Currently active artifact ID
 */
export function saveArtifactState(artifacts, orderedIds, activeId) {
  try {
    // Save artifact metadata (not content -- that's fetched from file API)
    const serializable = orderedIds.map((id) => {
      const a = artifacts.get(id)
      if (!a) return null
      return {
        id: a.id,
        canonicalKey: a.canonicalKey,
        kind: a.kind,
        title: a.title,
        source: a.source,
        rendererKey: a.rendererKey,
        params: a.params,
      }
    }).filter(Boolean)
    localStorage.setItem(ARTIFACT_KEY, JSON.stringify({ artifacts: serializable, activeId }))
  } catch {
    // Swallow — persistence is best-effort
  }
}

/**
 * Load previously saved artifact metadata.
 *
 * @returns {{ artifacts: object[], activeId: string|null }|null}
 */
export function loadArtifactState() {
  try {
    const raw = localStorage.getItem(ARTIFACT_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

/**
 * Save Dockview surface layout JSON.
 *
 * @param {object|null} layout - Serialized Dockview layout from api.toJSON()
 */
export function saveSurfaceLayout(layout) {
  try {
    if (!layout) {
      localStorage.removeItem(SURFACE_LAYOUT_KEY)
      return
    }
    localStorage.setItem(SURFACE_LAYOUT_KEY, JSON.stringify(layout))
  } catch {
    // Swallow — persistence is best-effort
  }
}

/**
 * Load previously saved Dockview surface layout.
 *
 * @returns {object|null}
 */
export function loadSurfaceLayout() {
  try {
    const raw = localStorage.getItem(SURFACE_LAYOUT_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

/**
 * Clear all chat-shell persistence data (both shell layout and artifacts).
 */
export function clearShellState() {
  try {
    localStorage.removeItem(SHELL_KEY)
    localStorage.removeItem(ARTIFACT_KEY)
    localStorage.removeItem(SURFACE_LAYOUT_KEY)
  } catch {
    // Swallow — persistence is best-effort
  }
}
