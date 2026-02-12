/**
 * WebSocket auth helpers for hosted mode (bd-1pwb.7.3).
 *
 * Browser WebSocket API doesn't support custom headers in the constructor.
 * In hosted mode, pass auth tokens as query parameters with short TTL.
 *
 * @module utils/wsAuth
 */

/**
 * Append a token query parameter to a WebSocket URL.
 *
 * @param {string} url - WebSocket URL (may already have query params)
 * @param {string|null} token - Auth token to append (null = no-op)
 * @returns {string} URL with token query param if provided
 */
export function appendWsToken(url, token) {
  if (!token) return url
  const separator = url.includes('?') ? '&' : '?'
  return `${url}${separator}token=${encodeURIComponent(token)}`
}
