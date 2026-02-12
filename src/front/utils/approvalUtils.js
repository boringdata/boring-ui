/**
 * Approval path normalization and title generation utilities.
 *
 * Pure functions extracted from App.jsx for reuse and testability.
 */

import { getFileName } from '../layout'

/**
 * Normalize an approval's file path to be project-relative.
 *
 * @param {Object|null} approval - Approval object
 * @param {string|null} projectRoot - Project root path
 * @returns {string} Normalized relative path, or empty string
 */
export function normalizeApprovalPath(approval, projectRoot) {
  if (!approval) return ''
  if (approval.project_path) return approval.project_path
  const filePath = approval.file_path || ''
  if (!filePath) return ''
  if (projectRoot) {
    const root = projectRoot.endsWith('/') ? projectRoot : `${projectRoot}/`
    if (filePath.startsWith(root)) {
      return filePath.slice(root.length)
    }
  }
  return filePath
}

/**
 * Generate a review panel title for an approval.
 *
 * @param {Object|null} approval - Approval object
 * @param {string|null} projectRoot - Project root path
 * @returns {string} Title like "Review: filename.js" or "Review: tool_name"
 */
export function getReviewTitle(approval, projectRoot) {
  const approvalPath = normalizeApprovalPath(approval, projectRoot)
  if (approvalPath) {
    return `Review: ${getFileName(approvalPath)}`
  }
  if (approval?.tool_name) {
    return `Review: ${approval.tool_name}`
  }
  return 'Review'
}
