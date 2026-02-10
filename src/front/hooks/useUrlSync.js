/**
 * Restores document from URL ?doc= query param on initial load.
 *
 * Waits for dockApi, projectRoot, and core panels before opening.
 *
 * @module hooks/useUrlSync
 */

import { useEffect, useRef } from 'react'

/**
 * @param {Object} options
 * @param {Object|null} options.dockApi - Dockview API
 * @param {string|null} options.projectRoot - Current project root
 * @param {Function} options.openFile
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
      setTimeout(() => {
        openFile(docPath)
      }, 150)
    }
  }, [dockApi, projectRoot, openFile])
}
