import React, { useState, useCallback, useMemo, memo } from 'react'
import { X } from 'lucide-react'
import MessageBubble from './MessageBubble'
import TypingIndicator from './TypingIndicator'
import '../../styles/streaming.css'

/**
 * StreamingMessage Component - Real-time message streaming UI
 *
 * Handles the display of streaming messages with:
 * - Word-by-word animation
 * - Progressive code block rendering
 * - Tool invocation indicators
 * - Progress percentage
 * - Cancel streaming button
 * - Estimated time remaining
 *
 * @param {Object} props
 * @param {string} props.id - Message ID
 * @param {string} props.content - Current message content
 * @param {string} props.author - Message author
 * @param {'user'|'assistant'} props.role - Message role
 * @param {boolean} props.isStreaming - Whether message is currently streaming
 * @param {Function} props.onCancel - Callback to cancel streaming
 * @param {number} props.progress - Stream progress 0-100
 * @param {Array} props.toolsInvoking - Array of tool names being invoked
 * @param {string} props.estimatedTimeRemaining - Estimated time (e.g., "5s")
 * @param {number} props.wordCount - Current word count
 * @param {boolean} props.showTypingIndicator - Show typing indicator
 * @returns {React.ReactElement}
 */
const StreamingMessage = memo(
  ({
    id = 'streaming-msg',
    content = '',
    author = 'Claude',
    role = 'assistant',
    isStreaming = true,
    onCancel = null,
    progress = null,
    toolsInvoking = [],
    estimatedTimeRemaining = null,
    wordCount = 0,
    showTypingIndicator = true,
    className = '',
  }) => {
    const [cancelled, setCancelled] = useState(false)

    const handleCancel = useCallback(() => {
      setCancelled(true)
      onCancel?.()
    }, [onCancel])

    // Format progress text
    const progressText = useMemo(() => {
      if (progress === null) return null
      return `${Math.round(progress)}%`
    }, [progress])

    // Format word count
    const wordCountText = useMemo(() => {
      if (wordCount === 0) return null
      return `${wordCount} word${wordCount !== 1 ? 's' : ''}`
    }, [wordCount])

    const containerClasses = `
      streaming-message-container
      ${isStreaming ? 'streaming-active' : 'streaming-complete'}
      ${cancelled ? 'streaming-cancelled' : ''}
      ${className}
    `.trim()

    return (
      <div className={containerClasses} data-message-id={id}>
        {/* Message bubble with content */}
        <div className="streaming-bubble-wrapper">
          <MessageBubble
            content={content || <TypingIndicator label="Assistant is typing..." />}
            isUser={false}
            isStreaming={isStreaming && !content}
            bubbleClasses="streaming-bubble"
          />
        </div>

        {/* Streaming status bar */}
        {isStreaming && (
          <div className="streaming-status">
            {/* Progress indicator */}
            {progress !== null && (
              <div className="streaming-progress-group">
                <div className="streaming-progress-bar">
                  <div
                    className="streaming-progress-fill"
                    style={{ width: `${Math.min(progress, 100)}%` }}
                  />
                </div>
                <span className="streaming-progress-text">{progressText}</span>
              </div>
            )}

            {/* Tools being invoked */}
            {toolsInvoking && toolsInvoking.length > 0 && (
              <div className="streaming-tools">
                <span className="streaming-tools-label">Tools:</span>
                <div className="streaming-tools-list">
                  {toolsInvoking.map((tool, idx) => (
                    <span key={`${id}-tool-${idx}`} className="streaming-tool-badge">
                      {tool}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Metadata: word count, time remaining, cancel button */}
            <div className="streaming-footer">
              <div className="streaming-metadata">
                {wordCountText && (
                  <span className="streaming-meta-item">{wordCountText}</span>
                )}
                {estimatedTimeRemaining && (
                  <span className="streaming-meta-item">
                    ETA: {estimatedTimeRemaining}
                  </span>
                )}
              </div>

              {onCancel && (
                <button
                  className="streaming-cancel-btn"
                  onClick={handleCancel}
                  disabled={cancelled}
                  title="Cancel streaming"
                  aria-label="Cancel message streaming"
                >
                  <X size={16} />
                  <span>Cancel</span>
                </button>
              )}
            </div>
          </div>
        )}

        {/* Completion indicator */}
        {!isStreaming && !cancelled && (
          <div className="streaming-complete-indicator">
            <span className="check-mark">✓</span>
            <span>Message complete</span>
          </div>
        )}

        {/* Cancellation indicator */}
        {cancelled && (
          <div className="streaming-cancelled-indicator">
            <span className="cancel-mark">●</span>
            <span>Stream cancelled</span>
          </div>
        )}
      </div>
    )
  },
)

StreamingMessage.displayName = 'StreamingMessage'

export default StreamingMessage
