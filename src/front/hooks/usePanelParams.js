/**
 * Keeps panel parameters in sync with current callbacks and state.
 *
 * Dockview panels receive params at creation, but callbacks and state
 * change over time. These effects push updated params to each panel.
 */

import { useEffect, useCallback } from 'react'

/**
 * @param {Object} options
 * @param {Object|null} options.dockApi - Dockview API
 * @param {Object} options.collapsed - { filetree, terminal, shell }
 * @param {Function} options.toggleFiletree
 * @param {Function} options.toggleTerminal
 * @param {Function} options.toggleShell
 * @param {Function} options.openFile
 * @param {Function} options.openFileToSide
 * @param {Function} options.openDiff
 * @param {string|null} options.projectRoot
 * @param {string|null} options.activeFile
 * @param {string|null} options.activeDiffFile
 * @param {Array} options.approvals
 * @param {Function} options.handleDecision
 * @param {Function} options.normalizeApprovalPath
 * @returns {{ focusReviewPanel: Function }}
 */
export function usePanelParams({
  dockApi,
  collapsed,
  toggleFiletree,
  toggleTerminal,
  toggleShell,
  openFile,
  openFileToSide,
  openDiff,
  projectRoot,
  activeFile,
  activeDiffFile,
  approvals,
  handleDecision,
  normalizeApprovalPath,
}) {
  // Filetree params
  useEffect(() => {
    if (!dockApi) return
    const panel = dockApi.getPanel('filetree')
    if (panel) {
      panel.api.updateParameters({
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
  }, [dockApi, openFile, openFileToSide, openDiff, projectRoot, activeFile, activeDiffFile, collapsed.filetree, toggleFiletree])

  // Focus helper for review panels
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

  // Terminal params
  useEffect(() => {
    if (!dockApi) return
    const panel = dockApi.getPanel('terminal')
    if (panel) {
      panel.api.updateParameters({
        collapsed: collapsed.terminal,
        onToggleCollapse: toggleTerminal,
        approvals,
        onFocusReview: focusReviewPanel,
        onDecision: handleDecision,
        normalizeApprovalPath,
      })
    }
  }, [dockApi, collapsed.terminal, toggleTerminal, approvals, focusReviewPanel, handleDecision, normalizeApprovalPath])

  // Shell params
  useEffect(() => {
    if (!dockApi) return
    const panel = dockApi.getPanel('shell')
    if (panel) {
      panel.api.updateParameters({
        collapsed: collapsed.shell,
        onToggleCollapse: toggleShell,
      })
    }
  }, [dockApi, collapsed.shell, toggleShell, projectRoot])

  return { focusReviewPanel }
}
