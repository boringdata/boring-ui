import React, { useEffect, useRef } from 'react'
import { Terminal as XTerm } from 'xterm'
import { FitAddon } from 'xterm-addon-fit'
import 'xterm/css/xterm.css'
import { useTheme } from '../hooks/useTheme'
import { getStorageKey, STORAGE_KEYS } from '../utils/storage'

// Terminal color schemes for light/dark mode
export const TERMINAL_THEMES = {
  light: {
    background: '#f8fafc',
    foreground: '#111827',
    cursor: '#111827',
    selectionBackground: '#bfdbfe',
    black: '#0f172a',
    red: '#dc2626',
    green: '#16a34a',
    yellow: '#f59e0b',
    blue: '#2563eb',
    magenta: '#db2777',
    cyan: '#0891b2',
    white: '#e2e8f0',
  },
  dark: {
    background: '#0f172a',
    foreground: '#e2e8f0',
    cursor: '#e2e8f0',
    selectionBackground: '#334155',
    black: '#0f172a',
    red: '#ef4444',
    green: '#22c55e',
    yellow: '#f59e0b',
    blue: '#3b82f6',
    magenta: '#ec4899',
    cyan: '#06b6d4',
    white: '#f1f5f9',
  },
}

const HISTORY_LIMIT_BYTES = 200000

const getHistoryKey = (sessionId, historyPrefix) => {
  if (!sessionId) return null
  // Use custom prefix if provided, otherwise use storage utility with PTY_HISTORY key
  if (historyPrefix) {
    return `${historyPrefix}-${sessionId}`
  }
  return getStorageKey(`${STORAGE_KEYS.PTY_HISTORY}-${sessionId}`)
}

const loadStoredHistory = (sessionId, historyPrefix) => {
  const key = getHistoryKey(sessionId, historyPrefix)
  if (!key) return ''
  try {
    const raw = localStorage.getItem(key)
    return typeof raw === 'string' ? raw : ''
  } catch {
    return ''
  }
}

const saveStoredHistory = (sessionId, text, historyPrefix) => {
  const key = getHistoryKey(sessionId, historyPrefix)
  if (!key) return
  const normalized = text.length > HISTORY_LIMIT_BYTES
    ? text.slice(-HISTORY_LIMIT_BYTES)
    : text
  try {
    localStorage.setItem(key, normalized)
  } catch {
    // Ignore storage errors
  }
}

/**
 * Build a WebSocket URL with optional parameters.
 * This helper is exported for consumers who need to construct URLs dynamically.
 *
 * @param {Object} options - URL building options
 * @param {string} [options.baseUrl] - Base WebSocket URL (e.g., 'wss://example.com')
 * @param {string} [options.path='/ws/pty'] - WebSocket path
 * @param {string} [options.sessionId] - Session identifier
 * @param {boolean} [options.resume] - Whether to resume existing session
 * @param {boolean} [options.forceNew] - Force new session creation
 * @param {string} [options.provider] - Provider name (e.g., 'claude', 'shell')
 * @param {string} [options.sessionName] - Human-readable session name
 * @returns {string} Complete WebSocket URL
 */
export const buildWsUrl = ({
  baseUrl,
  path = '/ws/pty',
  sessionId,
  resume,
  forceNew,
  provider,
  sessionName,
} = {}) => {
  let wsBase = baseUrl
  if (!wsBase) {
    // Default: derive from current page location
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    wsBase = `${protocol}://${window.location.host}`
  }

  const params = new URLSearchParams()
  if (sessionId) {
    params.set('session_id', sessionId)
  }
  if (resume) {
    params.set('resume', '1')
  }
  if (forceNew) {
    params.set('force_new', '1')
  }
  if (provider) {
    params.set('provider', provider)
  }
  if (sessionName) {
    params.set('session_name', sessionName)
  }
  const query = params.toString()
  return `${wsBase}${path}${query ? `?${query}` : ''}`
}

// Legacy helper for backwards compatibility with existing app code
const buildSocketUrl = (sessionId, resume, forceNew, provider, sessionName) => {
  const apiBase = import.meta.env.VITE_API_URL || ''
  let wsBase
  if (apiBase) {
    wsBase = apiBase.replace(/^http/, 'ws')
  } else {
    wsBase = undefined // Will use default from buildWsUrl
  }
  return buildWsUrl({
    baseUrl: wsBase,
    sessionId,
    resume,
    forceNew,
    provider,
    sessionName,
  })
}

/**
 * Reusable Terminal component with xterm.js integration.
 *
 * @param {Object} props - Component props
 * @param {string} [props.wsUrl] - WebSocket URL (if provided, overrides legacy URL building)
 * @param {string} [props.sessionId] - Session identifier for history persistence
 * @param {function} [props.onSessionChange] - Callback when session ID changes: (newId: string) => void
 * @param {function} [props.onData] - Callback for terminal data output: (data: string) => void
 * @param {string} [props.className] - Additional CSS class names
 * @param {boolean} [props.isActive=true] - Whether the terminal is active/visible
 * @param {function} [props.onFirstPrompt] - Legacy: Callback for first user prompt
 * @param {string} [props.provider='claude'] - Legacy: Provider name for URL building
 * @param {string} [props.sessionName] - Legacy: Human-readable session name
 * @param {boolean} [props.resume] - Legacy: Whether to resume existing session
 * @param {function} [props.onSessionStarted] - Legacy: Callback when session connects
 * @param {function} [props.onResumeMissing] - Legacy: Callback when resume session not found
 * @param {string} [props.bannerMessage] - Message to display in terminal
 * @param {function} [props.onBannerShown] - Callback after banner message is shown
 * @param {string} [props.historyPrefix] - Custom prefix for localStorage history keys
 * @param {Object} [props.theme] - Custom terminal theme (overrides auto light/dark)
 */
export default function Terminal({
  // New standalone props
  wsUrl,
  onSessionChange,
  onData,
  className,
  historyPrefix,
  theme: customTheme,
  // Legacy props for backwards compatibility
  isActive = true,
  onFirstPrompt,
  provider = 'claude',
  sessionId,
  sessionName,
  resume,
  onSessionStarted,
  onResumeMissing,
  bannerMessage,
  onBannerShown,
}) {
  const { theme: appTheme } = useTheme()
  const containerRef = useRef(null)
  const termRef = useRef(null)
  const fitAddonRef = useRef(null)
  const socketRef = useRef(null)
  const isActiveRef = useRef(isActive)
  const onFirstPromptRef = useRef(onFirstPrompt)
  const onSessionStartedRef = useRef(onSessionStarted)
  const onResumeMissingRef = useRef(onResumeMissing)
  const onBannerShownRef = useRef(onBannerShown)
  const onSessionChangeRef = useRef(onSessionChange)
  const onDataRef = useRef(onData)
  const inputBufferRef = useRef('')
  const firstPromptSentRef = useRef(false)
  const sessionStartedRef = useRef(false)
  const historyAppliedRef = useRef(false)
  const openedRef = useRef(false)
  const rendererReadyRef = useRef(false)
  const openAttemptRef = useRef(null)
  const openRetryRef = useRef(null)
  const renderFallbackRef = useRef(null)
  const resizeObserverRef = useRef(null)
  const historyBufferRef = useRef('')
  const historyFallbackTimerRef = useRef(null)
  const historySourceRef = useRef(null)
  // Use provider from props, default to 'claude'
  const providerKey = provider || 'claude'
  const providerLabel = providerKey === 'shell' ? 'Shell' : 'Claude'

  useEffect(() => {
    isActiveRef.current = isActive
    if (!isActive) return
    if (fitAddonRef.current && termRef.current && openedRef.current && rendererReadyRef.current) {
      // Double requestAnimationFrame to ensure renderer is stable
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          try {
            // Extra guard: check if terminal element is still in DOM
            if (!containerRef.current?.isConnected) return
            fitAddonRef.current.fit()
            termRef.current.focus()
          } catch {
            // Ignore fit errors while the terminal is initializing.
          }
        })
      })
    }
    if (!openedRef.current && openAttemptRef.current) {
      openAttemptRef.current()
    }
  }, [isActive])

  useEffect(() => {
    onFirstPromptRef.current = onFirstPrompt
    onSessionStartedRef.current = onSessionStarted
    onResumeMissingRef.current = onResumeMissing
    onBannerShownRef.current = onBannerShown
    onSessionChangeRef.current = onSessionChange
    onDataRef.current = onData
  }, [onFirstPrompt, onSessionStarted, onResumeMissing, onBannerShown, onSessionChange, onData])

  // Update terminal theme when app theme changes (unless custom theme is provided)
  useEffect(() => {
    if (termRef.current && !customTheme) {
      termRef.current.options.theme = TERMINAL_THEMES[appTheme] || TERMINAL_THEMES.light
    }
  }, [appTheme, customTheme])

  useEffect(() => {
    if (!containerRef.current) return

    openedRef.current = false
    rendererReadyRef.current = false
    sessionStartedRef.current = false
    firstPromptSentRef.current = false
    inputBufferRef.current = ''
    historyBufferRef.current = ''
    historySourceRef.current = null

    // Use custom theme if provided, otherwise use app theme
    const termTheme = customTheme || TERMINAL_THEMES[appTheme] || TERMINAL_THEMES.light
    const term = new XTerm({
      cursorBlink: true,
      convertEol: false,
      fontFamily: '"IBM Plex Mono", "SFMono-Regular", Menlo, monospace',
      fontSize: 13,
      theme: termTheme,
    })
    const fitAddon = new FitAddon()
    term.loadAddon(fitAddon)
    termRef.current = term
    fitAddonRef.current = fitAddon

    let shouldReconnect = true
    let reconnectTimer = null
    let connectionStarted = false
    let retryCount = 0
    let disposed = false
    const MAX_RETRIES = 10
    const INITIAL_RETRY_DELAY = 500
    const storedHistory = loadStoredHistory(sessionId, historyPrefix)
    historyBufferRef.current = storedHistory

    const sendResize = () => {
      if (!isActiveRef.current || !openedRef.current) return
      if (!containerRef.current) return
      if (containerRef.current.clientWidth === 0 || containerRef.current.clientHeight === 0) {
        return
      }
      if (!rendererReadyRef.current) return
      try {
        fitAddon.fit()
      } catch {
        return
      }
      const socket = socketRef.current
      if (!socket || socket.readyState !== WebSocket.OPEN) return
      socket.send(
        JSON.stringify({
          type: 'resize',
          cols: term.cols,
          rows: term.rows,
        }),
      )
    }

    const connect = () => {
      if (connectionStarted) return
      connectionStarted = true
      historyAppliedRef.current = false
      // Use wsUrl prop if provided, otherwise fall back to legacy URL building
      const socketUrl = wsUrl || buildSocketUrl(sessionId, resume, false, providerKey, sessionName)
      const socket = new WebSocket(socketUrl)
      socketRef.current = socket
      let resumeMissingNotified = false

      const applyHistory = (source, chunk) => {
        if (!chunk) return
        if (!historyAppliedRef.current) {
          historyAppliedRef.current = true
          historySourceRef.current = source
          historyBufferRef.current = ''
          term.reset()
        }
        historyBufferRef.current += chunk
        if (historyBufferRef.current.length > HISTORY_LIMIT_BYTES) {
          historyBufferRef.current = historyBufferRef.current.slice(-HISTORY_LIMIT_BYTES)
        }
        term.write(chunk)
        saveStoredHistory(sessionId, historyBufferRef.current, historyPrefix)
      }

      const appendOutput = (chunk) => {
        if (!chunk) return
        historyBufferRef.current += chunk
        if (historyBufferRef.current.length > HISTORY_LIMIT_BYTES) {
          historyBufferRef.current = historyBufferRef.current.slice(-HISTORY_LIMIT_BYTES)
        }
        term.write(chunk)
        saveStoredHistory(sessionId, historyBufferRef.current, historyPrefix)
        // Call onData callback if provided
        onDataRef.current?.(chunk)
      }

      const handlePayload = (payload) => {
        if (payload.type === 'session_not_found') {
          if (resume && !resumeMissingNotified) {
            resumeMissingNotified = true
            term.writeln(
              `\r\n[bridge] No saved conversation found. Starting a new session...\r\n`,
            )
            onResumeMissingRef.current?.()
          }
          return
        }

        // Handle session_id from server (new session created)
        if (payload.type === 'session_id' && typeof payload.session_id === 'string') {
          onSessionChangeRef.current?.(payload.session_id)
          return
        }

        if (payload.type === 'history' && typeof payload.data === 'string') {
          if (historySourceRef.current === 'local') {
            return
          }
          if (historyFallbackTimerRef.current) {
            window.clearTimeout(historyFallbackTimerRef.current)
            historyFallbackTimerRef.current = null
          }
          applyHistory('server', payload.data)
          return
        }

        if (payload.type === 'output' && typeof payload.data === 'string') {
          if (
            resume &&
            !resumeMissingNotified &&
            payload.data.includes('No conversation found with session ID')
          ) {
            resumeMissingNotified = true
            term.writeln(
              `\r\n[bridge] No saved conversation found. Starting a new session...\r\n`,
            )
            onResumeMissingRef.current?.()
          }
          appendOutput(payload.data)
        }

        if (payload.type === 'error') {
          term.writeln(`\r\n[bridge] ${payload.data}\r\n`)
        }

        if (payload.type === 'exit') {
          const code = payload.code ?? 'unknown'
          term.writeln(`\r\n[bridge] ${providerLabel} CLI exited (${code}).\r\n`)
        }
      }

      const handleRaw = (raw) => {
        let payload
        try {
          payload = JSON.parse(raw)
        } catch {
          payload = { type: 'output', data: raw }
        }
        handlePayload(payload)
      }

      socket.addEventListener('message', (event) => {
        const data = event.data
        if (typeof data === 'string') {
          handleRaw(data)
          return
        }
        if (data instanceof ArrayBuffer) {
          handleRaw(new TextDecoder().decode(data))
          return
        }
        if (data instanceof Blob) {
          data
            .text()
            .then(handleRaw)
            .catch(() => {
              handleRaw('')
            })
          return
        }
        handleRaw(String(data ?? ''))
      })

      socket.addEventListener('open', () => {
        if (isActiveRef.current) {
          sendResize()
        }
        if (onSessionStartedRef.current && !sessionStartedRef.current) {
          sessionStartedRef.current = true
          onSessionStartedRef.current()
        }
        if (storedHistory && !historyAppliedRef.current) {
          historyFallbackTimerRef.current = window.setTimeout(() => {
            if (historyAppliedRef.current || historySourceRef.current === 'server') return
            historySourceRef.current = 'local'
            historyAppliedRef.current = true
            historyBufferRef.current = storedHistory
            term.reset()
            term.write(storedHistory)
          }, 200)
        }
      })

      socket.addEventListener('error', () => {
        // Only show error message after a few retries to avoid spam during startup
        if (retryCount >= 3) {
          term.writeln(`\r\n[bridge] Unable to connect. Retrying...\r\n`)
        }
      })

      socket.addEventListener('close', () => {
        if (!shouldReconnect) return
        retryCount++
        if (retryCount > MAX_RETRIES) {
          term.writeln(`\r\n[bridge] Max retries reached. Click "New session" to try again.\r\n`)
          return
        }
        reconnectTimer = window.setTimeout(() => {
          connectionStarted = false
          connect()
        }, INITIAL_RETRY_DELAY)
      })
    }

    const handlePageUnload = () => {
      shouldReconnect = false
      const socket = socketRef.current
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.close()
      }
    }

    const resizeListener = () => {
      const socket = socketRef.current
      if (socket?.readyState === WebSocket.OPEN && isActiveRef.current) {
        sendResize()
      }
    }

    const resizeObserver =
      typeof ResizeObserver !== 'undefined'
        ? new ResizeObserver(() => {
            if (!isActiveRef.current) return
            sendResize()
          })
        : null

    if (resizeObserver) {
      resizeObserver.observe(containerRef.current)
      resizeObserverRef.current = resizeObserver
    }

    window.addEventListener('resize', resizeListener)
    window.addEventListener('beforeunload', handlePageUnload)

    const captureFirstPrompt = (data) => {
      if (!onFirstPromptRef.current || firstPromptSentRef.current) return
      // eslint-disable-next-line no-control-regex
      const sanitized = data.replace(/\x1b\[[0-9;]*[A-Za-z]/g, '')
      let buffer = inputBufferRef.current

      for (const char of sanitized) {
        if (char === '\r' || char === '\n') {
          const prompt = buffer.trim()
          if (prompt) {
            firstPromptSentRef.current = true
            onFirstPromptRef.current(prompt)
          }
          buffer = ''
        } else if (char === '\u007f') {
          buffer = buffer.slice(0, -1)
        } else {
          buffer += char
        }
      }

      inputBufferRef.current = buffer
    }

    term.onData((data) => {
      captureFirstPrompt(data)
      const socket = socketRef.current
      if (socket?.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: 'input', data }))
      }
    })

    const canOpen = () => {
      if (!containerRef.current) return false
      if (!containerRef.current.isConnected) return false
      const rects = containerRef.current.getClientRects()
      if (!rects.length) return false
      if (containerRef.current.clientWidth === 0 || containerRef.current.clientHeight === 0) {
        return false
      }
      const style = window.getComputedStyle(containerRef.current)
      if (style.visibility === 'hidden' || style.display === 'none') {
        return false
      }
      return true
    }

    const attemptOpen = () => {
      if (disposed || openedRef.current || !isActiveRef.current) return
      if (!canOpen()) {
        openRetryRef.current = window.setTimeout(attemptOpen, 60)
        return
      }

      try {
        term.open(containerRef.current)
        openedRef.current = true
      } catch {
        openRetryRef.current = window.setTimeout(attemptOpen, 60)
        return
      }

      const finalizeRenderer = () => {
        if (rendererReadyRef.current || disposed) return
        rendererReadyRef.current = true
        try {
          fitAddon.fit()
          if (isActiveRef.current) {
            term.focus()
          }
        } catch {
          // Ignore fit errors while the renderer is initializing.
        }
        if (isActiveRef.current) {
          sendResize()
        }
      }

      // Wait for renderer to be fully ready before marking as ready.
      // Use multiple frames to ensure xterm's internal state is settled.
      const renderSubscription = term.onRender(() => {
        renderSubscription.dispose()
        if (renderFallbackRef.current) {
          window.clearTimeout(renderFallbackRef.current)
          renderFallbackRef.current = null
        }
        // Double requestAnimationFrame to ensure renderer is fully initialized.
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            finalizeRenderer()
          })
        })
      })

      renderFallbackRef.current = window.setTimeout(() => {
        finalizeRenderer()
      }, 120)

      if (document?.fonts?.ready) {
        document.fonts.ready.then(() => {
          if (disposed || !openedRef.current) return
          try {
            fitAddon.fit()
          } catch {
            // Ignore fit errors while the renderer is initializing.
          }
          if (isActiveRef.current) {
            sendResize()
          }
        })
      }

      connect()
    }

    openAttemptRef.current = attemptOpen

    if (isActiveRef.current) {
      attemptOpen()
    }

    return () => {
      window.removeEventListener('resize', resizeListener)
      window.removeEventListener('beforeunload', handlePageUnload)
      shouldReconnect = false
      disposed = true
      if (reconnectTimer) {
        window.clearTimeout(reconnectTimer)
      }
      if (openRetryRef.current) {
        window.clearTimeout(openRetryRef.current)
      }
      if (renderFallbackRef.current) {
        window.clearTimeout(renderFallbackRef.current)
        renderFallbackRef.current = null
      }
      if (historyFallbackTimerRef.current) {
        window.clearTimeout(historyFallbackTimerRef.current)
        historyFallbackTimerRef.current = null
      }
      if (resizeObserverRef.current) {
        resizeObserverRef.current.disconnect()
        resizeObserverRef.current = null
      }
      if (socketRef.current) {
        socketRef.current.close()
      }
      term.dispose()
    }
  // Note: appTheme and providerLabel are intentionally excluded from dependencies
  // to avoid reconnecting the terminal when theme changes. Theme updates are
  // handled by a separate effect that updates the terminal theme without reconnecting.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [providerKey, sessionId, sessionName, resume, wsUrl, historyPrefix, customTheme])

  useEffect(() => {
    if (!bannerMessage) return
    const term = termRef.current
    if (!term) return
    term.writeln(`\r\n[bridge] ${bannerMessage}\r\n`)
    onBannerShownRef.current?.()
  }, [bannerMessage])

  // Update terminal theme when app theme changes (unless custom theme is provided)
  useEffect(() => {
    const term = termRef.current
    if (!term) return
    // If custom theme is provided, use it; otherwise use app theme
    const newTheme = customTheme || TERMINAL_THEMES[appTheme] || TERMINAL_THEMES.light
    term.options.theme = newTheme
  }, [appTheme, customTheme])

  // Build class name string
  const classNames = ['terminal', className].filter(Boolean).join(' ')

  return (
    <div
      className={classNames}
      ref={containerRef}
      tabIndex={0}
      onMouseDown={() => termRef.current?.focus()}
    />
  )
}
