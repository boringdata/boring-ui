/**
 * Dockview initialization handler.
 *
 * Returns the `onReady` callback for DockviewReact that sets up:
 * - Core panel creation (or defers to layout restoration)
 * - Panel lifecycle handlers (remove cleanup, empty-center restore)
 * - Layout and panel size persistence with debouncing
 * - Minimum constraint enforcement
 *
 * @module hooks/useLayoutInit
 */

import { useCallback } from 'react'
import {
  applyLockedPanels as applyLockedPanelsUtil,
  ensureCorePanels as ensureCorePanelsUtil,
  applyPanelSizes,
  restoreEmptyPanel,
} from '../utils/layoutUtils'
import {
  LAYOUT_VERSION,
  validateLayoutStructure,
  saveLayout,
  savePanelSizes,
} from '../layout'

/** Debounce with flush/cancel support. */
function debounce(fn, wait) {
  let timeoutId = null
  const debounced = (...args) => {
    if (timeoutId) clearTimeout(timeoutId)
    timeoutId = setTimeout(() => {
      timeoutId = null
      fn(...args)
    }, wait)
  }
  debounced.flush = () => {
    if (timeoutId) {
      clearTimeout(timeoutId)
      timeoutId = null
      fn()
    }
  }
  debounced.cancel = () => {
    if (timeoutId) {
      clearTimeout(timeoutId)
      timeoutId = null
    }
  }
  return debounced
}

/**
 * @param {Object} options
 * @param {Function} options.setDockApi - dockApi state setter
 * @param {Function} options.setTabs - tab state setter
 * @param {string} options.storagePrefix - storage key prefix
 * @param {Object} options.panelSizesRef - ref to saved panel sizes
 * @param {Object} options.panelMinRef - ref to panel minimums
 * @param {Object} options.panelCollapsedRef - ref to collapsed thresholds
 * @param {Object} options.centerGroupRef - ref to center editor group
 * @param {Object} options.ensureCorePanelsRef - ref to ensureCorePanels fn
 * @param {Object} options.storagePrefixRef - ref to storagePrefix
 * @param {Object} options.projectRootRef - ref to projectRoot
 * @param {Object} options.layoutVersionRef - ref to layoutVersion
 * @param {Object} options.isInitialized - ref tracking init
 * @returns {{ onReady: Function }}
 */
export function useLayoutInit({
  setDockApi,
  setTabs,
  storagePrefix,
  panelSizesRef,
  panelMinRef,
  panelCollapsedRef,
  centerGroupRef,
  ensureCorePanelsRef,
  storagePrefixRef,
  projectRootRef,
  layoutVersionRef,
  isInitialized,
}) {
  const onReady = useCallback(
    (event) => {
      const api = event.api
      setDockApi(api)

      const applyLockedPanels = () => applyLockedPanelsUtil(api, panelMinRef.current)

      const ensureCorePanels = () => {
        centerGroupRef.current = ensureCorePanelsUtil(api, panelMinRef.current)
        applyLockedPanels()
      }

      // Check if there's a saved layout - if so, DON'T create panels here
      // Let the layout restoration effect handle it to avoid creating->destroying->recreating
      let hasSavedLayout = false
      let invalidLayoutFound = false
      try {
        const layoutKeyPrefix = `${storagePrefix}-`
        for (let i = 0; i < localStorage.length; i++) {
          const key = localStorage.key(i)
          if (key && key.startsWith(layoutKeyPrefix) && key.endsWith('-layout')) {
            const raw = localStorage.getItem(key)
            if (raw) {
              const parsed = JSON.parse(raw)
              const hasValidVersion = parsed?.version >= LAYOUT_VERSION
              const hasPanels = !!parsed?.panels
              const hasValidStructure = validateLayoutStructure(parsed)

              if (hasValidVersion && hasPanels && hasValidStructure) {
                hasSavedLayout = true
                break
              }

              if (!hasValidStructure || !hasValidVersion || !hasPanels) {
                console.warn('[Layout] Invalid layout detected in onReady, clearing and reloading:', key)
                localStorage.removeItem(key)
                const keyPrefix = key.replace('-layout', '')
                localStorage.removeItem(`${keyPrefix}-tabs`)
                localStorage.removeItem(`${storagePrefix}-terminal-sessions`)
                localStorage.removeItem(`${storagePrefix}-terminal-active`)
                localStorage.removeItem(`${storagePrefix}-terminal-chat-interface`)
                invalidLayoutFound = true
              }
            }
          }
        }
      } catch {
        // Ignore errors checking localStorage
      }

      if (!hasSavedLayout || invalidLayoutFound) {
        ensureCorePanels()
      }
      ensureCorePanelsRef.current = () => {
        ensureCorePanels()
        applyLockedPanels()
      }

      // Apply initial panel sizes for fresh layout
      requestAnimationFrame(() => {
        applyPanelSizes(api, {
          collapsed: { filetree: false, terminal: false, shell: false },
          panelSizes: panelSizesRef.current,
          panelMin: panelMinRef.current,
          panelCollapsed: panelCollapsedRef.current,
        })
      })

      // Handle panel close to clean up tabs state
      api.onDidRemovePanel((e) => {
        if (e.id.startsWith('editor-')) {
          const path = e.id.replace('editor-', '')
          setTabs((prev) => {
            const next = { ...prev }
            delete next[path]
            return next
          })
        }
      })

      // When all editors are closed, show the empty panel again
      api.onDidRemovePanel(() => restoreEmptyPanel(api, centerGroupRef, panelMinRef.current))

      const saveLayoutNow = () => {
        if (typeof api.toJSON !== 'function') return
        saveLayout(storagePrefixRef.current, projectRootRef.current, api.toJSON(), layoutVersionRef.current)
      }

      // Enforce minimum constraints on panels (workaround for dockview not enforcing during drag)
      const enforceMinimumConstraints = () => {
        const shellPanel = api.getPanel('shell')
        const shellGroup = shellPanel?.group
        if (shellGroup) {
          const height = shellGroup.api.height
          const minHeight = panelMinRef.current.shell
          const collapsedHeight = panelCollapsedRef.current.shell
          if (height < minHeight && height > collapsedHeight) {
            shellGroup.api.setSize({ height: minHeight })
          }
        }
      }

      // Save panel sizes when layout changes (user resizes via drag)
      const savePanelSizesNow = () => {
        const filetreePanel = api.getPanel('filetree')
        const terminalPanel = api.getPanel('terminal')
        const shellPanel = api.getPanel('shell')

        const filetreeGroup = filetreePanel?.group
        const terminalGroup = terminalPanel?.group
        const shellGroup = shellPanel?.group

        const newSizes = { ...panelSizesRef.current }
        let changed = false

        if (filetreeGroup && filetreeGroup.api.width > panelCollapsedRef.current.filetree) {
          if (newSizes.filetree !== filetreeGroup.api.width) {
            newSizes.filetree = filetreeGroup.api.width
            changed = true
          }
        }
        if (terminalGroup && terminalGroup.api.width > panelCollapsedRef.current.terminal) {
          if (newSizes.terminal !== terminalGroup.api.width) {
            newSizes.terminal = terminalGroup.api.width
            changed = true
          }
        }
        if (shellGroup && shellGroup.api.height > panelCollapsedRef.current.shell) {
          const height = Math.max(shellGroup.api.height, panelMinRef.current.shell)
          if (newSizes.shell !== height) {
            newSizes.shell = height
            changed = true
          }
        }

        if (changed) {
          panelSizesRef.current = newSizes
          savePanelSizes(newSizes, storagePrefixRef.current)
        }
      }

      // Debounce layout saves to avoid excessive writes during drag operations
      const debouncedSaveLayout = debounce(saveLayoutNow, 300)
      const debouncedSavePanelSizes = debounce(savePanelSizesNow, 300)

      if (typeof api.onDidLayoutChange === 'function') {
        api.onDidLayoutChange(() => {
          enforceMinimumConstraints()
          debouncedSaveLayout()
          debouncedSavePanelSizes()
        })
      }

      // Flush pending saves before page unload to avoid data loss
      window.addEventListener('beforeunload', () => {
        debouncedSaveLayout.flush()
        debouncedSavePanelSizes.flush()
      })

      // Mark as initialized immediately - tabs will be restored via useEffect
      isInitialized.current = true
    },
    [setDockApi, setTabs, storagePrefix, panelSizesRef, panelMinRef, panelCollapsedRef, centerGroupRef, ensureCorePanelsRef, storagePrefixRef, projectRootRef, layoutVersionRef, isInitialized],
  )

  return { onReady }
}
