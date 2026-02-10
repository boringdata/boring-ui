/**
 * Tracks the active panel in dockview and syncs URL + state.
 *
 * When an editor panel becomes active, updates activeFile/activeDiffFile
 * and pushes the file path to the URL ?doc= param.
 *
 * @module hooks/useActivePanel
 */

import { useEffect } from 'react'

/**
 * @param {Object} options
 * @param {Object|null} options.dockApi - Dockview API
 * @param {Function} options.setActiveFile
 * @param {Function} options.setActiveDiffFile
 */
export function useActivePanel({ dockApi, setActiveFile, setActiveDiffFile }) {
  useEffect(() => {
    if (!dockApi) return
    const disposable = dockApi.onDidActivePanelChange((panel) => {
      if (panel && panel.id && panel.id.startsWith('editor-')) {
        const path = panel.id.replace('editor-', '')
        setActiveFile(path)
        setActiveDiffFile(path)
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
  }, [dockApi])
}
