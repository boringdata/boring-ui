/**
 * Dockview onReady handler for layout initialization.
 *
 * Extracted from App.jsx lines 701-1058. Provides the onReady callback
 * that DockviewReact calls when the layout engine is initialized.
 *
 * Responsibilities:
 * - Apply locked panel configurations
 * - Create or restore core panel structure
 * - Check localStorage for saved layouts
 * - Set up panel lifecycle handlers (remove, empty state)
 * - Configure debounced save handlers for layout and panel sizes
 * - Set up beforeunload flush
 */

import { useCallback } from 'react'
import {
  LAYOUT_VERSION,
  validateLayoutStructure,
  saveLayout,
  savePanelSizes,
} from '../layout'

/**
 * Simple debounce with flush and cancel support.
 */
export function debounce(fn, wait) {
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
 * Creates the onReady callback for DockviewReact.
 *
 * @param {Object} options
 * @param {Function} options.setDockApi - Setter for dockApi state
 * @param {Function} options.setTabs - Tab state setter (for panel remove cleanup)
 * @param {string} options.storagePrefix - Storage key prefix
 * @param {Object} options.panelMinRef - Ref to minimum panel sizes
 * @param {Object} options.panelCollapsedRef - Ref to collapsed size thresholds
 * @param {Object} options.panelSizesRef - Ref to saved panel sizes
 * @param {Object} options.centerGroupRef - Ref to center editor group
 * @param {Object} options.isInitialized - Ref for initialization flag
 * @param {Object} options.ensureCorePanelsRef - Ref to store ensureCorePanels for external use
 * @param {Object} options.storagePrefixRef - Ref to storage prefix (stable)
 * @param {Object} options.projectRootRef - Ref to project root (stable)
 * @param {Object} options.layoutVersionRef - Ref to layout version (stable)
 * @returns {Function} onReady callback for DockviewReact
 */
export function useLayoutInit({
  setDockApi,
  setTabs,
  storagePrefix,
  panelMinRef,
  panelCollapsedRef,
  panelSizesRef,
  centerGroupRef,
  isInitialized,
  ensureCorePanelsRef,
  storagePrefixRef,
  projectRootRef,
  layoutVersionRef,
}) {
  const onReady = useCallback(
    (event) => {
      const api = event.api
      setDockApi(api)

      const applyLockedPanels = () => {
        const filetreePanel = api.getPanel('filetree')
        const terminalPanel = api.getPanel('terminal')

        const filetreeGroup = filetreePanel?.group
        if (filetreeGroup) {
          filetreeGroup.locked = true
          filetreeGroup.header.hidden = true
          filetreeGroup.api.setConstraints({
            minimumWidth: panelMinRef.current.filetree,
            maximumWidth: Infinity,
          })
        }

        const terminalGroup = terminalPanel?.group
        if (terminalGroup) {
          terminalGroup.locked = true
          terminalGroup.header.hidden = true
          terminalGroup.api.setConstraints({
            minimumWidth: panelMinRef.current.terminal,
            maximumWidth: Infinity,
          })
        }

        const shellPanel = api.getPanel('shell')
        const shellGroup = shellPanel?.group
        if (shellGroup) {
          shellGroup.api.setConstraints({
            minimumHeight: panelMinRef.current.shell,
            maximumHeight: Infinity,
          })
        }
      }

      const ensureCorePanels = () => {
        let filetreePanel = api.getPanel('filetree')
        if (!filetreePanel) {
          filetreePanel = api.addPanel({
            id: 'filetree',
            component: 'filetree',
            title: 'Files',
            params: { onOpenFile: () => {} },
          })
        }

        let terminalPanel = api.getPanel('terminal')
        if (!terminalPanel) {
          terminalPanel = api.addPanel({
            id: 'terminal',
            component: 'terminal',
            title: 'Code Sessions',
            position: { direction: 'right', referencePanel: 'filetree' },
          })
        }

        let emptyPanel = api.getPanel('empty-center')
        if (!emptyPanel) {
          emptyPanel = api.addPanel({
            id: 'empty-center',
            component: 'empty',
            title: '',
            position: { direction: 'left', referencePanel: 'terminal' },
          })
        }

        if (emptyPanel?.group) {
          emptyPanel.group.header.hidden = true
          centerGroupRef.current = emptyPanel.group
          emptyPanel.group.api.setConstraints({
            minimumHeight: panelMinRef.current.center,
            maximumHeight: Infinity,
          })
        }

        let shellPanel = api.getPanel('shell')
        if (!shellPanel && emptyPanel?.group) {
          shellPanel = api.addPanel({
            id: 'shell',
            component: 'shell',
            tabComponent: 'noClose',
            title: 'Shell',
            position: { direction: 'below', referenceGroup: emptyPanel.group },
            params: {
              collapsed: false,
              onToggleCollapse: () => {},
            },
          })
        }

        if (shellPanel?.group) {
          shellPanel.group.header.hidden = false
          shellPanel.group.locked = true
        }

        const panels = Array.isArray(api.panels)
          ? api.panels
          : typeof api.getPanels === 'function'
            ? api.getPanels()
            : []
        const editorPanels = panels.filter((p) => p.id.startsWith('editor-'))
        if (editorPanels.length > 0) {
          centerGroupRef.current = editorPanels[0].group
        }

        applyLockedPanels()
      }

      // Check for saved layout
      let hasSavedLayout = false
      let invalidLayoutFound = false
      try {
        const layoutKeyPrefix = `${storagePrefix}-`
        for (let i = 0; i < localStorage.length; i++) {
          const key = localStorage.key(i)
          if (
            key &&
            key.startsWith(layoutKeyPrefix) &&
            key.endsWith('-layout')
          ) {
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
                localStorage.removeItem(key)
                const keyPrefix = key.replace('-layout', '')
                localStorage.removeItem(`${keyPrefix}-tabs`)
                localStorage.removeItem(`${storagePrefix}-terminal-sessions`)
                localStorage.removeItem(`${storagePrefix}-terminal-active`)
                localStorage.removeItem(
                  `${storagePrefix}-terminal-chat-interface`,
                )
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

      // Apply initial panel sizes
      requestAnimationFrame(() => {
        const filetreeGroup = api.getPanel('filetree')?.group
        const terminalGroup = api.getPanel('terminal')?.group
        const shellGroup = api.getPanel('shell')?.group
        if (filetreeGroup) {
          api
            .getGroup(filetreeGroup.id)
            ?.api.setSize({ width: panelSizesRef.current.filetree })
        }
        if (terminalGroup) {
          api
            .getGroup(terminalGroup.id)
            ?.api.setSize({ width: panelSizesRef.current.terminal })
        }
        if (shellGroup) {
          const shellHeight = Math.max(
            panelSizesRef.current.shell,
            panelMinRef.current.shell,
          )
          api.getGroup(shellGroup.id)?.api.setSize({ height: shellHeight })
        }
      })

      // Panel close cleanup
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

      // Restore empty panel when all editors are closed
      api.onDidRemovePanel(() => {
        const existingEmpty = api.getPanel('empty-center')
        if (existingEmpty) return

        const allPanels = Array.isArray(api.panels) ? api.panels : []
        const hasEditors = allPanels.some((p) => p.id.startsWith('editor-'))
        const hasReviews = allPanels.some((p) => p.id.startsWith('review-'))

        if (hasEditors || hasReviews) return

        let centerGroup = centerGroupRef.current
        const groupStillExists =
          centerGroup && api.groups?.includes(centerGroup)
        const shellPanel = api.getPanel('shell')

        let emptyPanel
        if (groupStillExists && centerGroup.panels?.length > 0) {
          emptyPanel = api.addPanel({
            id: 'empty-center',
            component: 'empty',
            title: '',
            position: { referenceGroup: centerGroup },
          })
        } else if (shellPanel?.group) {
          emptyPanel = api.addPanel({
            id: 'empty-center',
            component: 'empty',
            title: '',
            position: {
              direction: 'above',
              referenceGroup: shellPanel.group,
            },
          })
        } else {
          emptyPanel = api.addPanel({
            id: 'empty-center',
            component: 'empty',
            title: '',
            position: { direction: 'right', referencePanel: 'filetree' },
          })
        }

        if (emptyPanel?.group) {
          centerGroupRef.current = emptyPanel.group
          emptyPanel.group.header.hidden = true
          emptyPanel.group.api.setConstraints({
            minimumHeight: panelMinRef.current.center,
            maximumHeight: Infinity,
          })
        }
      })

      // Save handlers
      const saveLayoutNow = () => {
        if (typeof api.toJSON !== 'function') return
        saveLayout(
          storagePrefixRef.current,
          projectRootRef.current,
          api.toJSON(),
          layoutVersionRef.current,
        )
      }

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

      const savePanelSizesNow = () => {
        const filetreePanel = api.getPanel('filetree')
        const terminalPanel = api.getPanel('terminal')
        const shellPanel = api.getPanel('shell')

        const filetreeGroup = filetreePanel?.group
        const terminalGroup = terminalPanel?.group
        const shellGroup = shellPanel?.group

        const newSizes = { ...panelSizesRef.current }
        let changed = false

        if (
          filetreeGroup &&
          filetreeGroup.api.width > panelCollapsedRef.current.filetree
        ) {
          if (newSizes.filetree !== filetreeGroup.api.width) {
            newSizes.filetree = filetreeGroup.api.width
            changed = true
          }
        }
        if (
          terminalGroup &&
          terminalGroup.api.width > panelCollapsedRef.current.terminal
        ) {
          if (newSizes.terminal !== terminalGroup.api.width) {
            newSizes.terminal = terminalGroup.api.width
            changed = true
          }
        }
        if (
          shellGroup &&
          shellGroup.api.height > panelCollapsedRef.current.shell
        ) {
          const height = Math.max(
            shellGroup.api.height,
            panelMinRef.current.shell,
          )
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

      const debouncedSaveLayout = debounce(saveLayoutNow, 300)
      const debouncedSavePanelSizes = debounce(savePanelSizesNow, 300)

      if (typeof api.onDidLayoutChange === 'function') {
        api.onDidLayoutChange(() => {
          enforceMinimumConstraints()
          debouncedSaveLayout()
          debouncedSavePanelSizes()
        })
      }

      window.addEventListener('beforeunload', () => {
        debouncedSaveLayout.flush()
        debouncedSavePanelSizes.flush()
      })

      isInitialized.current = true
    },
    [
      setDockApi,
      setTabs,
      storagePrefix,
      panelMinRef,
      panelCollapsedRef,
      panelSizesRef,
      centerGroupRef,
      isInitialized,
      ensureCorePanelsRef,
      storagePrefixRef,
      projectRootRef,
      layoutVersionRef,
    ],
  )

  return onReady
}
