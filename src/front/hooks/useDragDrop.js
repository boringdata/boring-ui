/**
 * Drag-and-drop file handling for dockview.
 *
 * Provides showDndOverlay (recognizes our custom drag type) and
 * onDidDrop (opens file at the drop position).
 *
 * @module hooks/useDragDrop
 */

import { useCallback } from 'react'

/**
 * @param {Object} options
 * @param {Function} options.openFileAtPosition - Opens file at a specific dockview position
 * @param {Object} options.centerGroupRef - React ref to center group
 * @returns {{ showDndOverlay: Function, onDidDrop: Function }}
 */
export function useDragDrop({ openFileAtPosition, centerGroupRef }) {
  const showDndOverlay = useCallback((event) => {
    return event.dataTransfer.types.includes('application/x-kurt-file')
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
          const centerGroup = centerGroupRef.current
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
