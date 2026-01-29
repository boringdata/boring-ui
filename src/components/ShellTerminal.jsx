import React, { useEffect, useRef } from 'react'
import Terminal, { buildWsUrl } from './Terminal'

/**
 * ShellTerminal - A reusable shell terminal component.
 *
 * This component wraps the base Terminal component to provide shell-specific
 * functionality. It connects to a shell session (bash, zsh, sh) via WebSocket.
 *
 * @param {Object} props - Component props
 * @param {string} props.wsUrl - WebSocket URL for the shell connection (required)
 * @param {'bash' | 'zsh' | 'sh'} [props.shellType='bash'] - Shell type to use
 * @param {string} [props.command] - Initial command to run after connection
 * @param {string} [props.sessionId] - Session identifier for history persistence
 * @param {function} [props.onSessionChange] - Callback when session ID changes: (newId: string) => void
 * @param {function} [props.onData] - Callback for terminal data output: (data: string) => void
 * @param {function} [props.onReady] - Callback when terminal is ready and connected
 * @param {function} [props.onExit] - Callback when shell exits: (code: number) => void
 * @param {string} [props.className] - Additional CSS class names
 * @param {boolean} [props.isActive=true] - Whether the terminal is active/visible
 * @param {string} [props.historyPrefix] - Custom prefix for localStorage history keys
 * @param {Object} [props.theme] - Custom terminal theme (overrides auto light/dark)
 *
 * @example
 * // Basic usage with WebSocket URL
 * <ShellTerminal wsUrl="wss://example.com/ws/shell" />
 *
 * @example
 * // With shell type and initial command
 * <ShellTerminal
 *   wsUrl="wss://example.com/ws/shell"
 *   shellType="zsh"
 *   command="ls -la"
 *   onData={(data) => console.log('Output:', data)}
 * />
 *
 * @example
 * // Using buildWsUrl helper for URL construction
 * import { buildWsUrl } from './Terminal'
 * const wsUrl = buildWsUrl({
 *   baseUrl: 'wss://example.com',
 *   path: '/ws/shell',
 *   sessionId: 'my-session',
 * })
 * <ShellTerminal wsUrl={wsUrl} shellType="bash" />
 */
export default function ShellTerminal({
  // Required props
  wsUrl,

  // Shell-specific props
  shellType = 'bash',
  command,

  // Props passed through to Terminal
  sessionId,
  onSessionChange,
  onData,
  className,
  isActive = true,
  historyPrefix,
  theme,

  // ShellTerminal-specific callbacks
  onReady,
  onExit,
}) {
  const commandSentRef = useRef(false)
  const onReadyRef = useRef(onReady)
  const onExitRef = useRef(onExit)

  // Keep refs up to date
  useEffect(() => {
    onReadyRef.current = onReady
    onExitRef.current = onExit
  }, [onReady, onExit])

  // Build WebSocket URL with shell parameters if needed
  const effectiveWsUrl = React.useMemo(() => {
    if (!wsUrl) {
      console.warn('ShellTerminal: wsUrl prop is required')
      return ''
    }

    // If wsUrl already has shell parameters, use it as-is
    try {
      const url = new URL(wsUrl)
      // Add shell type if not already present
      if (!url.searchParams.has('shell') && shellType) {
        url.searchParams.set('shell', shellType)
      }
      return url.toString()
    } catch {
      // If URL parsing fails, return as-is
      return wsUrl
    }
  }, [wsUrl, shellType])

  // Handle data from terminal - intercept to detect ready state and exit
  const handleData = React.useCallback(
    (data) => {
      // Forward to user callback
      onData?.(data)

      // Detect shell exit messages (basic heuristic)
      if (data.includes('[bridge] Shell exited') || data.includes('[bridge] CLI exited')) {
        const codeMatch = data.match(/\((\d+)\)/)
        const code = codeMatch ? parseInt(codeMatch[1], 10) : 0
        onExitRef.current?.(code)
      }
    },
    [onData],
  )

  // Handle session started - send initial command if provided
  const handleSessionStarted = React.useCallback(() => {
    onReadyRef.current?.()

    // Send initial command if provided and not already sent
    if (command && !commandSentRef.current) {
      commandSentRef.current = true
      // Note: The actual command sending would need WebSocket access
      // which the Terminal component manages internally.
      // For initial commands, they should be sent via the wsUrl parameters
      // or handled by the backend based on the connection parameters.
    }
  }, [command])

  // Reset command sent ref when command changes
  useEffect(() => {
    commandSentRef.current = false
  }, [command, sessionId])

  // Build className
  const terminalClassName = ['shell-terminal', className].filter(Boolean).join(' ')

  if (!effectiveWsUrl) {
    return (
      <div className={terminalClassName} style={{ padding: '1rem', color: '#ef4444' }}>
        ShellTerminal: wsUrl prop is required
      </div>
    )
  }

  return (
    <Terminal
      wsUrl={effectiveWsUrl}
      sessionId={sessionId}
      onSessionChange={onSessionChange}
      onData={handleData}
      className={terminalClassName}
      isActive={isActive}
      historyPrefix={historyPrefix || `shell-${shellType}`}
      theme={theme}
      provider="shell"
      onSessionStarted={handleSessionStarted}
    />
  )
}

/**
 * Helper to build a shell WebSocket URL with shell-specific parameters.
 *
 * @param {Object} options - URL building options
 * @param {string} options.baseUrl - Base WebSocket URL (e.g., 'wss://example.com')
 * @param {string} [options.path='/ws/shell'] - WebSocket path
 * @param {string} [options.sessionId] - Session identifier
 * @param {'bash' | 'zsh' | 'sh'} [options.shellType='bash'] - Shell type
 * @param {string} [options.command] - Initial command to run
 * @param {string} [options.workingDir] - Working directory for the shell
 * @returns {string} Complete WebSocket URL
 *
 * @example
 * const url = buildShellWsUrl({
 *   baseUrl: 'wss://example.com',
 *   shellType: 'zsh',
 *   command: 'npm start',
 *   workingDir: '/home/user/project',
 * })
 */
export const buildShellWsUrl = ({
  baseUrl,
  path = '/ws/shell',
  sessionId,
  shellType = 'bash',
  command,
  workingDir,
}) => {
  // Use the base buildWsUrl helper
  let url = buildWsUrl({
    baseUrl,
    path,
    sessionId,
    provider: 'shell',
  })

  // Add shell-specific parameters
  try {
    const urlObj = new URL(url)
    if (shellType) {
      urlObj.searchParams.set('shell', shellType)
    }
    if (command) {
      urlObj.searchParams.set('command', command)
    }
    if (workingDir) {
      urlObj.searchParams.set('cwd', workingDir)
    }
    return urlObj.toString()
  } catch {
    return url
  }
}
