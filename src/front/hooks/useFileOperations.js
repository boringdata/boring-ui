/**
 * File opening operations for the editor interface.
 *
 * Extracted from App.jsx lines 414-608. Provides openFile, openFileAtPosition,
 * openFileToSide, and openDiff callbacks with smart Dockview positioning.
 */

import { useCallback } from 'react'
import { buildApiUrl } from '../utils/apiBase'
import { getFileName } from '../layout'

/**
 * Creates file operation callbacks for the editor.
 *
 * @param {Object} options
 * @param {Object|null} options.dockApi - Dockview API instance
 * @param {Function} options.setTabs - Tab state setter
 * @param {Function} options.setActiveDiffFile - Active diff file setter
 * @param {Object} options.centerGroupRef - Ref to center editor group
 * @param {Object} options.panelMinRef - Ref to minimum panel sizes
 * @returns {Object} { openFile, openFileAtPosition, openFileToSide, openDiff }
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
          existingPanel.api.updateParameters({
            initialMode: extraParams.initialMode,
          })
        }
        existingPanel.api.setActive()
        return
      }

      const emptyPanel = dockApi.getPanel('empty-center')
      const centerGroup = centerGroupRef?.current
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
              const dirtyPanel = dockApi.getPanel(`editor-${p}`)
              if (dirtyPanel) {
                dirtyPanel.api.setTitle(getFileName(p) + (dirty ? ' *' : ''))
              }
            },
          },
        })

        if (emptyPanel) {
          emptyPanel.api.close()
        }
        if (panel?.group) {
          panel.group.header.hidden = false
          if (centerGroupRef) {
            centerGroupRef.current = panel.group
          }
          panel.group.api.setConstraints({
            minimumHeight: panelMinRef?.current?.center ?? 200,
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

      const emptyPanel = dockApi.getPanel('empty-center')
      const shellPanel = dockApi.getPanel('shell')
      const centerGroup = centerGroupRef?.current

      const allPanels = Array.isArray(dockApi.panels) ? dockApi.panels : []
      const existingEditorPanel = allPanels.find(
        (p) => p.id.startsWith('editor-') || p.id.startsWith('review-'),
      )

      let position
      if (existingEditorPanel?.group) {
        position = { referenceGroup: existingEditorPanel.group }
      } else if (centerGroup) {
        position = { referenceGroup: centerGroup }
      } else if (emptyPanel?.group) {
        position = { referenceGroup: emptyPanel.group }
      } else if (shellPanel?.group) {
        position = { direction: 'above', referenceGroup: shellPanel.group }
      } else {
        position = { direction: 'right', referencePanel: 'filetree' }
      }

      openFileAtPosition(path, position)
      return true
    },
    [dockApi, openFileAtPosition, centerGroupRef],
  )

  const openFileToSide = useCallback(
    (path) => {
      if (!dockApi) return

      const panelId = `editor-${path}`
      const existingPanel = dockApi.getPanel(panelId)

      if (existingPanel) {
        existingPanel.api.setActive()
        return
      }

      const activePanel = dockApi.activePanel
      let position

      if (activePanel && activePanel.id.startsWith('editor-')) {
        position = { direction: 'right', referencePanel: activePanel.id }
      } else if (centerGroupRef?.current) {
        position = {
          direction: 'right',
          referenceGroup: centerGroupRef.current,
        }
      } else {
        position = { direction: 'right', referencePanel: 'filetree' }
      }

      openFileAtPosition(path, position)
    },
    [dockApi, openFileAtPosition, centerGroupRef],
  )

  const openDiff = useCallback(
    (path, _status) => {
      if (!dockApi) return

      const panelId = `editor-${path}`
      const existingPanel = dockApi.getPanel(panelId)

      if (existingPanel) {
        existingPanel.api.updateParameters({ initialMode: 'git-diff' })
        existingPanel.api.setActive()
        setActiveDiffFile(path)
        return
      }

      const emptyPanel = dockApi.getPanel('empty-center')
      const shellPanel = dockApi.getPanel('shell')
      const centerGroup = centerGroupRef?.current

      let position
      if (emptyPanel?.group) {
        position = { referenceGroup: emptyPanel.group }
      } else if (centerGroup) {
        position = { referenceGroup: centerGroup }
      } else if (shellPanel?.group) {
        position = { direction: 'above', referenceGroup: shellPanel.group }
      } else {
        position = { direction: 'right', referencePanel: 'filetree' }
      }

      openFileAtPosition(path, position, { initialMode: 'git-diff' })
      setActiveDiffFile(path)
    },
    [dockApi, openFileAtPosition, setActiveDiffFile, centerGroupRef],
  )

  return {
    openFile,
    openFileAtPosition,
    openFileToSide,
    openDiff,
  }
}
