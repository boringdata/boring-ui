import React, { useRef, useEffect } from 'react'
import { Sparkles, MessageSquareText } from 'lucide-react'
import ChatMessage from '../../shared/components/chat/ChatMessage'
import ChatComposer from './components/ChatComposer'
import '../../shared/components/chat/chat-stage.css'

/**
 * ChatStage - Main container component for the chat experience.
 *
 * Manages message list rendering, scroll behavior, empty state,
 * and composer integration. Designed to be connected to useChat + useChatTransport
 * by a parent component.
 *
 * Props:
 *   messages  - UIMessage[] from useChat
 *   input     - string, current composer input value
 *   onInputChange - (value: string) => void
 *   onSubmit  - () => void, send message
 *   onStop    - () => void, stop streaming
 *   status    - 'ready' | 'streaming' | 'submitted'
 *   disabled  - boolean
 */
export default function ChatStage({
  activeSessionId = null,
  sessionTitle = 'New chat',
  messages = [],
  input = '',
  onInputChange,
  onSubmit,
  onStop,
  status = 'ready',
  disabled = false,
  onOpenArtifact,
  thinkingLevel,
  onThinkingLevelChange,
  agentMode,
  selectedModel,
  onModelChange,
  availableModels,
}) {
  const scrollRef = useRef(null)

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  const isEmpty = messages.length === 0
  const lastAssistantIndex = messages.findLastIndex((m) => m.role === 'assistant')

  return (
    <div className="vc-stage">
      <div className="vc-stage-header">
        <div className="vc-stage-header-copy">
          <div className="vc-stage-eyebrow">Chat</div>
          <div className="vc-stage-title-row">
            <MessageSquareText size={14} />
            <span className="vc-stage-title">{sessionTitle}</span>
          </div>
        </div>
        {activeSessionId && (
          <span className="vc-stage-session-pill" data-testid="chat-session-pill">
            {activeSessionId.slice(0, 8)}
          </span>
        )}
      </div>

      <div className="vc-stage-scroll" ref={scrollRef}>
        <div className="vc-stage-messages">
          {isEmpty && (
            <div className="vc-stage-empty">
              <Sparkles size={32} className="vc-stage-empty-icon" />
              <span className="vc-stage-empty-title">
                What can I help with?
              </span>
              <span className="vc-stage-empty-hint">
                Results appear on the Surface
              </span>
            </div>
          )}
          {messages.map((msg, index) => (
            <ChatMessage
              key={msg.id}
              message={msg}
              activeSessionId={activeSessionId}
              onOpenArtifact={onOpenArtifact}
              isLastAssistantMessage={msg.role === 'assistant' && index === lastAssistantIndex}
            />
          ))}
        </div>
      </div>
      <ChatComposer
        value={input}
        onChange={onInputChange}
        onSubmit={onSubmit}
        onStop={onStop}
        status={status}
        disabled={disabled}
        thinkingLevel={thinkingLevel}
        onThinkingLevelChange={onThinkingLevelChange}
        agentMode={agentMode}
        selectedModel={selectedModel}
        onModelChange={onModelChange}
        availableModels={availableModels}
      />
    </div>
  )
}
