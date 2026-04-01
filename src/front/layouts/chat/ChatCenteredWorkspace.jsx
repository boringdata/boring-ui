import React, { useState, useCallback, useMemo, useEffect } from 'react'
import { useChat } from '@ai-sdk/react'

import ChatStage from './ChatStage'
import NavRail from './NavRail'
import BrowseDrawer from './BrowseDrawer'
import SurfaceShell from './SurfaceShell'
import { useSessionState } from './hooks/useSessionState'
import { useArtifactController } from './hooks/useArtifactController'
import { useToolBridge } from './hooks/useToolBridge'
import { ChatMetricsProvider } from '../../shared/hooks/useChatMetrics'
import { useReducedMotion } from '../../shared/hooks/useReducedMotion'
import { useShellPersistence } from './hooks/useShellPersistence'
import { useShellStatePublisher } from './hooks/useShellStatePublisher'
import { useAgentTransport } from '../../shared/providers/agent/useAgentTransport'

const EMPTY_MESSAGES = []
import ApiKeyPrompt from './components/ApiKeyPrompt'
import './layout.css'

/**
 * ChatCenteredWorkspace — the chat-first Stage + Wings shell.
 *
 * Renders:
 * - nav rail
 * - progressive-disclosure browse drawer
 * - permanent chat stage
 * - persistent Surface workbench
 */
export default function ChatCenteredWorkspace({ shellContext = {} }) {
  const reducedMotion = useReducedMotion()
  const {
    transport,
    mode: agentMode,
    thinkingLevel,
    setThinkingLevel,
    selectedModel,
    setModel,
    availableModels,
  } = useAgentTransport()

  const {
    activeSessionId,
    activeSession,
    sessions,
    switchSession,
    createNewSession,
    ensureSession,
    updateSessionDraft,
    updateSessionMessages,
  } = useSessionState()

  const {
    activeArtifactId,
    artifacts,
    orderedIds,
    open: openArtifact,
    focus: focusArtifact,
    close: closeArtifact,
  } = useArtifactController()

  const [activeDestination, setActiveDestination] = useState(null)
  const [surfaceCollapsed, setSurfaceCollapsed] = useState(true)
  const [surfaceWidth, setSurfaceWidth] = useState(620)
  const [surfaceSidebarWidth, setSurfaceSidebarWidth] = useState(296)
  const [surfaceLayout, setSurfaceLayout] = useState(null)

  useEffect(() => {
    ensureSession()
  }, [ensureSession])

  const sessionMessages = Array.isArray(activeSession?.messages) ? activeSession.messages : EMPTY_MESSAGES

  const {
    messages: chatMessages,
    sendMessage,
    status: chatStatus,
    stop,
    error: chatError,
  } = useChat({
    id: activeSessionId || 'chat-shell-bootstrap',
    messages: sessionMessages,
    transport,
  })

  const [chatInput, setChatInput] = useState(activeSession?.draft || '')

  useEffect(() => {
    setChatInput(activeSession?.draft || '')
  }, [activeSessionId, activeSession?.draft])

  useEffect(() => {
    if (!activeSessionId) return
    const timer = setTimeout(() => updateSessionDraft(activeSessionId, chatInput), 300)
    return () => clearTimeout(timer)
  }, [activeSessionId, chatInput, updateSessionDraft])

  useEffect(() => {
    if (!activeSessionId) return
    const timer = setTimeout(() => updateSessionMessages(activeSessionId, chatMessages), 500)
    return () => clearTimeout(timer)
  }, [activeSessionId, chatMessages, updateSessionMessages])

  useEffect(() => {
    if (!activeSessionId || typeof transport?.resetAgent !== 'function') return
    transport.resetAgent({ id: activeSessionId })
  }, [activeSessionId, transport])

  useShellPersistence({
    surfaceCollapsed,
    setSurfaceCollapsed,
    surfaceWidth,
    setSurfaceWidth,
    surfaceSidebarWidth,
    setSurfaceSidebarWidth,
    activeDestination,
    setActiveDestination,
    artifacts,
    orderedIds,
    activeArtifactId,
    openArtifact,
    focusArtifact,
    surfaceLayout,
    setSurfaceLayout,
  })

  useShellStatePublisher({
    activeDestination,
    drawerOpen: Boolean(activeDestination),
    drawerMode: 'sessions',
    surfaceCollapsed,
    activeArtifactId,
    orderedIds,
    activeSessionId,
  })

  const handleOpenArtifact = useCallback((artifact) => {
    if (!artifact) return

    openArtifact({
      sourceSessionId: activeSessionId || null,
      rendererKey: artifact.rendererKey || artifact.kind || 'code',
      status: artifact.status || 'ready',
      ...artifact,
    })
    setSurfaceCollapsed(false)
  }, [activeSessionId, openArtifact])

  useToolBridge({
    openArtifact: handleOpenArtifact,
    activeSessionId,
    artifacts,
    activeArtifactId,
  })

  const handleOpenFile = useCallback((filePath) => {
    if (!filePath) return
    handleOpenArtifact({
      kind: 'code',
      canonicalKey: filePath,
      title: filePath.split('/').pop() || filePath,
      source: 'user',
      rendererKey: 'code',
      params: { path: filePath },
    })
  }, [handleOpenArtifact])

  const handleSendMessage = useCallback(async () => {
    const text = chatInput.trim()
    if (!text) return
    setChatInput('')
    await sendMessage({ text })
  }, [chatInput, sendMessage])

  useEffect(() => {
    const handler = (event) => {
      const mod = event.metaKey || event.ctrlKey
      const key = String(event.key || '').toLowerCase()

      if (mod && key === '2') {
        event.preventDefault()
        setSurfaceCollapsed((collapsed) => !collapsed)
      }

      if (mod && key === '1') {
        event.preventDefault()
        setActiveDestination((destination) => (destination === 'sessions' ? null : 'sessions'))
      }

      if (mod && key === 'k') {
        event.preventDefault()
        const composer = document.querySelector('.vc-composer-input')
        if (composer) composer.focus()
      }

      if (event.key === 'Escape') {
        const composer = document.querySelector('.vc-composer-input')
        if (composer) composer.focus()
      }
    }

    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  const handleDestinationChange = useCallback((destination) => {
    setActiveDestination(destination === 'sessions' ? 'sessions' : null)
  }, [])

  const stopIfBusy = useCallback(() => {
    if (chatStatus === 'streaming' || chatStatus === 'submitted') {
      stop()
    }
  }, [chatStatus, stop])

  const handleNewChat = useCallback(() => {
    stopIfBusy()
    createNewSession()
    setActiveDestination(null)
  }, [createNewSession, stopIfBusy])

  const handleSwitchSession = useCallback((id) => {
    stopIfBusy()
    switchSession(id)
    setActiveDestination(null)
  }, [stopIfBusy, switchSession])

  const handleSurfaceClose = useCallback(() => setSurfaceCollapsed(true), [])
  const handleSurfaceCollapse = useCallback(() => setSurfaceCollapsed((c) => !c), [])

  const drawerOpen = Boolean(activeDestination)
  const artifactsList = useMemo(
    () => orderedIds.map((id) => artifacts.get(id)).filter(Boolean),
    [orderedIds, artifacts],
  )

  const activeArtifact = activeArtifactId ? artifacts.get(activeArtifactId) || null : null

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
          onToggleSurface={handleSurfaceCollapse}
          surfaceOpen={!surfaceCollapsed}
          shellContext={shellContext}
        />

        <BrowseDrawer
          open={drawerOpen}
          sessions={sessions}
          activeSessionId={activeSessionId}
          onSwitchSession={handleSwitchSession}
        />

        <main className="ccw-stage-area" role="main">
          <ChatStage
            activeSessionId={activeSessionId}
            sessionTitle={activeSession?.title || 'New chat'}
            messages={chatMessages}
            input={chatInput}
            onInputChange={setChatInput}
            onSubmit={handleSendMessage}
            onStop={stop}
            status={chatStatus}
            disabled={false}
            onOpenArtifact={handleOpenArtifact}
            thinkingLevel={thinkingLevel}
            onThinkingLevelChange={setThinkingLevel}
            agentMode={agentMode}
            selectedModel={selectedModel}
            onModelChange={setModel}
            availableModels={availableModels}
          />
          {chatError && (
            <div className="ccw-chat-error" role="status">
              {chatError.message}
              {agentMode === 'frontend' && /api key/i.test(chatError.message) && (
                <ApiKeyPrompt onKeySaved={() => transport.resetAgent({ id: activeSessionId })} />
              )}
            </div>
          )}
        </main>

        <SurfaceShell
          open={!surfaceCollapsed}
          collapsed={surfaceCollapsed}
          width={surfaceWidth}
          sidebarWidth={surfaceSidebarWidth}
          artifacts={artifactsList}
          activeArtifact={activeArtifact}
          activeArtifactId={activeArtifactId}
          onClose={handleSurfaceClose}
          onCollapse={handleSurfaceCollapse}
          onResize={setSurfaceWidth}
          onSidebarResize={setSurfaceSidebarWidth}
          layout={surfaceLayout}
          onLayoutChange={setSurfaceLayout}
          onSelectArtifact={focusArtifact}
          onCloseArtifact={closeArtifact}
          onOpenFile={handleOpenFile}
          shellContext={shellContext}
        />
      </div>
    </ChatMetricsProvider>
  )
}
