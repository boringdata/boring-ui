/**
 * Drag and drop file handling for Dockview.
 *
 * Extracted from App.jsx lines 1488-1525. Handles external drag events
 * from the FileTree component using the application/x-kurt-file MIME type.
 */

import { useCallback } from 'react'

/**
 * Provides drag-and-drop handlers for Dockview.
 *
 * @param {Object} options
 * @param {Function} options.openFileAtPosition - Opens file at a specific layout position
 * @param {Object} options.centerGroupRef - Ref to center group for fallback positioning
 * @returns {Object} { showDndOverlay, onDidDrop }
 */
export function useDragDrop({ openFileAtPosition, centerGroupRef }) {
  const showDndOverlay = useCallback((event) => {
    const hasFileData = event.dataTransfer.types.includes('application/x-kurt-file')
    return hasFileData
  }, [])

  const onDidDrop = useCallback(
    (event) => {
      const { dataTransfer, position, group } = event
      const fileDataStr = dataTransfer.getData('application/x-kurt-file')

      if (!fileDataStr) return

      try {
        const fileData = JSON.parse(fileDataStr)
        const path = fileData.path

        let dropPosition
        if (group) {
          dropPosition = { referenceGroup: group }
        } else if (position) {
          dropPosition = position
        } else {
          const centerGroup = centerGroupRef?.current
          dropPosition = centerGroup
            ? { referenceGroup: centerGroup }
            : { direction: 'right', referencePanel: 'filetree' }
        }

        openFileAtPosition(path, dropPosition)
      } catch {
        // Ignore parse errors
      }
    },
    [openFileAtPosition, centerGroupRef],
  )

  return { showDndOverlay, onDidDrop }
}
