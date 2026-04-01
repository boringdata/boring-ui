import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Send, Square, Brain, ChevronDown } from 'lucide-react'

import { THINKING_LEVELS } from '../../../shared/providers/pi/piAgentCoreTransport'

/**
 * ChatComposer - Pill-shaped input with keyboard hints and send/stop controls.
 *
 * Props:
 *   value          - string, current input text
 *   onChange       - (value: string) => void
 *   onSubmit       - () => void, called on Enter (without Shift)
 *   onStop         - () => void, called when Stop button clicked
 *   status         - 'ready' | 'streaming' | 'submitted'
 *   disabled       - boolean
 *   thinkingLevel  - 'off' | 'low' | 'high' (optional, frontend mode only)
 *   onThinkingLevelChange - (level) => void (optional)
 *   agentMode      - 'frontend' | 'backend' (optional, controls visibility)
 */
export default function ChatComposer({
  value,
  onChange,
  onSubmit,
  onStop,
  status,
  disabled,
  thinkingLevel = 'off',
  onThinkingLevelChange,
  agentMode,
  selectedModel,
  onModelChange,
  availableModels = [],
}) {
  const textareaRef = useRef(null)

  useEffect(() => {
    const textarea = textareaRef.current
    if (!textarea) return
    textarea.style.height = '0px'
    textarea.style.height = `${Math.min(textarea.scrollHeight, 160)}px`
  }, [value])

  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        if (value.trim() && !disabled) {
          onSubmit()
        }
      }
    },
    [value, disabled, onSubmit]
  )

  const handleChange = useCallback(
    (e) => {
      onChange(e.target.value)
    },
    [onChange]
  )

  const isStreaming = status === 'streaming'
  const canSend = value.trim().length > 0 && !disabled && !isStreaming

  const cycleThinking = useCallback(() => {
    if (!onThinkingLevelChange) return
    const idx = THINKING_LEVELS.indexOf(thinkingLevel)
    const next = THINKING_LEVELS[(idx + 1) % THINKING_LEVELS.length]
    onThinkingLevelChange(next)
  }, [thinkingLevel, onThinkingLevelChange])

  const showThinking = typeof onThinkingLevelChange === 'function'
  const showModelSelector = typeof onModelChange === 'function' && availableModels.length > 0

  const [modelMenuOpen, setModelMenuOpen] = useState(false)
  const modelMenuRef = useRef(null)

  // Close model menu on outside click
  useEffect(() => {
    if (!modelMenuOpen) return
    const handler = (e) => {
      if (modelMenuRef.current && !modelMenuRef.current.contains(e.target)) {
        setModelMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [modelMenuOpen])

  const activeModelLabel = selectedModel
    ? availableModels.find((m) => m.provider === selectedModel.provider && m.modelId === selectedModel.modelId)?.label || selectedModel.modelId
    : availableModels.find((m) => m.available)?.label || 'Auto'

  return (
    <div className="vc-composer-wrap">
      <div className="vc-composer">
        <textarea
          ref={textareaRef}
          role="textbox"
          className="vc-composer-input"
          placeholder="Ask a question..."
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          rows={1}
        />
        <div className="vc-composer-hints">
          {showModelSelector && (
            <div className="vc-model-selector" ref={modelMenuRef}>
              <button
                type="button"
                className="vc-model-trigger"
                data-testid="model-selector"
                onClick={() => setModelMenuOpen((o) => !o)}
              >
                <span className="vc-model-trigger-label">{activeModelLabel}</span>
                <ChevronDown size={12} />
              </button>
              {modelMenuOpen && (
                <div className="vc-model-menu" data-testid="model-menu">
                  {availableModels.map((m) => (
                    <button
                      key={`${m.provider}:${m.modelId}`}
                      type="button"
                      className={`vc-model-option${
                        selectedModel?.provider === m.provider && selectedModel?.modelId === m.modelId ? ' active' : ''
                      }${!m.available ? ' unavailable' : ''}`}
                      disabled={!m.available}
                      onClick={() => {
                        onModelChange(m.provider, m.modelId)
                        setModelMenuOpen(false)
                      }}
                    >
                      <span className="vc-model-option-label">{m.label}</span>
                      {!m.available && <span className="vc-model-option-badge">No key</span>}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
          {showThinking && (
            <button
              type="button"
              className={`vc-thinking-toggle${thinkingLevel !== 'off' ? ' active' : ''}`}
              data-testid="thinking-toggle"
              onClick={cycleThinking}
              title={`Thinking: ${thinkingLevel}`}
            >
              <Brain size={14} />
              {thinkingLevel !== 'off' && (
                <span className="vc-thinking-label">{thinkingLevel}</span>
              )}
            </button>
          )}
          <kbd className="vc-kbd">&#8984;</kbd>
          <kbd className="vc-kbd">K</kbd>
        </div>
        {isStreaming ? (
          <button
            className="vc-composer-stop"
            data-testid="chat-stop-btn"
            onClick={onStop}
            type="button"
          >
            <Square size={14} />
          </button>
        ) : (
          <button
            className="vc-composer-send"
            data-testid="chat-send-btn"
            onClick={canSend ? onSubmit : undefined}
            disabled={!canSend}
            type="button"
          >
            <Send size={16} />
          </button>
        )}
      </div>
    </div>
  )
}
