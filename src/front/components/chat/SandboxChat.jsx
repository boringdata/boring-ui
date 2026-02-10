/**
 * SandboxChat - Native chat component for sandbox-agent.
 *
 * Communicates directly with the sandbox-agent REST API via the
 * backend proxy at /api/sandbox/v1/*, replacing the iframe approach.
 *
 * Supports:
 * - Sandbox lifecycle management (auto-start, status monitoring)
 * - Session creation with agent selection
 * - Message sending with turn-based SSE streaming
 * - Native message display with tool call rendering
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import { Send, Square, Loader2, AlertCircle, RefreshCw } from 'lucide-react'
import { buildApiUrl } from '../../utils/apiBase'
import './SandboxChat.css'

const SANDBOX_SESSION_KEY = 'kurt-web-sandbox-session'
const SANDBOX_AGENT_KEY = 'kurt-web-sandbox-agent'

const generateSessionId = () => {
  const chars = 'abcdefghijklmnopqrstuvwxyz0123456789'
  let id = 'session-'
  for (let i = 0; i < 8; i++) {
    id += chars[Math.floor(Math.random() * chars.length)]
  }
  return id
}

const loadSavedSession = () => {
  try {
    return localStorage.getItem(SANDBOX_SESSION_KEY) || null
  } catch {
    return null
  }
}

const loadSavedAgent = () => {
  try {
    return localStorage.getItem(SANDBOX_AGENT_KEY) || 'claude'
  } catch {
    return 'claude'
  }
}

// Parse SSE stream text into events
const parseSSEEvents = (text) => {
  const events = []
  const lines = text.split('\n')
  let currentData = ''

  for (const line of lines) {
    if (line.startsWith('data: ')) {
      currentData += line.slice(6)
    } else if (line === '' && currentData) {
      try {
        events.push(JSON.parse(currentData))
      } catch {
        // Skip malformed events
      }
      currentData = ''
    }
  }
  // Handle trailing data without final newline
  if (currentData) {
    try {
      events.push(JSON.parse(currentData))
    } catch {
      // Skip
    }
  }
  return events
}

// Extract display text from a UniversalItem's content array
const getItemText = (item) => {
  if (!item?.content || !Array.isArray(item.content)) return ''
  return item.content
    .filter((part) => part.type === 'text')
    .map((part) => part.text || '')
    .join('')
}

// Get tool call info from an item
const getToolInfo = (item) => {
  if (!item?.content || !Array.isArray(item.content)) return null
  const toolPart = item.content.find(
    (part) => part.type === 'tool_call' || part.type === 'tool_result',
  )
  return toolPart || null
}

const agentLabels = {
  claude: 'Claude Code',
  codex: 'Codex',
  opencode: 'OpenCode',
  amp: 'Amp',
  mock: 'Mock',
}

export default function SandboxChat() {
  // Sandbox lifecycle
  const [sandboxStatus, setSandboxStatus] = useState(null) // null | 'starting' | 'running' | 'error' | 'not_running'
  const [sandboxError, setSandboxError] = useState(null)

  // Agent selection
  const [agents, setAgents] = useState([])
  const [selectedAgent, setSelectedAgent] = useState(loadSavedAgent)

  // Session state
  const [sessionId, setSessionId] = useState(loadSavedSession)
  const [sessionError, setSessionError] = useState(null)

  // Messages (timeline entries)
  const [entries, setEntries] = useState([])
  const [deltaBuffer, setDeltaBuffer] = useState({}) // item_id -> accumulated delta text
  const [streaming, setStreaming] = useState(false)
  const [eventError, setEventError] = useState(null)

  // Input
  const [message, setMessage] = useState('')
  const messagesEndRef = useRef(null)
  const textareaRef = useRef(null)
  const abortRef = useRef(null)
  const sseAbortRef = useRef(null)
  const offsetRef = useRef(0)

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [entries, deltaBuffer])

  // Save session to localStorage
  useEffect(() => {
    try {
      if (sessionId) {
        localStorage.setItem(SANDBOX_SESSION_KEY, sessionId)
      } else {
        localStorage.removeItem(SANDBOX_SESSION_KEY)
      }
    } catch {
      // Ignore
    }
  }, [sessionId])

  useEffect(() => {
    try {
      localStorage.setItem(SANDBOX_AGENT_KEY, selectedAgent)
    } catch {
      // Ignore
    }
  }, [selectedAgent])

  // --- Sandbox lifecycle ---

  const fetchSandboxStatus = useCallback(async () => {
    try {
      const resp = await fetch(buildApiUrl('/api/sandbox/status'))
      if (!resp.ok) throw new Error('Failed to fetch status')
      const data = await resp.json()
      setSandboxStatus(data.status || 'not_running')
      setSandboxError(null)
      return data.status
    } catch (err) {
      setSandboxError(err.message)
      return null
    }
  }, [])

  const startSandbox = useCallback(async () => {
    setSandboxStatus('starting')
    setSandboxError(null)
    try {
      const resp = await fetch(buildApiUrl('/api/sandbox/start'), {
        method: 'POST',
      })
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}))
        throw new Error(data.detail || 'Failed to start sandbox')
      }
      setSandboxStatus('running')
    } catch (err) {
      setSandboxStatus('error')
      setSandboxError(err.message)
    }
  }, [])

  // Initial status check + auto-start
  useEffect(() => {
    let cancelled = false
    const init = async () => {
      const status = await fetchSandboxStatus()
      if (cancelled) return
      if (status === 'not_running') {
        await startSandbox()
      }
      if (!cancelled && status === 'running') {
        // Fetch agents
        fetchAgents()
      }
    }
    init()
    return () => {
      cancelled = true
    }
  }, [])

  // Poll sandbox status until running
  useEffect(() => {
    if (sandboxStatus === 'running') {
      fetchAgents()
      return
    }
    if (sandboxStatus === 'starting') {
      const interval = setInterval(async () => {
        const status = await fetchSandboxStatus()
        if (status === 'running') {
          clearInterval(interval)
        }
      }, 2000)
      return () => clearInterval(interval)
    }
  }, [sandboxStatus, fetchSandboxStatus])

  // --- Agent management ---

  const fetchAgents = useCallback(async () => {
    try {
      const resp = await fetch(buildApiUrl('/api/sandbox/v1/agents'))
      if (!resp.ok) return
      const data = await resp.json()
      const agentList = data.agents || []
      setAgents(agentList)
    } catch {
      // Agents not available yet
    }
  }, [])

  // --- Session management ---

  const createSession = useCallback(
    async (agentOverride) => {
      const agent = agentOverride || selectedAgent
      const id = generateSessionId()
      setSessionError(null)
      setEntries([])
      setDeltaBuffer({})
      offsetRef.current = 0

      try {
        const resp = await fetch(
          buildApiUrl(`/api/sandbox/v1/sessions/${id}`),
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ agent }),
          },
        )
        if (!resp.ok) {
          const data = await resp.json().catch(() => ({}))
          throw new Error(data.detail || data.title || 'Failed to create session')
        }
        setSessionId(id)
        setSelectedAgent(agent)
      } catch (err) {
        setSessionError(err.message)
      }
    },
    [selectedAgent],
  )

  const endSession = useCallback(async () => {
    if (!sessionId) return
    // Stop any streaming
    if (abortRef.current) {
      abortRef.current.abort()
      abortRef.current = null
    }
    if (sseAbortRef.current) {
      sseAbortRef.current.abort()
      sseAbortRef.current = null
    }
    try {
      await fetch(
        buildApiUrl(`/api/sandbox/v1/sessions/${sessionId}/terminate`),
        { method: 'POST' },
      )
    } catch {
      // Ignore
    }
    setSessionId(null)
    setEntries([])
    setDeltaBuffer({})
    setStreaming(false)
    offsetRef.current = 0
  }, [sessionId])

  // --- Event processing ---

  const processEvent = useCallback((event) => {
    const type = event.type || event.event
    const data = event.data || event

    if (type === 'item.started' || type === 'item.created') {
      const item = data.item || data
      if (item?.item_id) {
        setEntries((prev) => {
          // Don't add duplicate items
          if (prev.some((e) => e.id === item.item_id)) return prev
          return [
            ...prev,
            {
              id: item.item_id,
              kind: 'item',
              time: new Date().toISOString(),
              item,
            },
          ]
        })
      }
    } else if (type === 'item.delta') {
      const itemId = data.item_id
      const delta = data.delta || ''
      if (itemId && delta) {
        setDeltaBuffer((prev) => ({
          ...prev,
          [itemId]: (prev[itemId] || '') + delta,
        }))
      }
    } else if (type === 'item.completed') {
      const item = data.item || data
      if (item?.item_id) {
        // Update existing entry with final state
        setEntries((prev) =>
          prev.map((e) =>
            e.id === item.item_id ? { ...e, item } : e,
          ),
        )
        // Clear delta buffer for this item
        setDeltaBuffer((prev) => {
          const next = { ...prev }
          delete next[item.item_id]
          return next
        })
      }
    } else if (type === 'session.started') {
      // Session started confirmation
    } else if (type === 'session.completed' || type === 'session.ended') {
      setStreaming(false)
    }
  }, [])

  // --- Send message with turn-based streaming ---

  const sendMessage = useCallback(async () => {
    const prompt = message.trim()
    if (!prompt || !sessionId || streaming) return

    setMessage('')
    setSessionError(null)
    setEventError(null)

    // Add user message to entries
    const userItemId = `user-${Date.now()}`
    setEntries((prev) => [
      ...prev,
      {
        id: userItemId,
        kind: 'item',
        time: new Date().toISOString(),
        item: {
          item_id: userItemId,
          kind: 'message',
          role: 'user',
          content: [{ type: 'text', text: prompt }],
          status: 'completed',
        },
      },
    ])

    setStreaming(true)
    const controller = new AbortController()
    abortRef.current = controller

    try {
      const resp = await fetch(
        buildApiUrl(`/api/sandbox/v1/sessions/${sessionId}/messages/stream`),
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: prompt }),
          signal: controller.signal,
        },
      )

      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}))
        throw new Error(data.detail || data.title || 'Failed to send message')
      }

      // Read SSE stream
      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // Process complete SSE events
        const parts = buffer.split('\n\n')
        buffer = parts.pop() || '' // Keep incomplete part

        for (const part of parts) {
          if (!part.trim()) continue
          const events = parseSSEEvents(part + '\n\n')
          for (const event of events) {
            processEvent(event)
          }
        }
      }

      // Process remaining buffer
      if (buffer.trim()) {
        const events = parseSSEEvents(buffer + '\n\n')
        for (const event of events) {
          processEvent(event)
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        setEventError(err.message)
      }
    } finally {
      setStreaming(false)
      abortRef.current = null
    }
  }, [message, sessionId, streaming, processEvent])

  const stopStreaming = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort()
      abortRef.current = null
    }
    if (sseAbortRef.current) {
      sseAbortRef.current.abort()
      sseAbortRef.current = null
    }
    setStreaming(false)
  }, [])

  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        sendMessage()
      }
    },
    [sendMessage],
  )

  // --- Render states ---

  if (sandboxStatus === null || sandboxStatus === 'starting') {
    return (
      <div className="sandbox-chat sandbox-chat--loading">
        <Loader2 size={20} className="sandbox-chat-spinner" />
        <span>{sandboxStatus === 'starting' ? 'Starting sandbox-agent...' : 'Checking sandbox...'}</span>
      </div>
    )
  }

  if (sandboxStatus === 'error' || (sandboxStatus !== 'running' && sandboxStatus !== 'starting')) {
    return (
      <div className="sandbox-chat sandbox-chat--error">
        <AlertCircle size={20} />
        <span>{sandboxError || 'Sandbox not available'}</span>
        <button className="sandbox-chat-btn" onClick={startSandbox}>
          <RefreshCw size={14} />
          Retry
        </button>
      </div>
    )
  }

  // --- Running state ---

  return (
    <div className="sandbox-chat">
      {/* Session header */}
      <div className="sandbox-chat-header">
        {sessionId ? (
          <>
            <span className="sandbox-chat-session-info">
              <span className="sandbox-chat-dot sandbox-chat-dot--active" />
              {agentLabels[selectedAgent] || selectedAgent}
            </span>
            <span className="sandbox-chat-session-id">{sessionId.slice(0, 16)}</span>
            <div className="sandbox-chat-header-spacer" />
            <button
              className="sandbox-chat-btn sandbox-chat-btn--small sandbox-chat-btn--danger"
              onClick={endSession}
              title="End session"
            >
              <Square size={12} />
              End
            </button>
          </>
        ) : (
          <>
            <span className="sandbox-chat-label">No session</span>
            <div className="sandbox-chat-header-spacer" />
            <select
              className="sandbox-chat-select"
              value={selectedAgent}
              onChange={(e) => setSelectedAgent(e.target.value)}
            >
              {agents.length > 0 ? (
                agents.map((a) => (
                  <option key={a.id} value={a.id}>
                    {agentLabels[a.id] || a.id}
                    {a.installed ? '' : ' (not installed)'}
                  </option>
                ))
              ) : (
                <>
                  <option value="claude">Claude Code</option>
                  <option value="codex">Codex</option>
                  <option value="opencode">OpenCode</option>
                  <option value="mock">Mock</option>
                </>
              )}
            </select>
            <button
              className="sandbox-chat-btn sandbox-chat-btn--small"
              onClick={() => createSession()}
            >
              New Session
            </button>
          </>
        )}
      </div>

      {/* Messages area */}
      <div className="sandbox-chat-messages">
        {!sessionId ? (
          <div className="sandbox-chat-empty">
            <p>Create a session to start chatting with an agent.</p>
          </div>
        ) : entries.length === 0 && !sessionError ? (
          <div className="sandbox-chat-empty">
            <p>Send a message to start a conversation.</p>
          </div>
        ) : (
          entries.map((entry) => {
            const item = entry.item
            if (!item) return null

            const isUser = item.role === 'user'
            const isToolCall = item.kind === 'tool_call'
            const isToolResult = item.kind === 'tool_result'
            const isFailed = item.status === 'failed'
            const isInProgress = item.status === 'in_progress'

            // Get text from content or delta buffer
            let text = getItemText(item)
            const delta = deltaBuffer[item.item_id]
            if (!text && delta) {
              text = delta
            }

            const toolInfo = getToolInfo(item)

            let className = 'sandbox-chat-msg'
            if (isUser) className += ' sandbox-chat-msg--user'
            else if (isToolCall || isToolResult) className += ' sandbox-chat-msg--tool'
            else className += ' sandbox-chat-msg--assistant'
            if (isFailed) className += ' sandbox-chat-msg--error'

            return (
              <div key={entry.id} className={className}>
                {isToolCall && (
                  <div className="sandbox-chat-tool-header">
                    {toolInfo?.name || 'Tool Call'}
                    {isInProgress && <Loader2 size={12} className="sandbox-chat-spinner" />}
                  </div>
                )}
                {isToolResult && (
                  <div className="sandbox-chat-tool-header">
                    Result
                  </div>
                )}
                {text && (
                  <div className="sandbox-chat-msg-text">
                    {text}
                    {isInProgress && !isToolCall && (
                      <span className="sandbox-chat-cursor" />
                    )}
                  </div>
                )}
                {!text && isInProgress && !isToolCall && (
                  <div className="sandbox-chat-thinking">
                    <span className="sandbox-chat-thinking-dot" />
                    <span className="sandbox-chat-thinking-dot" />
                    <span className="sandbox-chat-thinking-dot" />
                  </div>
                )}
                {isFailed && (
                  <div className="sandbox-chat-msg-error">
                    {item.status_detail || 'Failed'}
                  </div>
                )}
              </div>
            )
          })
        )}
        {sessionError && (
          <div className="sandbox-chat-msg sandbox-chat-msg--error">
            <div className="sandbox-chat-msg-text">{sessionError}</div>
          </div>
        )}
        {eventError && (
          <div className="sandbox-chat-msg sandbox-chat-msg--error">
            <div className="sandbox-chat-msg-text">{eventError}</div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="sandbox-chat-input">
        <textarea
          ref={textareaRef}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={sessionId ? 'Send a message...' : 'Create a session first'}
          rows={1}
          disabled={!sessionId || streaming}
        />
        {streaming ? (
          <button
            className="sandbox-chat-send"
            onClick={stopStreaming}
            title="Stop"
          >
            <Square size={16} />
          </button>
        ) : (
          <button
            className="sandbox-chat-send"
            onClick={sendMessage}
            disabled={!sessionId || !message.trim()}
            title="Send"
          >
            <Send size={16} />
          </button>
        )}
      </div>
    </div>
  )
}
