/**
 * apiErrors utility unit tests.
 *
 * Bead: bd-223o.14.3.1 (H3a)
 *
 * Validates:
 *   - resolveApiError returns correct info for each HTTP status.
 *   - Backend error code overrides generic status message.
 *   - Unknown status falls back to 500 defaults.
 *   - resolveFromError extracts status/code/detail from error objects.
 *   - Retryable flag is correct for 5xx vs 4xx.
 */

import { describe, it, expect } from 'vitest'
import { resolveApiError, resolveFromError } from './apiErrors.js'

describe('resolveApiError', () => {
  it('returns correct info for 401', () => {
    const info = resolveApiError(401)
    expect(info.label).toBe('Session expired')
    expect(info.action).toBe('sign_in')
    expect(info.retryable).toBe(false)
  })

  it('returns correct info for 403', () => {
    const info = resolveApiError(403)
    expect(info.label).toBe('Permission denied')
    expect(info.action).toBe('contact_admin')
    expect(info.retryable).toBe(false)
  })

  it('returns correct info for 409', () => {
    const info = resolveApiError(409)
    expect(info.label).toBe('Conflict')
    expect(info.action).toBe('refresh')
    expect(info.retryable).toBe(false)
  })

  it('returns correct info for 410', () => {
    const info = resolveApiError(410)
    expect(info.label).toBe('No longer available')
    expect(info.action).toBe('navigate_back')
    expect(info.retryable).toBe(false)
  })

  it('returns correct info for 503', () => {
    const info = resolveApiError(503)
    expect(info.label).toBe('Service unavailable')
    expect(info.action).toBe('retry')
    expect(info.retryable).toBe(true)
  })

  it('returns correct info for 500', () => {
    const info = resolveApiError(500)
    expect(info.label).toBe('Server error')
    expect(info.retryable).toBe(true)
  })

  it('returns correct info for 429', () => {
    const info = resolveApiError(429)
    expect(info.label).toBe('Too many requests')
    expect(info.retryable).toBe(true)
  })

  it('returns correct info for 400', () => {
    const info = resolveApiError(400)
    expect(info.label).toBe('Invalid request')
    expect(info.retryable).toBe(false)
  })

  it('returns correct info for 404', () => {
    const info = resolveApiError(404)
    expect(info.label).toBe('Not found')
    expect(info.action).toBe('navigate_back')
  })

  it('returns correct info for 422', () => {
    const info = resolveApiError(422)
    expect(info.label).toBe('Validation error')
    expect(info.action).toBe('fix_input')
  })

  it('falls back to 500 for unknown status', () => {
    const info = resolveApiError(999)
    expect(info.label).toBe('Server error')
    expect(info.retryable).toBe(true)
  })

  it('includes detail when provided', () => {
    const info = resolveApiError(400, null, 'name too long')
    expect(info.detail).toBe('name too long')
  })

  it('omits detail when not provided', () => {
    const info = resolveApiError(400)
    expect(info.detail).toBeUndefined()
  })

  // ── Backend error code overrides ──────────────────────────────

  it('overrides label with backend error code', () => {
    const info = resolveApiError(409, 'file_already_exists')
    expect(info.label).toBe('File already exists')
    expect(info.action).toBe('rename')
  })

  it('overrides with workspace_not_found', () => {
    const info = resolveApiError(404, 'workspace_not_found')
    expect(info.label).toBe('Workspace not found')
    expect(info.guidance).toContain('deleted')
  })

  it('overrides with member_already_exists', () => {
    const info = resolveApiError(409, 'member_already_exists')
    expect(info.label).toBe('Already a member')
    expect(info.action).toBe('dismiss')
  })

  it('overrides with approval_already_decided', () => {
    const info = resolveApiError(409, 'approval_already_decided')
    expect(info.label).toBe('Already decided')
  })

  it('uses status defaults for unknown error code', () => {
    const info = resolveApiError(409, 'something_weird')
    expect(info.label).toBe('Conflict')
  })

  it('preserves retryable from status when code overrides label', () => {
    const info = resolveApiError(503, 'workspace_not_found')
    // workspace_not_found overrides label but retryable comes from status
    expect(info.retryable).toBe(true)
  })
})

describe('resolveFromError', () => {
  it('extracts status and detail from error object', () => {
    const err = new Error('Something broke')
    err.status = 500
    err.data = { detail: 'Internal server error' }
    const info = resolveFromError(err)
    expect(info.status).toBe(500)
    expect(info.label).toBe('Server error')
    expect(info.detail).toBe('Internal server error')
  })

  it('extracts backend error code from data.error', () => {
    const err = new Error('Conflict')
    err.status = 409
    err.data = { error: 'file_already_exists', detail: 'File foo.txt exists' }
    const info = resolveFromError(err)
    expect(info.label).toBe('File already exists')
    expect(info.detail).toBe('File foo.txt exists')
  })

  it('extracts backend error code from data.code', () => {
    const err = new Error('Conflict')
    err.status = 409
    err.data = { code: 'member_already_exists' }
    const info = resolveFromError(err)
    expect(info.label).toBe('Already a member')
  })

  it('handles error with no status', () => {
    const err = new Error('Network failure')
    const info = resolveFromError(err)
    expect(info.status).toBe(0)
    expect(info.label).toBe('Server error')
    expect(info.detail).toBe('Network failure')
  })

  it('handles null error', () => {
    const info = resolveFromError(null)
    expect(info.status).toBe(0)
    expect(info.label).toBe('Server error')
  })
})
