/**
 * Keeps Dockview panel parameters synchronized with current state.
 *
 * Extracted from App.jsx lines 1379-1436. Panels receive callbacks and
 * state through Dockview's parameter system, and this hook ensures those
 * parameters stay up-to-date when dependencies change.
 */

import { useEffect, useCallback } from 'react'

/**
 * Synchronizes filetree, terminal, and shell panel parameters.
 *
 * @param {Object} options
 * @param {Object|null} options.dockApi - Dockview API instance
 * @param {Object} options.fileOps - { openFile, openFileToSide, openDiff }
 * @param {Object} options.toggles - { filetree, terminal, shell } toggle functions
 * @param {Object} options.collapsed - { filetree, terminal, shell } booleans
 * @param {string|null} options.projectRoot - Project root path
 * @param {string|null} options.activeFile - Currently active file path
 * @param {string|null} options.activeDiffFile - Currently active diff file path
 * @param {Array} options.approvals - Pending approval requests
 * @param {Function} options.handleDecision - Approval decision handler
 * @param {Function} options.normalizeApprovalPath - Path normalization for approvals
 */
export function usePanelParams({
  dockApi,
  fileOps,
  toggles,
  collapsed,
  projectRoot,
  activeFile,
  activeDiffFile,
  approvals,
  handleDecision,
  normalizeApprovalPath,
}) {
  const { openFile, openFileToSide, openDiff } = fileOps || {}
  const { filetree: toggleFiletree, terminal: toggleTerminal, shell: toggleShell } = toggles || {}

  // Focus a review panel by request ID
  const focusReviewPanel = useCallback(
    (requestId) => {
      if (!dockApi) return
      const panel = dockApi.getPanel(`review-${requestId}`)
      if (panel) {
        panel.api.setActive()
      }
    },
    [dockApi],
  )

  // Update filetree panel params
  useEffect(() => {
    if (!dockApi) return
    const filetreePanel = dockApi.getPanel('filetree')
    if (filetreePanel) {
      filetreePanel.api.updateParameters({
        onOpenFile: openFile,
        onOpenFileToSide: openFileToSide,
        onOpenDiff: openDiff,
        projectRoot,
        activeFile,
        activeDiffFile,
        collapsed: collapsed?.filetree,
        onToggleCollapse: toggleFiletree,
      })
    }
  }, [
    dockApi,
    openFile,
    openFileToSide,
    openDiff,
    projectRoot,
    activeFile,
    activeDiffFile,
    collapsed?.filetree,
    toggleFiletree,
  ])

  // Update terminal panel params
  useEffect(() => {
    if (!dockApi) return
    const terminalPanel = dockApi.getPanel('terminal')
    if (terminalPanel) {
      terminalPanel.api.updateParameters({
        collapsed: collapsed?.terminal,
        onToggleCollapse: toggleTerminal,
        approvals,
        onFocusReview: focusReviewPanel,
        onDecision: handleDecision,
        normalizeApprovalPath,
      })
    }
  }, [
    dockApi,
    collapsed?.terminal,
    toggleTerminal,
    approvals,
    focusReviewPanel,
    handleDecision,
    normalizeApprovalPath,
  ])

  // Update shell panel params
  useEffect(() => {
    if (!dockApi) return
    const shellPanel = dockApi.getPanel('shell')
    if (shellPanel) {
      shellPanel.api.updateParameters({
        collapsed: collapsed?.shell,
        onToggleCollapse: toggleShell,
      })
    }
  }, [dockApi, collapsed?.shell, toggleShell, projectRoot])

  return { focusReviewPanel }
}
