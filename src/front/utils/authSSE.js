/**
 * Auth-aware SSE client using EventSource + qpToken.
 *
 * Appends the short-lived query-param token to SSE URLs.
 * On connection error, calls onTokenExpired so the caller
 * can refresh tokens and reconnect.
 *
 * @module utils/authSSE
 */

/**
 * Create an EventSource with auth token in query params.
 *
 * @param {string} url        - SSE endpoint URL
 * @param {string|null} qpToken - Query-param token (appended as ?token=...)
 * @param {Object} [options]
 * @param {function} [options.onMessage]      - Called with each parsed SSE event
 * @param {function} [options.onTokenExpired] - Called when connection fails (likely token expiry)
 * @param {function} [options.onError]        - Called on EventSource error
 * @param {function} [options.onOpen]         - Called when connection opens
 * @returns {{ close: () => void }} Handle to close the connection
 */
export function createAuthSSE(url, qpToken, options = {}) {
  const { onMessage, onTokenExpired, onError, onOpen } = options

  // Append token as query param
  const sep = url.includes('?') ? '&' : '?'
  const fullUrl = qpToken ? `${url}${sep}token=${encodeURIComponent(qpToken)}` : url

  const es = new EventSource(fullUrl)
  let errorCount = 0

  es.onopen = () => {
    errorCount = 0
    onOpen?.()
  }

  es.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      onMessage?.(data)
    } catch {
      // Non-JSON message, pass raw
      onMessage?.({ raw: event.data })
    }
  }

  es.onerror = (event) => {
    errorCount++
    onError?.(event)

    // After repeated errors, likely token expiry — notify caller
    if (errorCount >= 2 && es.readyState === EventSource.CLOSED) {
      onTokenExpired?.()
    }
  }

  return {
    close: () => {
      es.close()
    },
  }
}

export default createAuthSSE
