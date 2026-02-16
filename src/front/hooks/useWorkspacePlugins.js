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
import { buildApiUrl } from '../utils/apiBase'

/**
 * @param {Object} opts
 * @param {() => void} opts.onPluginChanged - Called when a plugin file changes
 * @param {boolean} [opts.enabled=true] - Whether to connect
 */
export function useWorkspacePlugins({ onPluginChanged, enabled = true }) {
  const wsRef = useRef(null)
  const reconnectTimer = useRef(null)
  const onPluginChangedRef = useRef(onPluginChanged)
  onPluginChangedRef.current = onPluginChanged

  useEffect(() => {
    if (!enabled) return

    let disposed = false

    const connect = () => {
      if (disposed) return

      // Build WebSocket URL from API base
      const httpUrl = buildApiUrl('/ws/plugins')
      const wsUrl = httpUrl.replace(/^http/, 'ws')

      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

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
          // Reconnect after a short delay
          reconnectTimer.current = setTimeout(connect, 3000)
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
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [enabled])
}
