/**
 * useWorkspacePlugins – WebSocket hook for live workspace plugin updates.
 *
 * Connects to /ws/plugins, listens for {type:"plugin_changed"} events,
 * and calls the provided callback so the app can refetch capabilities
 * and reload workspace panels.
 *
 * @module hooks/useWorkspacePlugins
 */

import { useEffect, useRef } from 'react'
import { openWebSocket } from '../utils/transport'
import { routes } from '../utils/routes'

/**
 * @param {Object} opts
 * @param {() => void} opts.onPluginChanged - Called when a plugin file changes
 * @param {boolean} [opts.enabled=true] - Whether to connect
 */
export function useWorkspacePlugins({ onPluginChanged, enabled = true }) {
  const wsRef = useRef(null)
  const reconnectTimer = useRef(null)
  const reconnectDelayMs = useRef(1000)
  const onPluginChangedRef = useRef(onPluginChanged)

  useEffect(() => {
    onPluginChangedRef.current = onPluginChanged
  }, [onPluginChanged])

  useEffect(() => {
    if (!enabled) return

    let disposed = false

    const connect = () => {
      if (disposed) return

      const route = routes.ws.plugins()
      const ws = openWebSocket(route.path, { query: route.query })
      wsRef.current = ws

      ws.onopen = () => {
        reconnectDelayMs.current = 1000
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.type === 'plugin_changed') {
            onPluginChangedRef.current?.()
          }
        } catch {
          // ignore malformed messages
        }
      }

      ws.onclose = () => {
        if (!disposed) {
          // Exponential backoff to avoid hammering unavailable endpoints.
          const delay = reconnectDelayMs.current
          reconnectDelayMs.current = Math.min(delay * 2, 30000)
          reconnectTimer.current = setTimeout(connect, delay)
        }
      }

      ws.onerror = () => {
        // onclose will fire after onerror, triggering reconnect
      }
    }

    connect()

    return () => {
      disposed = true
      clearTimeout(reconnectTimer.current)
      reconnectDelayMs.current = 1000
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [enabled])
}
