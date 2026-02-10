/**
 * authSSE — EventSource wrapper with query-param token auth and auto-refresh.
 *
 * For long-lived SSE subscriptions (e.g., /v1/events/sse) that require
 * auth via query-param tokens. Handles token expiry by reconnecting
 * with a fresh token from the provided refresh function.
 *
 * For POST-based SSE (e.g., messages/stream), use fetch() with
 * ReadableStream and Authorization headers instead — EventSource
 * only supports GET.
 *
 * @module utils/authSSE
 */

const MAX_RECONNECTS = 5
const INITIAL_RECONNECT_MS = 1000
const MAX_RECONNECT_MS = 30000

/**
 * Create an authenticated EventSource connection with auto-refresh.
 *
 * @param {Object} options
 * @param {string} options.url       - Full SSE endpoint URL (without token param)
 * @param {string} options.token     - Initial query-param token
 * @param {() => Promise<string|null>} options.refreshToken
 *   Async function that returns a fresh qpToken, or null if unavailable.
 *   Called when the connection drops (potential token expiry).
 * @param {(event: MessageEvent) => void} [options.onMessage]  - Handler for message events
 * @param {(event: Event) => void}        [options.onError]    - Handler for errors (after reconnect exhaustion)
 * @param {() => void}                    [options.onOpen]     - Handler for successful connection
 * @param {Object<string, (event: MessageEvent) => void>} [options.eventHandlers]
 *   Named event handlers, e.g. { 'item.delta': handler }
 * @returns {{ close: () => void }} Controller with close method
 */
export function createAuthSSE({
  url,
  token,
  refreshToken,
  onMessage,
  onError,
  onOpen,
  eventHandlers = {},
}) {
  let es = null
  let currentToken = token
  let reconnectCount = 0
  let closed = false
  let reconnectTimer = null

  function buildUrl(tkn) {
    const u = new URL(url)
    if (tkn) {
      u.searchParams.set('token', tkn)
    }
    return u.toString()
  }

  function attachListeners(source) {
    source.onopen = () => {
      reconnectCount = 0
      onOpen?.()
    }

    source.onmessage = (event) => {
      onMessage?.(event)
    }

    source.onerror = () => {
      // EventSource fires error on disconnect; attempt reconnect with fresh token
      source.close()
      if (!closed) {
        scheduleReconnect()
      }
    }

    // Attach named event handlers
    for (const [eventName, handler] of Object.entries(eventHandlers)) {
      source.addEventListener(eventName, handler)
    }
  }

  function connect(tkn) {
    if (closed) return
    es = new EventSource(buildUrl(tkn))
    attachListeners(es)
  }

  async function scheduleReconnect() {
    if (closed) return

    if (reconnectCount >= MAX_RECONNECTS) {
      onError?.(new Event('error'))
      return
    }

    const delay = Math.min(
      INITIAL_RECONNECT_MS * Math.pow(2, reconnectCount),
      MAX_RECONNECT_MS,
    )
    reconnectCount += 1

    reconnectTimer = setTimeout(async () => {
      if (closed) return

      // Try to get a fresh token
      try {
        const freshToken = await refreshToken()
        if (freshToken) {
          currentToken = freshToken
        }
      } catch {
        // Use existing token as fallback
      }

      connect(currentToken)
    }, delay)
  }

  // Initial connection
  connect(currentToken)

  return {
    /** Close the EventSource and stop reconnection attempts. */
    close() {
      closed = true
      if (reconnectTimer) {
        clearTimeout(reconnectTimer)
        reconnectTimer = null
      }
      if (es) {
        es.close()
        es = null
      }
    },
  }
}
