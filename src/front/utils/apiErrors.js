/**
 * API error code/status mappings for user-facing UX.
 *
 * Bead: bd-223o.14.3.1 (H3a)
 *
 * Maps HTTP status codes and backend error codes to:
 *   - label: short user-friendly title
 *   - guidance: actionable description
 *   - retryable: whether automatic/manual retry is appropriate
 *   - action: suggested user action (e.g. 'sign_in', 'retry', 'rename')
 */

// ── Status code → error info ────────────────────────────────────────

const STATUS_MAP = {
  400: {
    label: 'Invalid request',
    guidance: 'The request contained invalid data. Check your input and try again.',
    retryable: false,
    action: 'fix_input',
  },
  401: {
    label: 'Session expired',
    guidance: 'Your session has expired. Please sign in again to continue.',
    retryable: false,
    action: 'sign_in',
  },
  403: {
    label: 'Permission denied',
    guidance: 'You do not have permission to perform this action.',
    retryable: false,
    action: 'contact_admin',
  },
  404: {
    label: 'Not found',
    guidance: 'The requested resource could not be found. It may have been deleted or moved.',
    retryable: false,
    action: 'navigate_back',
  },
  409: {
    label: 'Conflict',
    guidance: 'This action conflicts with the current state. The resource may have been modified by someone else.',
    retryable: false,
    action: 'refresh',
  },
  410: {
    label: 'No longer available',
    guidance: 'This resource has been permanently removed and is no longer available.',
    retryable: false,
    action: 'navigate_back',
  },
  422: {
    label: 'Validation error',
    guidance: 'The provided data did not pass validation. Please check the fields and try again.',
    retryable: false,
    action: 'fix_input',
  },
  429: {
    label: 'Too many requests',
    guidance: 'You are sending requests too quickly. Please wait a moment and try again.',
    retryable: true,
    action: 'retry',
  },
  500: {
    label: 'Server error',
    guidance: 'An unexpected error occurred on the server. Please try again.',
    retryable: true,
    action: 'retry',
  },
  502: {
    label: 'Bad gateway',
    guidance: 'The server received an invalid response from an upstream service. Please try again.',
    retryable: true,
    action: 'retry',
  },
  503: {
    label: 'Service unavailable',
    guidance: 'The service is temporarily unavailable. Please try again in a moment.',
    retryable: true,
    action: 'retry',
  },
  504: {
    label: 'Gateway timeout',
    guidance: 'The request timed out. Please try again.',
    retryable: true,
    action: 'retry',
  },
}

// ── Backend error code overrides ────────────────────────────────────
// When the backend sends a specific error code in the JSON body,
// these override the generic status-based message.

const ERROR_CODE_MAP = {
  workspace_not_found: {
    label: 'Workspace not found',
    guidance: 'This workspace does not exist or has been deleted.',
    action: 'navigate_back',
  },
  member_already_exists: {
    label: 'Already a member',
    guidance: 'This user is already a member of the workspace.',
    action: 'dismiss',
  },
  member_not_found: {
    label: 'Member not found',
    guidance: 'This member could not be found in the workspace.',
    action: 'refresh',
  },
  file_already_exists: {
    label: 'File already exists',
    guidance: 'A file with this name already exists. Choose a different name.',
    action: 'rename',
  },
  path_traversal: {
    label: 'Invalid path',
    guidance: 'The file path is not allowed. Paths must stay within the workspace.',
    action: 'fix_input',
  },
  approval_already_decided: {
    label: 'Already decided',
    guidance: 'This approval has already been accepted or rejected.',
    action: 'refresh',
  },
}

// ── Public API ──────────────────────────────────────────────────────

/**
 * Resolve an API error into a user-friendly info object.
 *
 * @param {number} status   - HTTP status code
 * @param {string} [code]   - Backend error code from response body (e.g. 'workspace_not_found')
 * @param {string} [detail] - Backend detail message
 * @returns {{ label: string, guidance: string, detail?: string, retryable: boolean, action: string, status: number }}
 */
export function resolveApiError(status, code, detail) {
  // Prefer backend error code override if available.
  const codeInfo = code ? ERROR_CODE_MAP[code] : null
  const statusInfo = STATUS_MAP[status] || STATUS_MAP[500]

  return {
    status,
    label: codeInfo?.label || statusInfo.label,
    guidance: codeInfo?.guidance || statusInfo.guidance,
    detail: detail || undefined,
    retryable: statusInfo.retryable ?? false,
    action: codeInfo?.action || statusInfo.action,
  }
}

/**
 * Extract a structured error from a fetch response or caught error.
 *
 * @param {Error} error - Error thrown by fetch or fetchJson
 * @returns {{ label: string, guidance: string, detail?: string, retryable: boolean, action: string, status: number }}
 */
export function resolveFromError(error) {
  const status = error?.status || 0
  const code = error?.data?.error || error?.data?.code || error?.code || ''
  const detail = error?.data?.detail || error?.message || ''
  return resolveApiError(status, code, detail)
}
