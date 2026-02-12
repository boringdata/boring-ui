/**
 * Layout restoration from localStorage when projectRoot becomes available.
 *
 * Handles:
 * - Loading saved layout JSON and applying via dockApi.fromJSON
 * - Re-applying locked panel constraints after restore
 * - Re-wiring callbacks to filetree and editor panels (not serializable)
 * - Pruning empty groups from stale layouts
 * - Falling back to ensureCorePanels for fresh layouts
 *
 * @module hooks/useLayoutRestore
 */

import { useEffect, useRef } from 'react'
import { loadLayout, saveLayout, getFileName, pruneEmptyGroups } from '../layout'
import { applyPanelSizes } from '../utils/layoutUtils'
import { getKnownComponents } from '../registry/panes'

const KNOWN_COMPONENTS = getKnownComponents()

/**
 * @param {Object} options
 * @param {Object|null} options.dockApi
 * @param {string|null} options.projectRoot
 * @param {string} options.storagePrefix
 * @param {number} options.layoutVersion
 * @param {Object} options.collapsed - { filetree, terminal, shell }
 * @param {Function} options.openFile
 * @param {Function} options.openFileToSide
 * @param {Function} options.openDiff
 * @param {string|null} options.activeFile
 * @param {string|null} options.activeDiffFile
 * @param {Function} options.toggleFiletree
 * @param {Function} options.setTabs
 * @param {Object} options.centerGroupRef
 * @param {Object} options.panelSizesRef
 * @param {Object} options.panelMinRef
 * @param {Object} options.panelCollapsedRef
 * @param {Object} options.collapsedEffectRan
 * @param {Object} options.layoutRestored
 * @param {Object} options.ensureCorePanelsRef
 */
export function useLayoutRestore({
  dockApi,
  projectRoot,
  storagePrefix,
  layoutVersion,
  collapsed,
  openFile,
  openFileToSide,
  openDiff,
  activeFile,
  activeDiffFile,
  toggleFiletree,
  setTabs,
  centerGroupRef,
  panelSizesRef,
  panelMinRef,
  panelCollapsedRef,
  collapsedEffectRan,
  layoutRestored,
  ensureCorePanelsRef,
}) {
  const layoutRestorationRan = useRef(false)

  useEffect(() => {
    if (!dockApi || projectRoot === null || layoutRestorationRan.current) return
    layoutRestorationRan.current = true

    const savedLayout = loadLayout(storagePrefix, projectRoot, KNOWN_COMPONENTS, layoutVersion)
    if (!savedLayout) {
      if (ensureCorePanelsRef.current) {
        ensureCorePanelsRef.current()
        layoutRestored.current = true
        requestAnimationFrame(() => {
          applyPanelSizes(dockApi, {
            collapsed,
            panelSizes: panelSizesRef.current,
            panelMin: panelMinRef.current,
            panelCollapsed: panelCollapsedRef.current,
          })
          collapsedEffectRan.current = true
        })
      }
      return
    }

    if (savedLayout && typeof dockApi.fromJSON === 'function') {
      try {
        dockApi.fromJSON(savedLayout)
        layoutRestored.current = true

        // Re-apply locked panel constraints
        const filetreePanel = dockApi.getPanel('filetree')
        const terminalPanel = dockApi.getPanel('terminal')
        const shellPanel = dockApi.getPanel('shell')

        const filetreeGroup = filetreePanel?.group
        if (filetreeGroup) {
          filetreeGroup.locked = true
          filetreeGroup.header.hidden = true
        }

        // Re-wire filetree callbacks (not serializable in layout JSON)
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

        const terminalGroup = terminalPanel?.group
        if (terminalGroup) {
          terminalGroup.locked = true
          terminalGroup.header.hidden = true
        }

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

        // Handle editor panels — set constraints and close empty-center
        const panels = Array.isArray(dockApi.panels)
          ? dockApi.panels
          : typeof dockApi.getPanels === 'function'
            ? dockApi.getPanels()
            : []
        const editorPanels = panels.filter((p) => p.id.startsWith('editor-'))
        const hasReviews = panels.some((p) => p.id.startsWith('review-'))
        if (editorPanels.length > 0 || hasReviews) {
          const editorPanel = panels.find((p) => p.id.startsWith('editor-') || p.id.startsWith('review-'))
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

        // Re-wire editor callbacks (not serializable in layout JSON)
        editorPanels.forEach((panel) => {
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

        // Update centerGroupRef from empty-center if present
        const emptyPanel = dockApi.getPanel('empty-center')
        if (emptyPanel?.group) {
          centerGroupRef.current = emptyPanel.group
          emptyPanel.group.api.setConstraints({
            minimumHeight: panelMinRef.current.center,
            maximumHeight: Infinity,
          })
        }

        // Prune empty groups
        const pruned = pruneEmptyGroups(dockApi, KNOWN_COMPONENTS)
        if (pruned && typeof dockApi.toJSON === 'function') {
          saveLayout(storagePrefix, projectRoot, dockApi.toJSON(), layoutVersion)
        }

        // Apply saved panel sizes
        requestAnimationFrame(() => {
          applyPanelSizes(dockApi, {
            collapsed,
            panelSizes: panelSizesRef.current,
            panelMin: panelMinRef.current,
            panelCollapsed: panelCollapsedRef.current,
          })
          collapsedEffectRan.current = true
        })
      } catch {
        layoutRestored.current = false
      }
    }
  }, [dockApi, projectRoot, storagePrefix, collapsed.filetree, collapsed.terminal, collapsed.shell, openFile, openFileToSide, openDiff, activeFile, activeDiffFile, toggleFiletree])
}
