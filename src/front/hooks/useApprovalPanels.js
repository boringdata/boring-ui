/**
 * Synchronizes Dockview review panels with pending approvals.
 *
 * Creates review panels for new approvals, closes panels for dismissed ones,
 * and updates params on existing panels.
 */

import { useEffect } from 'react'

/**
 * @param {Object} options
 * @param {Object|null} options.dockApi - Dockview API
 * @param {Array} options.approvals - Current pending approvals
 * @param {boolean} options.approvalsLoaded - Whether initial load completed
 * @param {Function} options.normalizeApprovalPath - Path normalizer
 * @param {Function} options.getReviewTitle - Title generator
 * @param {Function} options.handleDecision - Decision callback
 * @param {Function} options.openFile - File open callback
 * @param {Object} options.centerGroupRef - Ref to center group
 * @param {Object} options.panelMinRef - Ref to panel minimums
 */
export function useApprovalPanels({
  dockApi,
  approvals,
  approvalsLoaded,
  normalizeApprovalPath,
  getReviewTitle,
  handleDecision,
  openFile,
  centerGroupRef,
  panelMinRef,
}) {
  useEffect(() => {
    if (!dockApi || !approvalsLoaded) return
    const pendingIds = new Set(approvals.map((req) => req.id))
    const panels = Array.isArray(dockApi.panels)
      ? dockApi.panels
      : typeof dockApi.getPanels === 'function'
        ? dockApi.getPanels()
        : []

    panels.forEach((panel) => {
      if (!panel?.id?.startsWith('review-')) return
      const requestId = panel.id.replace('review-', '')
      if (!pendingIds.has(requestId)) {
        panel.api.close()
      }
    })

    approvals.forEach((approval) => {
      const panelId = `review-${approval.id}`
      const approvalPath = normalizeApprovalPath(approval)
      const existingPanel = dockApi.getPanel(panelId)
      const params = {
        request: approval,
        filePath: approvalPath,
        onDecision: handleDecision,
        onOpenFile: openFile,
      }

      if (existingPanel) {
        existingPanel.api.updateParameters(params)
        existingPanel.api.setTitle(getReviewTitle(approval))
        return
      }

      // Get panel references for positioning
      const emptyPanel = dockApi.getPanel('empty-center')
      const shellPanel = dockApi.getPanel('shell')

      // Find existing editor/review panels to add as sibling tab
      const allPanels = Array.isArray(dockApi.panels) ? dockApi.panels : []
      const existingEditorPanel = allPanels.find(
        (p) => p.id.startsWith('editor-') || p.id.startsWith('review-'),
      )

      // Priority: existing editor group > centerGroupRef > empty panel > shell > fallback
      let position
      if (existingEditorPanel?.group) {
        position = { referenceGroup: existingEditorPanel.group }
      } else if (centerGroupRef.current) {
        position = { referenceGroup: centerGroupRef.current }
      } else if (emptyPanel?.group) {
        position = { referenceGroup: emptyPanel.group }
      } else if (shellPanel?.group) {
        position = { direction: 'above', referenceGroup: shellPanel.group }
      } else {
        position = { direction: 'right', referencePanel: 'filetree' }
      }

      const panel = dockApi.addPanel({
        id: panelId,
        component: 'review',
        title: getReviewTitle(approval),
        position,
        params,
      })

      // Close empty panel AFTER adding review to its group
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
    })
  }, [
    approvals,
    approvalsLoaded,
    dockApi,
    getReviewTitle,
    handleDecision,
    normalizeApprovalPath,
    openFile,
  ])
}
