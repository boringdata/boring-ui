/**
 * Tab state management with localStorage persistence.
 *
 * Extracted from App.jsx tab-related state (line 100) and effects
 * (lines 1440-1466). Manages the open file tab map, active file tracking,
 * tab restoration from storage, and tab persistence on change.
 */

import { useState, useRef, useEffect } from 'react'
import { loadSavedTabs, saveTabs } from '../layout'

/**
 * Manages tab state with localStorage persistence.
 *
 * Tabs are stored as an object mapping file path to { content, isDirty }.
 * Tab paths are persisted to localStorage via layout helpers.
 *
 * @param {Object} options
 * @param {string} options.storagePrefix - Prefix for localStorage keys
 * @param {string|null} options.projectRoot - Project root path (null = not loaded)
 * @param {Object|null} options.dockApi - Dockview API instance
 * @param {Object} options.layoutRestored - Ref indicating layout was restored from saved state
 * @param {Object} options.isInitialized - Ref indicating app is initialized
 * @param {Function} [options.openFile] - Callback to open a file in the editor
 * @returns {Object} Tab state, setters, and active file tracking
 */
export function useTabManager({
  storagePrefix,
  projectRoot,
  dockApi,
  layoutRestored,
  isInitialized,
  openFile,
}) {
  const [tabs, setTabs] = useState({})
  const [activeFile, setActiveFile] = useState(null)
  const [activeDiffFile, setActiveDiffFile] = useState(null)
  const hasRestoredTabs = useRef(false)

  // Restore tabs from localStorage
  useEffect(() => {
    if (!dockApi || projectRoot === null || hasRestoredTabs.current) return
    hasRestoredTabs.current = true

    if (layoutRestored?.current) {
      return
    }

    const savedPaths = loadSavedTabs(storagePrefix, projectRoot)
    if (savedPaths.length > 0 && typeof openFile === 'function') {
      setTimeout(() => {
        savedPaths.forEach((path) => {
          openFile(path)
        })
      }, 50)
    }
  }, [dockApi, projectRoot, openFile, storagePrefix, layoutRestored])

  // Persist tabs to localStorage on change
  useEffect(() => {
    if (!isInitialized?.current || projectRoot === null) return
    const paths = Object.keys(tabs)
    saveTabs(storagePrefix, projectRoot, paths)
  }, [tabs, projectRoot, storagePrefix, isInitialized])

  return {
    tabs,
    setTabs,
    activeFile,
    setActiveFile,
    activeDiffFile,
    setActiveDiffFile,
    hasRestoredTabs,
  }
}
