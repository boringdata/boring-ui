import React, { useMemo, useEffect, useRef } from 'react'
import MessageBubble from './MessageBubble'
import './chat-animations.css'

/**
 * Message Component - Individual message display with animations
 *
 * Renders a single message with:
 * - Author avatar with fade-in animation
 * - Timestamp with smart formatting (just now, 5m ago, etc.)
 * - Message content with smooth fade-in/slide animation
 * - Reaction indicators
 * - Author name for grouped messages
 *
 * @param {Object} props
 * @param {string} props.id - Unique message ID
 * @param {string} props.content - Message text content
 * @param {string} props.author - Message author (user or assistant)
 * @param {'user'|'assistant'} props.role - Message role for styling
 * @param {Date|string} props.timestamp - Message creation time
 * @param {boolean} props.isStreaming - Whether message is currently streaming
 * @param {boolean} props.showGrouped - Whether to show author name (first in group)
 * @param {Array} props.reactions - Array of reaction objects {emoji, count, users}
 * @param {number} props.animationDelay - Stagger animation delay (ms)
 * @returns {React.ReactElement}
 */

/**
 * Format timestamp as relative time string without external dependencies
 * @param {Date|string} timestamp - The timestamp to format
 * @returns {string} Formatted time string (e.g., "just now", "5m ago")
 */
function formatRelativeTime(timestamp) {
  if (!timestamp) return ''
  try {
    const date = timestamp instanceof Date ? timestamp : new Date(timestamp)
    if (isNaN(date.getTime())) return ''

    const now = new Date()
    const diffMs = now - date
    const diffSeconds = Math.floor(diffMs / 1000)
    const diffMinutes = Math.floor(diffSeconds / 60)
    const diffHours = Math.floor(diffMinutes / 60)
    const diffDays = Math.floor(diffHours / 24)

    if (diffSeconds < 60) return 'just now'
    if (diffMinutes < 60) return `${diffMinutes}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays < 7) return `${diffDays}d ago`

    // For older messages, show date in short format
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    })
  } catch (e) {
    return ''
  }
}

const Message = React.forwardRef(
  (
    {
      id,
      content,
      author = 'assistant',
      role = 'assistant',
      timestamp,
      isStreaming = false,
      showGrouped = true,
      reactions = [],
      animationDelay = 0,
      className = '',
    },
    ref,
  ) => {
    const messageRef = useRef(null)
    const containerRef = ref || messageRef

    // Smart timestamp formatting
    const formattedTime = useMemo(() => {
      return formatRelativeTime(timestamp)
    }, [timestamp])

    // Determine message styling based on role
    const isUser = role === 'user'
    const messageClasses = `
      message-container
      message-role-${role}
      ${isStreaming ? 'message-streaming' : ''}
      ${className}
    `.trim()

    const bubbleClasses = `
      message-bubble
      ${isUser ? 'message-bubble-user' : 'message-bubble-assistant'}
    `.trim()

    // Track render performance
    useEffect(() => {
      const renderTime = performance.now()
      return () => {
        const renderDuration = performance.now() - renderTime
        if (renderDuration > 100) {
          console.warn(`Message render took ${renderDuration.toFixed(2)}ms`)
        }
      }
    }, [])

    return (
      <div
        ref={containerRef}
        data-message-id={id}
        className={messageClasses}
        style={{
          '--animation-delay': `${animationDelay}ms`,
        }}
      >
        {/* Author and metadata row */}
        {showGrouped && (
          <div className="message-header">
            {/* Avatar */}
            <div className="message-avatar animate-fade-in">
              {isUser ? (
                <div className="avatar-user" title={author}>
                  {author.charAt(0).toUpperCase()}
                </div>
              ) : (
                <div className="avatar-assistant" title="Claude">
                  C
                </div>
              )}
            </div>

            {/* Author name and timestamp */}
            <div className="message-meta">
              <span className="message-author">{isUser ? 'You' : author}</span>
              {formattedTime && <span className="message-time">{formattedTime}</span>}
            </div>
          </div>
        )}

        {/* Message content bubble */}
        <div className="message-content-wrapper">
          <MessageBubble
            content={content}
            isUser={isUser}
            isStreaming={isStreaming}
            bubbleClasses={bubbleClasses}
          />

          {/* Reactions */}
          {reactions && reactions.length > 0 && (
            <div className="message-reactions">
              {reactions.map((reaction, idx) => (
                <div
                  key={`${id}-reaction-${idx}`}
                  className="reaction-chip animate-scale-in"
                  style={{
                    '--animation-delay': `${animationDelay + (idx + 1) * 50}ms`,
                  }}
                  title={`${reaction.users?.join(', ') || ''}`}
                >
                  <span className="reaction-emoji">{reaction.emoji}</span>
                  {reaction.count > 1 && (
                    <span className="reaction-count">{reaction.count}</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    )
  },
)

Message.displayName = 'Message'

export default Message
