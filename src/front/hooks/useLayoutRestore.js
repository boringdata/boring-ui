/**
 * Restores Dockview layout from localStorage once dockApi and projectRoot
 * are available.
 *
 * Extracted from App.jsx lines 1111-1352. Handles two paths:
 * 1. No saved layout: calls ensureCorePanels and applies collapsed sizes
 * 2. Saved layout: applies fromJSON, restores panel locks/constraints/params,
 *    prunes empty groups, and applies collapsed sizes
 */

import { useEffect, useRef } from 'react'
import {
  loadLayout,
  saveLayout,
  pruneEmptyGroups,
  getFileName,
} from '../layout'

/**
 * Helper to apply collapsed/expanded constraints and sizes to core panels.
 * Used in both the fresh-layout and saved-layout code paths.
 */
function applyCollapsedSizes(dockApi, collapsed, panelCollapsedRef, panelMinRef, panelSizesRef) {
  const ftGroup = dockApi.getPanel('filetree')?.group
  const tGroup = dockApi.getPanel('terminal')?.group
  const sGroup = dockApi.getPanel('shell')?.group

  if (ftGroup) {
    const ftApi = dockApi.getGroup(ftGroup.id)?.api
    if (ftApi) {
      if (collapsed.filetree) {
        ftApi.setConstraints({ minimumWidth: panelCollapsedRef.current.filetree, maximumWidth: panelCollapsedRef.current.filetree })
        ftApi.setSize({ width: panelCollapsedRef.current.filetree })
      } else {
        ftApi.setConstraints({ minimumWidth: panelMinRef.current.filetree, maximumWidth: Infinity })
        ftApi.setSize({ width: panelSizesRef.current.filetree })
      }
    }
  }
  if (tGroup) {
    const tApi = dockApi.getGroup(tGroup.id)?.api
    if (tApi) {
      if (collapsed.terminal) {
        tApi.setConstraints({ minimumWidth: panelCollapsedRef.current.terminal, maximumWidth: panelCollapsedRef.current.terminal })
        tApi.setSize({ width: panelCollapsedRef.current.terminal })
      } else {
        tApi.setConstraints({ minimumWidth: panelMinRef.current.terminal, maximumWidth: Infinity })
        tApi.setSize({ width: panelSizesRef.current.terminal })
      }
    }
  }
  if (sGroup) {
    const sApi = dockApi.getGroup(sGroup.id)?.api
    if (sApi) {
      if (collapsed.shell) {
        sApi.setConstraints({ minimumHeight: panelCollapsedRef.current.shell, maximumHeight: panelCollapsedRef.current.shell })
        sApi.setSize({ height: panelCollapsedRef.current.shell })
      } else {
        sApi.setConstraints({ minimumHeight: panelMinRef.current.shell, maximumHeight: Infinity })
        const shellHeight = Math.max(panelSizesRef.current.shell, panelMinRef.current.shell)
        sApi.setSize({ height: shellHeight })
      }
    }
  }
}

/**
 * Restores layout from localStorage on initial load.
 *
 * @param {Object} options
 * @param {Object|null} options.dockApi - Dockview API instance
 * @param {string|null} options.projectRoot - Project root (null = not loaded)
 * @param {string} options.storagePrefix - localStorage key prefix
 * @param {number} options.layoutVersion - Layout schema version
 * @param {string[]} options.knownComponents - Known component IDs for validation
 * @param {Object} options.collapsed - Current collapsed state
 * @param {Object} options.panelCollapsedRef - Ref to collapsed dimensions
 * @param {Object} options.panelMinRef - Ref to minimum dimensions
 * @param {Object} options.panelSizesRef - Ref to saved panel sizes
 * @param {Object} options.centerGroupRef - Ref to center group
 * @param {Object} options.layoutRestored - Ref boolean
 * @param {Object} options.collapsedEffectRan - Ref boolean
 * @param {Object} options.ensureCorePanelsRef - Ref to panel creation function
 * @param {Function} options.openFile - File open callback
 * @param {Function} options.openFileToSide - File open to side callback
 * @param {Function} options.openDiff - Diff open callback
 * @param {string|null} options.activeFile - Active file path
 * @param {string|null} options.activeDiffFile - Active diff file path
 * @param {Function} options.toggleFiletree - Filetree toggle function
 * @param {Function} options.setTabs - Tab state setter
 */
export function useLayoutRestore({
  dockApi,
  projectRoot,
  storagePrefix,
  layoutVersion,
  knownComponents,
  collapsed,
  panelCollapsedRef,
  panelMinRef,
  panelSizesRef,
  centerGroupRef,
  layoutRestored,
  collapsedEffectRan,
  ensureCorePanelsRef,
  openFile,
  openFileToSide,
  openDiff,
  activeFile,
  activeDiffFile,
  toggleFiletree,
  setTabs,
}) {
  const layoutRestorationRan = useRef(false)

  useEffect(() => {
    if (!dockApi || projectRoot === null || layoutRestorationRan.current) return
    layoutRestorationRan.current = true

    const savedLayout = loadLayout(storagePrefix, projectRoot, knownComponents, layoutVersion)

    // No saved layout: ensure core panels and apply collapsed sizes
    if (!savedLayout) {
      if (ensureCorePanelsRef.current) {
        ensureCorePanelsRef.current()
        layoutRestored.current = true
        requestAnimationFrame(() => {
          applyCollapsedSizes(dockApi, collapsed, panelCollapsedRef, panelMinRef, panelSizesRef)
          collapsedEffectRan.current = true
        })
      }
      return
    }

    // Saved layout: restore from JSON
    if (typeof dockApi.fromJSON === 'function') {
      try {
        dockApi.fromJSON(savedLayout)
        layoutRestored.current = true

        // Lock and configure filetree group
        const filetreePanel = dockApi.getPanel('filetree')
        const filetreeGroup = filetreePanel?.group
        if (filetreeGroup) {
          filetreeGroup.locked = true
          filetreeGroup.header.hidden = true
        }

        // Restore filetree callbacks (can't be serialized in layout JSON)
        if (filetreePanel) {
          filetreePanel.api.updateParameters({
            onOpenFile: openFile,
            onOpenFileToSide: openFileToSide,
            onOpenDiff: openDiff,
            projectRoot,
            activeFile,
            activeDiffFile,
            collapsed: collapsed.filetree,
            onToggleCollapse: toggleFiletree,
          })
        }

        // Lock terminal group
        const terminalPanel = dockApi.getPanel('terminal')
        const terminalGroup = terminalPanel?.group
        if (terminalGroup) {
          terminalGroup.locked = true
          terminalGroup.header.hidden = true
        }

        // Lock shell group with constraints
        const shellPanel = dockApi.getPanel('shell')
        const shellGroup = shellPanel?.group
        if (shellGroup) {
          shellGroup.locked = true
          shellGroup.header.hidden = false
          shellGroup.api.setConstraints({
            minimumHeight: panelMinRef.current.shell,
            maximumHeight: Infinity,
          })
          const currentHeight = shellGroup.api.height
          const minHeight = panelMinRef.current.shell
          const collapsedHeight = panelCollapsedRef.current.shell
          if (currentHeight < minHeight && currentHeight > collapsedHeight) {
            shellGroup.api.setSize({ height: minHeight })
          }
        }

        // Handle editor/review panels
        const panels = Array.isArray(dockApi.panels)
          ? dockApi.panels
          : typeof dockApi.getPanels === 'function'
            ? dockApi.getPanels()
            : []
        const editorPanels = panels.filter((p) => p.id.startsWith('editor-'))
        const hasReviews = panels.some((p) => p.id.startsWith('review-'))

        if (editorPanels.length > 0 || hasReviews) {
          const editorPanel = panels.find(
            (p) => p.id.startsWith('editor-') || p.id.startsWith('review-'),
          )
          if (editorPanel?.group) {
            centerGroupRef.current = editorPanel.group
            editorPanel.group.api.setConstraints({
              minimumHeight: panelMinRef.current.center,
              maximumHeight: Infinity,
            })
          }
          const emptyPanel = dockApi.getPanel('empty-center')
          if (emptyPanel) {
            emptyPanel.api.close()
          }
        }

        // Restore editor panel callbacks
        editorPanels.forEach((panel) => {
          const path = panel.id.replace('editor-', '')
          panel.api.updateParameters({
            onContentChange: (p, newContent) => {
              setTabs((prev) => ({
                ...prev,
                [p]: { ...prev[p], content: newContent },
              }))
            },
            onDirtyChange: (p, dirty) => {
              setTabs((prev) => ({
                ...prev,
                [p]: { ...prev[p], isDirty: dirty },
              }))
              const editorPanel = dockApi.getPanel(`editor-${p}`)
              if (editorPanel) {
                editorPanel.api.setTitle(getFileName(p) + (dirty ? ' *' : ''))
              }
            },
          })
        })

        // Track center group from empty panel
        const emptyPanel = dockApi.getPanel('empty-center')
        if (emptyPanel?.group) {
          centerGroupRef.current = emptyPanel.group
          emptyPanel.group.api.setConstraints({
            minimumHeight: panelMinRef.current.center,
            maximumHeight: Infinity,
          })
        }

        // Prune empty groups
        const pruned = pruneEmptyGroups(dockApi, knownComponents)
        if (pruned && typeof dockApi.toJSON === 'function') {
          saveLayout(storagePrefix, projectRoot, dockApi.toJSON(), layoutVersion)
        }

        // Apply saved sizes in next frame
        requestAnimationFrame(() => {
          applyCollapsedSizes(dockApi, collapsed, panelCollapsedRef, panelMinRef, panelSizesRef)
          collapsedEffectRan.current = true
        })
      } catch {
        layoutRestored.current = false
      }
    }
  }, [
    dockApi,
    projectRoot,
    storagePrefix,
    collapsed.filetree,
    collapsed.terminal,
    collapsed.shell,
    openFile,
    openFileToSide,
    openDiff,
    activeFile,
    activeDiffFile,
    toggleFiletree,
    layoutVersion,
    knownComponents,
    panelCollapsedRef,
    panelMinRef,
    panelSizesRef,
    centerGroupRef,
    layoutRestored,
    collapsedEffectRan,
    ensureCorePanelsRef,
    setTabs,
  ])
}
