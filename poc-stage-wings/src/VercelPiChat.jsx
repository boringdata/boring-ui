/**
 * POC: Vercel AI SDK `useChat` frontend → PI Agent backend harness
 *
 * This demonstrates wiring the Vercel AI SDK chat UI (useChat, streaming,
 * tool rendering) to the PI agent's tool system and session model.
 *
 * Architecture:
 *   ┌──────────────────────────────────────────────┐
 *   │  Vercel AI SDK Frontend (useChat)            │
 *   │  - streaming messages                        │
 *   │  - tool-call / tool-result rendering         │
 *   │  - artifact card emission                    │
 *   ├──────────────────────────────────────────────┤
 *   │  PiAgentTransport (custom ChatTransport)     │
 *   │  - wraps PI Agent core as a "backend"        │
 *   │  - converts useChat submit → Agent.run()     │
 *   │  - streams PI events → AI SDK data stream    │
 *   ├──────────────────────────────────────────────┤
 *   │  PI Agent Core (@mariozechner/pi-agent-core) │
 *   │  - model selection, tool execution           │
 *   │  - session persistence (IndexedDB)           │
 *   │  - multi-provider (Anthropic/OpenAI/Google)  │
 *   └──────────────────────────────────────────────┘
 *
 * Why this matters:
 *   - PI agent has battle-tested tools (file ops, git, search, bash)
 *   - Vercel AI SDK has better React integration (hooks, streaming, status)
 *   - The Stage+Wings design needs React-native message rendering
 *   - Shadow DOM (pi-web-ui) makes it hard to style messages for the new shell
 *   - This hybrid gives us PI's agent brain + Vercel's React rendering
 */

import { useState, useMemo, useCallback, useRef, useEffect } from 'react'
import { useChat } from '@ai-sdk/react'
import {
  Send, Square, Sparkles, User, ChevronRight,
  FileCode, BarChart3, Table2, FileText, Loader2,
  Check, X, Terminal, FolderOpen, Search, GitBranch,
} from 'lucide-react'

// ─── Tool Icon Registry ─────────────────────────────────────
const TOOL_ICONS = {
  read_file: FileCode,
  write_file: FileCode,
  edit_file: FileCode,
  list_dir: FolderOpen,
  search: Search,
  bash: Terminal,
  git_status: GitBranch,
  git_diff: GitBranch,
  default: Terminal,
}

const TOOL_COLORS = {
  read_file: '#3b82f6',
  write_file: '#a78bfa',
  edit_file: '#a78bfa',
  list_dir: '#f59e0b',
  search: '#22c55e',
  bash: '#888',
  git_status: '#f97316',
  git_diff: '#f97316',
}

// ─── PI Agent Transport for useChat ──────────────────────────
// This is a mock transport for the POC. In production, this would
// either: (a) proxy to the PI agent backend endpoint, or
// (b) run PI Agent Core in-browser and stream events to useChat.
//
// The real implementation would use @mariozechner/pi-agent-core's
// Agent class and subscribe to its events, converting them into
// the AI SDK data stream protocol format.

// ─── Anthropic → AI SDK UIMessageStream Transport ───────────
// Implements the ChatTransport interface:
//   sendMessages({ messages, abortSignal }) → ReadableStream
// Uses the Vite proxy at /api/anthropic → api.anthropic.com
// Converts Anthropic SSE into the AI SDK UI message stream protocol.

function createAnthropicTransport() {
  let textPartId = 0

  return {
    async sendMessages({ messages, abortSignal }) {
      // Convert AI SDK UIMessages → Anthropic messages format
      const anthropicMessages = messages
        .map(m => {
          const text = typeof m.content === 'string' ? m.content :
            (m.parts || []).filter(p => p.type === 'text').map(p => p.text).join('\n')
          return { role: m.role === 'user' ? 'user' : 'assistant', content: text }
        })
        .filter(m => m.content.trim().length > 0)

      if (anthropicMessages.length === 0) {
        return new ReadableStream({ start(c) { c.close() } })
      }

      const res = await fetch('/api/anthropic/v1/messages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: 'claude-sonnet-4-20250514',
          max_tokens: 4096,
          stream: true,
          system: 'You are an AI agent integrated into Boring UI, a workspace tool. Be concise, helpful, and action-oriented. When discussing code, be specific about file paths and changes.',
          messages: anthropicMessages,
        }),
        signal: abortSignal,
      })

      if (!res.ok) {
        const err = await res.text()
        throw new Error(`Anthropic API error ${res.status}: ${err}`)
      }

      // Transform Anthropic SSE → AI SDK UI message stream chunks (JS objects).
      // The stream must emit objects matching the UIMessageChunk schema:
      //   { type: 'text-start', id } → start a text part
      //   { type: 'text-delta', id, delta } → append text
      //   { type: 'text-end', id } → finalize text part
      //   { type: 'finish' } → end of message
      const currentId = `text-${++textPartId}`
      let started = false

      return res.body.pipeThrough(new TransformStream({
        buffer: '',
        transform(chunk, controller) {
          const text = new TextDecoder().decode(chunk)
          this.buffer += text
          const lines = this.buffer.split('\n')
          this.buffer = lines.pop() || ''

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            const data = line.slice(6).trim()
            if (data === '[DONE]') continue
            try {
              const event = JSON.parse(data)

              if (event.type === 'content_block_delta' && event.delta?.type === 'text_delta') {
                if (!started) {
                  controller.enqueue({ type: 'text-start', id: currentId })
                  started = true
                }
                controller.enqueue({ type: 'text-delta', id: currentId, delta: event.delta.text })
              }

              if (event.type === 'message_stop' || event.type === 'message_delta') {
                if (event.type === 'message_stop') {
                  if (started) {
                    controller.enqueue({ type: 'text-end', id: currentId })
                  }
                  controller.enqueue({ type: 'finish' })
                }
              }
            } catch { /* skip malformed */ }
          }
        },
        flush(controller) {
          if (started) {
            controller.enqueue({ type: 'text-end', id: currentId })
          }
          controller.enqueue({ type: 'finish' })
        }
      }))
    },

    async reconnectToStream() {
      return null
    }
  }
}

// ─── Tool Call Renderer ──────────────────────────────────────
function ToolCallCard({ name, args, result, status }) {
  const Icon = TOOL_ICONS[name] || TOOL_ICONS.default
  const color = TOOL_COLORS[name] || '#888'
  const isRunning = status === 'running' || status === 'pending'
  const isError = status === 'error'
  const isDone = status === 'complete' || status === 'done'

  // Check if result contains an artifact
  const artifact = result?.artifact

  return (
    <div className="tool-card" style={{ '--tool-color': color }}>
      <div className="tool-card-head">
        <div className="tool-card-icon" style={{ color }}>
          <Icon size={14} />
        </div>
        <span className="tool-card-name">{name}</span>
        {args?.path && <span className="tool-card-path">{args.path}</span>}
        <div style={{ flex: 1 }} />
        {isRunning && <Loader2 size={12} className="tool-card-spin" />}
        {isDone && <Check size={12} style={{ color: '#22c55e' }} />}
        {isError && <X size={12} style={{ color: '#ef4444' }} />}
      </div>
      {isDone && result && !artifact && (
        <div className="tool-card-result">
          {typeof result === 'string' ? result :
           typeof result?.content === 'string' ? (
            <pre className="tool-card-code">{result.content.slice(0, 200)}{result.content.length > 200 ? '...' : ''}</pre>
           ) : (
            <span className="tool-card-summary">Completed</span>
           )}
        </div>
      )}
      {artifact && (
        <div className="tool-card-artifact">
          <BarChart3 size={14} style={{ color: '#3b82f6' }} />
          <span>{artifact.title}</span>
          <ChevronRight size={12} style={{ opacity: 0.4 }} />
        </div>
      )}
    </div>
  )
}

// ─── Message Renderer ────────────────────────────────────────
function ChatMessage({ message, onOpenArtifact }) {
  const isUser = message.role === 'user'
  const parts = message.parts || []

  // Extract tool calls and results
  const toolCalls = []
  const toolResults = new Map()

  for (const part of parts) {
    if (part.type === 'tool-call') {
      toolCalls.push(part)
    }
    if (part.type === 'tool-result') {
      toolResults.set(part.toolCallId, part)
    }
  }

  return (
    <div className="vc-msg">
      <div className="vc-msg-role">
        <div className={`vc-msg-avatar ${isUser ? 'user' : 'agent'}`}>
          {isUser ? <User size={11} /> : <Sparkles size={11} />}
        </div>
        <span>{isUser ? 'You' : 'Agent'}</span>
      </div>

      {/* Text parts */}
      {parts.map((part, i) => {
        if (part.type === 'text' && part.text) {
          return <div key={i} className="vc-msg-text">{part.text}</div>
        }
        if (part.type === 'reasoning') {
          return <div key={i} className="vc-msg-reasoning">{part.text}</div>
        }
        return null
      })}

      {/* Fallback for simple string content */}
      {parts.length === 0 && message.content && (
        <div className="vc-msg-text">{message.content}</div>
      )}

      {/* Tool calls */}
      {toolCalls.map(tc => {
        const result = toolResults.get(tc.toolCallId)
        const artifact = result?.result?.artifact
        return (
          <div key={tc.toolCallId}>
            <ToolCallCard
              name={tc.toolName}
              args={tc.args}
              result={result?.result}
              status={result ? 'complete' : 'running'}
            />
            {artifact && (
              <div className="vc-artifact-card" onClick={() => onOpenArtifact?.(artifact)}>
                <div className="vc-artifact-icon">
                  <BarChart3 size={16} style={{ color: '#3b82f6' }} />
                </div>
                <div className="vc-artifact-info">
                  <span className="vc-artifact-title">{artifact.title}</span>
                  <span className="vc-artifact-type">{artifact.kind}</span>
                </div>
                <div style={{ flex: 1 }} />
                <ChevronRight size={14} style={{ color: 'var(--text-tertiary)', opacity: 0.4 }} />
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ─── Main Chat Component ─────────────────────────────────────
export default function VercelPiChat({ onOpenArtifact }) {
  const [input, setInput] = useState('')
  const scrollRef = useRef(null)
  const inputRef = useRef(null)

  // Transport: Anthropic API via Vite proxy → AI SDK stream protocol.
  // In production, replace with PI Agent Core transport.
  const transport = useMemo(() => createAnthropicTransport(), [])

  const { messages, sendMessage, status, error, stop } = useChat({
    transport,
  })

  const isBusy = status === 'submitted' || status === 'streaming'

  // Auto-scroll
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  const handleSubmit = useCallback(async (e) => {
    e?.preventDefault()
    const text = input.trim()
    if (!text || isBusy) return
    setInput('')
    await sendMessage({ text })
  }, [input, isBusy, sendMessage])

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }, [handleSubmit])

  return (
    <div className="vc-chat">
      {/* Message list */}
      <div className="vc-scroll" ref={scrollRef}>
        <div className="vc-msgs">
          {messages.length === 0 && (
            <div className="vc-empty">
              <Sparkles size={28} style={{ opacity: 0.12 }} />
              <span className="vc-empty-title">What can I help with?</span>
              <span className="vc-empty-sub">
                PI Agent tools available: file ops, search, bash, git
              </span>
              <div className="vc-empty-hints">
                <button onClick={() => { setInput('Read src/auth.js and explain the login flow'); inputRef.current?.focus() }}>
                  Read a file
                </button>
                <button onClick={() => { setInput('Show me a revenue chart by region'); inputRef.current?.focus() }}>
                  Generate a chart
                </button>
                <button onClick={() => { setInput('Fix the token refresh bug in auth.js'); inputRef.current?.focus() }}>
                  Fix a bug
                </button>
              </div>
            </div>
          )}
          {messages.map(msg => (
            <ChatMessage key={msg.id} message={msg} onOpenArtifact={onOpenArtifact} />
          ))}
          {isBusy && messages.length > 0 && messages[messages.length - 1]?.role === 'user' && (
            <div className="vc-msg">
              <div className="vc-msg-role">
                <div className="vc-msg-avatar agent"><Sparkles size={11} /></div>
                <span>Agent</span>
              </div>
              <div className="vc-thinking">
                <Loader2 size={14} className="tool-card-spin" />
                <span>Thinking...</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Composer */}
      <div className="vc-input-wrap">
        <div className={`vc-input${isBusy ? ' busy' : ''}`}>
          <input
            ref={inputRef}
            placeholder="Ask a question..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isBusy}
          />
          <div className="vc-kbd">
            <kbd>⌘</kbd><kbd>K</kbd>
          </div>
          {isBusy ? (
            <button className="vc-stop" onClick={stop} title="Stop">
              <Square size={14} />
            </button>
          ) : (
            <button className="vc-send" onClick={handleSubmit} disabled={!input.trim()} title="Send">
              <Send size={14} />
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="vc-error">Error: {error.message}</div>
      )}
    </div>
  )
}
