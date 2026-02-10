/**
 * File opening operations for the editor interface.
 *
 * Provides four callbacks for opening files in the Dockview layout:
 * - openFileAtPosition: core — opens at a specific DockView position
 * - openFile: smart positioning with fallback strategy
 * - openFileToSide: opens to the right of the active editor
 * - openDiff: opens in git-diff mode
 *
 * @module hooks/useFileOperations
 */

import { useCallback } from 'react'
import { buildApiUrl } from '../utils/apiBase'
import { findEditorPosition, findSidePosition, findDiffPosition } from '../utils/filePositioning'
import { getFileName } from '../layout'

/**
 * @param {Object} options
 * @param {Object|null} options.dockApi - Dockview API
 * @param {Function} options.setTabs - Tab state setter
 * @param {Function} options.setActiveDiffFile - Active diff file setter
 * @param {Object} options.centerGroupRef - Ref to center editor group
 * @param {Object} options.panelMinRef - Ref to panel minimum sizes
 * @returns {{ openFileAtPosition: Function, openFile: Function, openFileToSide: Function, openDiff: Function }}
 */
export function useFileOperations({
  dockApi,
  setTabs,
  setActiveDiffFile,
  centerGroupRef,
  panelMinRef,
}) {
  const openFileAtPosition = useCallback(
    (path, position, extraParams = {}) => {
      if (!dockApi) return

      const panelId = `editor-${path}`
      const existingPanel = dockApi.getPanel(panelId)

      if (existingPanel) {
        if (extraParams.initialMode) {
          existingPanel.api.updateParameters({ initialMode: extraParams.initialMode })
        }
        existingPanel.api.setActive()
        return
      }

      const emptyPanel = dockApi.getPanel('empty-center')
      const centerGroup = centerGroupRef.current
      if (centerGroup) {
        centerGroup.header.hidden = false
      }

      const addEditorPanel = (content) => {
        setTabs((prev) => ({
          ...prev,
          [path]: { content, isDirty: false },
        }))

        const panel = dockApi.addPanel({
          id: panelId,
          component: 'editor',
          title: getFileName(path),
          position,
          params: {
            path,
            initialContent: content,
            contentVersion: 1,
            ...extraParams,
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
              const panel = dockApi.getPanel(`editor-${p}`)
              if (panel) {
                panel.api.setTitle(getFileName(p) + (dirty ? ' *' : ''))
              }
            },
          },
        })

        if (emptyPanel) {
          emptyPanel.api.close()
        }
        if (panel?.group) {
          panel.group.header.hidden = false
          centerGroupRef.current = panel.group
          panel.group.api.setConstraints({
            minimumHeight: panelMinRef.current.center,
            maximumHeight: Infinity,
          })
        }
      }

      fetch(buildApiUrl(`/api/file?path=${encodeURIComponent(path)}`))
        .then((r) => r.json())
        .then((data) => {
          addEditorPanel(data.content || '')
        })
        .catch(() => {
          addEditorPanel('')
        })
    },
    [dockApi, setTabs, centerGroupRef, panelMinRef],
  )

  const openFile = useCallback(
    (path) => {
      if (!dockApi) return false

      const panelId = `editor-${path}`
      const existingPanel = dockApi.getPanel(panelId)

      if (existingPanel) {
        existingPanel.api.setActive()
        return true
      }

      openFileAtPosition(path, findEditorPosition(dockApi, centerGroupRef.current))
      return true
    },
    [dockApi, openFileAtPosition, centerGroupRef],
  )

  const openFileToSide = useCallback(
    (path) => {
      if (!dockApi) return

      const existingPanel = dockApi.getPanel(`editor-${path}`)
      if (existingPanel) {
        existingPanel.api.setActive()
        return
      }

      openFileAtPosition(path, findSidePosition(dockApi, centerGroupRef.current))
    },
    [dockApi, openFileAtPosition, centerGroupRef],
  )

  const openDiff = useCallback(
    (path, _status) => {
      if (!dockApi) return

      const existingPanel = dockApi.getPanel(`editor-${path}`)
      if (existingPanel) {
        existingPanel.api.updateParameters({ initialMode: 'git-diff' })
        existingPanel.api.setActive()
        setActiveDiffFile(path)
        return
      }

      openFileAtPosition(path, findDiffPosition(dockApi, centerGroupRef.current), { initialMode: 'git-diff' })
      setActiveDiffFile(path)
    },
    [dockApi, openFileAtPosition, setActiveDiffFile, centerGroupRef],
  )

  return { openFileAtPosition, openFile, openFileToSide, openDiff }
}
