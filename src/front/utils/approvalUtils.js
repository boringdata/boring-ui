/**
 * Approval path normalization and review title generation.
 *
 * Extracted from App.jsx to enable reuse and testing without React context.
 */

/**
 * Extracts the filename from a path string.
 *
 * @param {string} path - File path (relative or absolute)
 * @returns {string} Filename, or empty string if path is empty
 */
export function extractFilename(path) {
  if (!path) return ''
  const parts = path.split('/')
  return parts[parts.length - 1]
}

/**
 * Normalizes an approval path to be project-relative.
 *
 * Checks approval.project_path first (pre-normalized), then strips
 * projectRoot prefix from approval.file_path if present.
 *
 * @param {Object|null} approval - Approval object with optional project_path and file_path
 * @param {string|null} projectRoot - Absolute project root path
 * @returns {string} Normalized relative path, or empty string
 *
 * @example
 * normalizeApprovalPath({ file_path: '/home/user/project/src/a.js' }, '/home/user/project')
 * // Returns: 'src/a.js'
 *
 * normalizeApprovalPath({ project_path: 'src/a.js' }, '/anything')
 * // Returns: 'src/a.js'
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
 * Generates a title for a review panel based on the approval.
 *
 * Priority:
 * 1. "Review: {filename}" if a file path is available
 * 2. "Review: {tool_name}" if only tool name is available
 * 3. "Review" as fallback
 *
 * @param {Object|null} approval - Approval object
 * @param {string|null} projectRoot - Project root for path normalization
 * @returns {string} Panel title
 *
 * @example
 * getReviewTitle({ file_path: '/project/src/App.jsx', tool_name: 'Edit' }, '/project')
 * // Returns: 'Review: App.jsx'
 */
export function getReviewTitle(approval, projectRoot) {
  const approvalPath = normalizeApprovalPath(approval, projectRoot)
  if (approvalPath) {
    return `Review: ${extractFilename(approvalPath)}`
  }
  if (approval?.tool_name) {
    return `Review: ${approval.tool_name}`
  }
  return 'Review'
}
