import { useEffect, useMemo, useState } from 'react'
import { DefaultChatTransport } from 'ai'
import { useChat } from '@ai-sdk/react'
import { Loader2, SendHorizontal, Square } from 'lucide-react'
import { buildApiUrl } from '../../utils/apiBase'
import { getWorkspaceIdFromPathname } from '../../utils/controlPlane'
import { renderToolPart } from './toolRenderers'
import { Button } from '../ui/button'
import { Textarea } from '../ui/textarea'

const LOCATION_CHANGE_EVENT = 'boring-ui:location-change'
let historyChangePatched = false

function ensureHistoryChangeEvents() {
  if (typeof window === 'undefined' || historyChangePatched) return
  historyChangePatched = true

  for (const method of ['pushState', 'replaceState']) {
    const original = window.history[method]
    if (typeof original !== 'function') continue

    window.history[method] = function patchedHistoryMethod(...args) {
      const result = original.apply(this, args)
      window.dispatchEvent(new Event(LOCATION_CHANGE_EVENT))
      return result
    }
  }
}

function toolOutputToText(value) {
  if (typeof value === 'string') return value
  if (value && typeof value === 'object' && typeof value.text === 'string') {
    return value.text
  }
  if (value && typeof value === 'object' && Array.isArray(value.content)) {
    const text = value.content
      .filter((part) => part?.type === 'text' && typeof part.text === 'string')
      .map((part) => part.text)
      .join('\n')
      .trim()
    if (text) return text
  }
  if (value && typeof value === 'object' && typeof value.content === 'string') {
    return value.content
  }
  if (value && typeof value === 'object' && typeof value.diff === 'string') {
    return value.diff
  }
  if (value && typeof value === 'object' && Array.isArray(value.results)) {
    const lines = value.results
      .map((entry) => entry?.path)
      .filter((path) => typeof path === 'string' && path.length > 0)
    if (lines.length > 0) return lines.join('\n')
  }
  if (value && typeof value === 'object' && Array.isArray(value.entries)) {
    const lines = value.entries
      .map((entry) => {
        if (!entry || typeof entry.path !== 'string' || !entry.path) return null
        return entry.is_dir ? `${entry.path}/` : entry.path
      })
      .filter(Boolean)
    if (lines.length > 0) return lines.join('\n')
  }
  if (value && typeof value === 'object' && Array.isArray(value.files)) {
    const lines = value.files
      .map((entry) => {
        if (!entry || typeof entry.path !== 'string' || !entry.path) return null
        const status = typeof entry.status === 'string' ? entry.status : '?'
        return `${status} ${entry.path}`
      })
      .filter(Boolean)
    if (lines.length > 0) return lines.join('\n')
    if (value.is_repo === true) return 'Clean working tree'
  }
  if (value && typeof value === 'object' && ('stdout' in value || 'stderr' in value)) {
    const stdout = typeof value.stdout === 'string' ? value.stdout.trim() : ''
    const stderr = typeof value.stderr === 'string' ? value.stderr.trim() : ''
    const combined = [stdout, stderr].filter(Boolean).join('\n')
    if (combined) return combined
  }
  if (value == null) return ''
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function normalizeToolPart(part) {
  if (part?.type === 'tool-call') {
    return {
      name: part.toolName,
      input: part.input || {},
      output: '',
      status: 'running',
    }
  }

  if (part?.type === 'tool-result') {
    return {
      name: part.toolName,
      input: part.input || {},
      output: toolOutputToText(part.output),
      status: part.preliminary ? 'running' : 'complete',
    }
  }

  if (part?.type === 'tool-error') {
    return {
      name: part.toolName,
      input: part.input || {},
      output: toolOutputToText(part.error),
      error: toolOutputToText(part.error) || 'Tool failed',
      status: 'error',
    }
  }

  return null
}

const HIDDEN_PROTOCOL_PARTS = new Set([
  'tool-input-start',
  'tool-input-delta',
  'tool-input-end',
  'stream-start',
  'response-metadata',
  'finish',
  'raw',
])

function toolPartPriority(part) {
  if (part?.type === 'tool-error') return 3
  if (part?.type === 'tool-result') return part.preliminary ? 1 : 2
  if (part?.type === 'tool-call') return 0
  return -1
}

function selectVisibleToolParts(parts) {
  const selected = new Map()

  for (const part of parts) {
    const toolCallId = part?.toolCallId
    if (!toolCallId) continue

    const priority = toolPartPriority(part)
    if (priority < 0) continue

    const current = selected.get(toolCallId)
    if (!current || priority >= current.priority) {
      selected.set(toolCallId, { part, priority })
    }
  }

  return new Map(
    Array.from(selected.entries()).map(([toolCallId, value]) => [toolCallId, value.part]),
  )
}

function renderMessagePart(part, index, visibleToolParts) {
  if (part?.type === 'text') {
    return <div key={index}>{part.text}</div>
  }

  if (part?.type === 'reasoning') {
    return (
      <div key={index} className="text-xs text-muted-foreground">
        {part.text}
      </div>
    )
  }

  if (HIDDEN_PROTOCOL_PARTS.has(part?.type || '')) {
    return null
  }

  if (part?.type === 'tool-call' || part?.type === 'tool-result' || part?.type === 'tool-error') {
    if (part.toolCallId && visibleToolParts.get(part.toolCallId) !== part) {
      return null
    }
    const normalized = normalizeToolPart(part)
    if (!normalized) return null
    return (
      <div key={part.toolCallId || index}>
        {renderToolPart(normalized)}
      </div>
    )
  }

  return (
    <div key={index} className="text-xs text-muted-foreground">
      [{part?.type || 'unknown'} part]
    </div>
  )
}

function AiChatWorkspaceScope({ workspaceId }) {
  const [input, setInput] = useState('')
  const transport = useMemo(() => new DefaultChatTransport({
    api: buildApiUrl('/api/v1/agent/chat'),
    credentials: 'include',
    body: workspaceId ? { workspace_id: workspaceId } : undefined,
  }), [workspaceId])
  const { messages, sendMessage, status, error, stop } = useChat({ transport })
  const isBusy = status === 'submitted' || status === 'streaming'

  const handleSubmit = async (event) => {
    event.preventDefault()
    const text = input.trim()
    if (!text || isBusy) return
    setInput('')
    await sendMessage({ text })
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3" data-testid="ai-chat">
      <div className="min-h-0 flex-1 overflow-y-auto rounded-md border border-border bg-background/70 p-3">
        {messages.length === 0 ? (
          <div className="text-sm text-muted-foreground" data-testid="ai-chat-empty">
            AI SDK chat is ready. Messages stream through the server runtime.
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {messages.map((message) => (
              <div
                key={message.id}
                className="rounded-md border border-border bg-background p-3"
                data-testid={`ai-chat-message-${message.role}`}
              >
                <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {message.role}
                </div>
                <div className="space-y-2 text-sm">
                  {Array.isArray(message.parts) ? (() => {
                    const visibleToolParts = selectVisibleToolParts(message.parts)
                    return message.parts.map((part, index) => renderMessagePart(part, index, visibleToolParts))
                  })() : null}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {error ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error.message}
        </div>
      ) : null}

      <form className="flex flex-col gap-2" onSubmit={handleSubmit}>
        <Textarea
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Send a message to the server-side AI SDK runtime..."
          disabled={isBusy}
          rows={4}
        />
        <div className="flex items-center justify-between gap-2">
          <div className="text-xs text-muted-foreground">
            {isBusy ? 'Streaming response...' : 'Server-side Anthropic runtime'}
          </div>
          <div className="flex items-center gap-2">
            {isBusy ? (
              <Button type="button" variant="outline" size="sm" onClick={() => stop()}>
                <Square className="h-4 w-4" />
                Stop
              </Button>
            ) : null}
            <Button type="submit" size="sm" disabled={!input.trim() || isBusy}>
              {isBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <SendHorizontal className="h-4 w-4" />}
              Send
            </Button>
          </div>
        </div>
      </form>
    </div>
  )
}

export default function AiChat() {
  const [workspaceId, setWorkspaceId] = useState(
    () => (typeof window === 'undefined' ? '' : getWorkspaceIdFromPathname(window.location.pathname)),
  )

  useEffect(() => {
    if (typeof window === 'undefined') return undefined
    ensureHistoryChangeEvents()
    const syncWorkspaceId = () => {
      setWorkspaceId(getWorkspaceIdFromPathname(window.location.pathname))
    }
    syncWorkspaceId()
    window.addEventListener('popstate', syncWorkspaceId)
    window.addEventListener(LOCATION_CHANGE_EVENT, syncWorkspaceId)
    return () => {
      window.removeEventListener('popstate', syncWorkspaceId)
      window.removeEventListener(LOCATION_CHANGE_EVENT, syncWorkspaceId)
    }
  }, [])

  return <AiChatWorkspaceScope key={workspaceId || 'root'} workspaceId={workspaceId} />
}
