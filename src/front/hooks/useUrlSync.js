/**
 * Restores document from URL query parameter on load.
 *
 * Extracted from App.jsx lines 1468-1486. When dockApi and projectRoot
 * are available and core panels exist, opens the file specified by the
 * ?doc= query parameter.
 */

import { useEffect, useRef } from 'react'

/**
 * Restores file from URL ?doc= query parameter on initial load.
 *
 * @param {Object} options
 * @param {Object|null} options.dockApi - Dockview API instance
 * @param {string|null} options.projectRoot - Project root path (null = not loaded)
 * @param {Function} options.openFile - File open callback
 */
export function useUrlSync({ dockApi, projectRoot, openFile }) {
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
}
