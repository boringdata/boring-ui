/**
 * Tracks the active Dockview panel for UI synchronization.
 *
 * Extracted from App.jsx lines 1354-1377. When the active panel changes:
 * - If it's an editor panel: updates activeFile, activeDiffFile, and URL
 * - Otherwise: clears active file state and URL doc param
 */

import { useEffect } from 'react'

/**
 * Tracks active panel and synchronizes file state and URL.
 *
 * @param {Object} options
 * @param {Object|null} options.dockApi - Dockview API instance
 * @param {Function} options.setActiveFile - Active file setter
 * @param {Function} options.setActiveDiffFile - Active diff file setter
 */
export function useActivePanel({ dockApi, setActiveFile, setActiveDiffFile }) {
  useEffect(() => {
    if (!dockApi) return

    const disposable = dockApi.onDidActivePanelChange((panel) => {
      if (panel && panel.id && panel.id.startsWith('editor-')) {
        const path = panel.id.replace('editor-', '')
        setActiveFile(path)
        setActiveDiffFile(path)
        // Sync URL for easy sharing/reload
        const url = new URL(window.location.href)
        url.searchParams.set('doc', path)
        window.history.replaceState({}, '', url)
      } else {
        setActiveFile(null)
        setActiveDiffFile(null)
        const url = new URL(window.location.href)
        url.searchParams.delete('doc')
        window.history.replaceState({}, '', url)
      }
    })

    return () => disposable.dispose()
  }, [dockApi, setActiveFile, setActiveDiffFile])
}
