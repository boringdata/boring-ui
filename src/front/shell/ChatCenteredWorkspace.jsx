import React, { useState, useCallback, useMemo, useEffect } from 'react'
import { useChat } from '@ai-sdk/react'
import ChatStage from './ChatStage'
import NavRail from './NavRail'
import BrowseDrawer from './BrowseDrawer'
import SurfaceShell from './SurfaceShell'
import { useSessionState } from './useSessionState'
import { useArtifactController } from './useArtifactController'
import { useToolBridge } from './useToolBridge'
import { ChatMetricsProvider } from './useChatMetrics'
import { useReducedMotion } from './useReducedMotion'
import './shell.css'

/**
 * ChatCenteredWorkspace — the new shell entry point.
 * Renders: NavRail + BrowseDrawer + ChatStage + SurfaceShell.
 * Activated via features.chatCenteredShell or ?shell=chat-centered.
 */
export default function ChatCenteredWorkspace() {
  const reducedMotion = useReducedMotion()
  const {
    activeSessionId,
    sessions,
    switchSession,
    createNewSession,
  } = useSessionState()

  const {
    surfaceOpen,
    activeArtifactId,
    artifacts,
    orderedIds,
    open: openArtifact,
    focus: focusArtifact,
    close: closeArtifact,
  } = useArtifactController()

  // Wire tool bridge so PI agent tools can open files/panels in the Surface
  useToolBridge({ openArtifact, activeSessionId })

  // Shell layout state
  const [activeDestination, setActiveDestination] = useState(null)
  const [surfaceCollapsed, setSurfaceCollapsed] = useState(true)
  const [surfaceWidth, setSurfaceWidth] = useState(620)

  // Anthropic streaming transport (dev mode — no backend needed)
  const transport = useMemo(() => ({
    async sendMessages({ messages, abortSignal }) {
      const msgs = messages
        .map(m => ({ role: m.role === 'user' ? 'user' : 'assistant',
          content: typeof m.content === 'string' ? m.content :
            (m.parts || []).filter(p => p.type === 'text').map(p => p.text).join('\n') }))
        .filter(m => m.content.trim())
      if (!msgs.length) return new ReadableStream({ start(c) { c.close() } })
      const res = await fetch('/api/anthropic/v1/messages', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: 'claude-sonnet-4-20250514', max_tokens: 4096, stream: true,
          system: 'You are a helpful AI coding assistant integrated into Boring UI. Be concise, helpful, and action-oriented.',
          messages: msgs }),
        signal: abortSignal,
      })
      if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`)
      let id = `text-${Date.now()}`, started = false, finished = false
      return res.body.pipeThrough(new TransformStream({
        buffer: '',
        transform(chunk, c) {
          this.buffer += new TextDecoder().decode(chunk)
          const lines = this.buffer.split('\n'); this.buffer = lines.pop() || ''
          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            try {
              const e = JSON.parse(line.slice(6).trim())
              if (e.type === 'content_block_delta' && e.delta?.type === 'text_delta') {
                if (!started) { c.enqueue({ type: 'text-start', id }); started = true }
                c.enqueue({ type: 'text-delta', id, delta: e.delta.text })
              }
              if (e.type === 'message_stop') {
                if (started) c.enqueue({ type: 'text-end', id })
                c.enqueue({ type: 'finish' }); finished = true
              }
            } catch {}
          }
        },
        flush(c) { if (started && !finished) { c.enqueue({ type: 'text-end', id }); c.enqueue({ type: 'finish' }) } },
      }))
    },
    async reconnectToStream() { return null },
  }), [])

  const { messages: chatMessages, sendMessage, status: chatStatus, stop, error: chatError } = useChat({ transport })
  const [chatInput, setChatInput] = useState('')

  const handleSendMessage = useCallback(async () => {
    const text = chatInput.trim()
    if (!text) return
    setChatInput('')
    await sendMessage({ text })
  }, [chatInput, sendMessage])

  // Open artifact in Surface (from chat cards or explorer file tree)
  const handleOpenArtifact = useCallback((artifact) => {
    openArtifact(artifact)
    setSurfaceCollapsed(false)
  }, [openArtifact])

  // Open file from Surface explorer file tree
  const handleOpenFile = useCallback((filePath) => {
    handleOpenArtifact({
      kind: 'code',
      canonicalKey: filePath,
      title: filePath.split('/').pop() || filePath,
      source: 'user',
      rendererKey: 'code',
      params: { path: filePath },
      status: 'ready',
    })
  }, [handleOpenArtifact])

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e) => {
      const mod = e.metaKey || e.ctrlKey
      if (mod && e.key === '2') { e.preventDefault(); setSurfaceCollapsed(c => !c) }
      if (mod && e.key === '1') { e.preventDefault(); setActiveDestination(d => d === 'history' ? null : 'history') }
      if (mod && e.key === 'b') { e.preventDefault(); setActiveDestination(d => d === 'history' ? null : 'history') }
      if (e.key === 'Escape') {
        const composer = document.querySelector('.vc-composer-input')
        if (composer) composer.focus()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  const handleDestinationChange = useCallback((dest) => setActiveDestination(dest), [])
  const handleNewChat = useCallback(() => { createNewSession(); setActiveDestination(null) }, [createNewSession])
  const handleSwitchSession = useCallback((id) => switchSession(id), [switchSession])
  const handleSurfaceClose = useCallback(() => setSurfaceCollapsed(true), [])
  const handleSurfaceCollapse = useCallback(() => setSurfaceCollapsed(c => !c), [])
  const handleSurfaceResize = useCallback((w) => setSurfaceWidth(w), [])

  const drawerOpen = activeDestination === 'history'
  const artifactsList = orderedIds.map((id) => artifacts.get(id)).filter(Boolean)

  return (
    <ChatMetricsProvider>
      <div
        className={['chat-centered-workspace', reducedMotion && 'reduced-motion'].filter(Boolean).join(' ')}
        data-testid="chat-centered-workspace"
      >
        <NavRail
          activeDestination={activeDestination}
          onDestinationChange={handleDestinationChange}
          onNewChat={handleNewChat}
          onToggleSurface={() => setSurfaceCollapsed(c => !c)}
          surfaceOpen={!surfaceCollapsed}
        />

        <BrowseDrawer
          open={drawerOpen}
          mode="sessions"
          sessions={sessions}
          activeSessionId={activeSessionId}
          onSwitchSession={handleSwitchSession}
          onClose={() => setActiveDestination(null)}
        />

        <main className="ccw-stage-area" role="main">
          <ChatStage
            messages={chatMessages}
            input={chatInput}
            onInputChange={setChatInput}
            onSubmit={handleSendMessage}
            onStop={stop}
            status={chatStatus}
            disabled={false}
            onOpenArtifact={handleOpenArtifact}
          />
          {chatError && (
            <div style={{ color: '#ef4444', fontSize: 12, textAlign: 'center', padding: 8 }}>
              Error: {chatError.message}
            </div>
          )}
        </main>

        <SurfaceShell
          open={!surfaceCollapsed}
          collapsed={surfaceCollapsed}
          width={surfaceWidth}
          artifacts={artifactsList}
          activeArtifactId={activeArtifactId}
          onClose={handleSurfaceClose}
          onCollapse={handleSurfaceCollapse}
          onResize={handleSurfaceResize}
          onSelectArtifact={focusArtifact}
          onCloseArtifact={closeArtifact}
          onOpenFile={handleOpenFile}
        />
      </div>
    </ChatMetricsProvider>
  )
}
