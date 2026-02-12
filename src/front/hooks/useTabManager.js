/**
 * Tab save/restore for editor persistence across sessions.
 *
 * - Restores saved tab paths when layout isn't restored from JSON
 * - Saves open tab paths to localStorage on every change
 *
 * @module hooks/useTabManager
 */

import { useEffect, useRef } from 'react'
import { loadSavedTabs, saveTabs } from '../layout'

/**
 * @param {Object} options
 * @param {Object|null} options.dockApi - Dockview API
 * @param {string|null} options.projectRoot - Current project root
 * @param {string} options.storagePrefix - localStorage key prefix
 * @param {Object} options.tabs - Current tab state { [path]: { content, isDirty } }
 * @param {Function} options.openFile
 * @param {Object} options.isInitialized - Ref: whether dock is initialized
 * @param {Object} options.layoutRestored - Ref: whether layout was restored from JSON
 */
export function useTabManager({
  dockApi,
  projectRoot,
  storagePrefix,
  tabs,
  openFile,
  isInitialized,
  layoutRestored,
}) {
  // Restore saved tabs when dockApi and projectRoot become available
  const hasRestoredTabs = useRef(false)
  useEffect(() => {
    if (!dockApi || projectRoot === null || hasRestoredTabs.current) return
    hasRestoredTabs.current = true

    if (layoutRestored.current) return

    const savedPaths = loadSavedTabs(storagePrefix, projectRoot)
    if (savedPaths.length > 0) {
      setTimeout(() => {
        savedPaths.forEach((path) => {
          openFile(path)
        })
      }, 50)
    }
  }, [dockApi, projectRoot, openFile, storagePrefix])

  // Save open tabs to localStorage whenever tabs change
  useEffect(() => {
    if (!isInitialized.current || projectRoot === null) return
    const paths = Object.keys(tabs)
    saveTabs(storagePrefix, projectRoot, paths)
  }, [tabs, projectRoot, storagePrefix])
}
