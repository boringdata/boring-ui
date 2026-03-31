import { useEffect, useRef } from 'react'
import { bridgeToolResultToArtifact, bridgeOpenPanelToArtifact } from './toolArtifactBridge'

/**
 * Bridge key names on the window object.
 *
 * These replace the older PI_OPEN_FILE_BRIDGE and PI_OPEN_PANEL_BRIDGE
 * constants from `providers/pi/uiBridge.js`. The new shell routes everything
 * through the artifact controller instead of opening Dockview panels directly.
 */
export const SURFACE_OPEN_FILE_BRIDGE = '__SURFACE_OPEN_FILE__'
export const SURFACE_OPEN_PANEL_BRIDGE = '__SURFACE_OPEN_PANEL__'

/**
 * useToolBridge — Sets up window-level bridge functions that PI agent tools call
 * to open files and panels in the Surface.
 *
 * When a tool calls `window.__SURFACE_OPEN_FILE__(path)`, the bridge creates a
 * SurfaceArtifact via `bridgeToolResultToArtifact` and opens it through the
 * artifact controller. This replaces the old `PI_OPEN_FILE_BRIDGE` that opened
 * files directly in Dockview editor panels.
 *
 * @param {object} options
 * @param {function} options.openArtifact - The artifact controller's `open` function
 * @param {string} [options.activeSessionId] - Current session ID for provenance
 */
export function useToolBridge({ openArtifact, activeSessionId = null }) {
  const openArtifactRef = useRef(openArtifact)
  const sessionIdRef = useRef(activeSessionId)

  // Keep refs current without re-registering bridge functions
  useEffect(() => {
    openArtifactRef.current = openArtifact
  }, [openArtifact])

  useEffect(() => {
    sessionIdRef.current = activeSessionId
  }, [activeSessionId])

  useEffect(() => {
    /**
     * Open a file as a code artifact in the Surface.
     * Called by the `open_file` tool in defaultTools.js.
     */
    const openFile = (path) => {
      if (!path || typeof path !== 'string') return
      const trimmedPath = path.trim()
      if (!trimmedPath) return

      const { shouldOpen, artifact } = bridgeToolResultToArtifact(
        'open_file',
        { path: trimmedPath },
        {},
        sessionIdRef.current,
      )

      if (shouldOpen && artifact && openArtifactRef.current) {
        openArtifactRef.current(artifact)
      }
    }

    /**
     * Open an arbitrary panel as an artifact in the Surface.
     * Accepts { type, params } where type maps to an artifact kind.
     */
    const openPanel = (payload) => {
      if (!payload || typeof payload !== 'object') return

      const { shouldOpen, artifact } = bridgeOpenPanelToArtifact(
        payload,
        sessionIdRef.current,
      )

      if (shouldOpen && artifact && openArtifactRef.current) {
        openArtifactRef.current(artifact)
      }
    }

    window[SURFACE_OPEN_FILE_BRIDGE] = openFile
    window[SURFACE_OPEN_PANEL_BRIDGE] = openPanel

    return () => {
      if (window[SURFACE_OPEN_FILE_BRIDGE] === openFile) {
        delete window[SURFACE_OPEN_FILE_BRIDGE]
      }
      if (window[SURFACE_OPEN_PANEL_BRIDGE] === openPanel) {
        delete window[SURFACE_OPEN_PANEL_BRIDGE]
      }
    }
  }, []) // Empty deps — refs handle value updates
}
