import React, { memo } from 'react'
import './chat-animations.css'

/**
 * MessageBubble Component - Message content with styling and animations
 *
 * Renders the message bubble with:
 * - Gradient backgrounds for assistant/user differentiation
 * - Support for markdown/HTML content
 * - Smooth fade-in animation
 * - Loading skeleton during streaming
 * - Optimized for performance with memo
 *
 * @param {Object} props
 * @param {string} props.content - Message content (text, markdown, or HTML)
 * @param {boolean} props.isUser - Whether message is from user
 * @param {boolean} props.isStreaming - Whether message is currently streaming
 * @param {string} props.bubbleClasses - Additional CSS classes for bubble
 * @returns {React.ReactElement}
 */
const MessageBubble = memo(
  ({ content, isUser = false, isStreaming = false, bubbleClasses = '' }) => {
    return (
      <div className={`${bubbleClasses} animate-fade-in animate-slide-up`}>
        {isStreaming && !content ? (
          // Skeleton loader for streaming messages
          <div className="message-skeleton">
            <div className="skeleton-line skeleton-line-1" />
            <div className="skeleton-line skeleton-line-2" />
            <div className="skeleton-line skeleton-line-3" />
          </div>
        ) : (
          <div className="message-text">
            {content || (
              <span className="text-muted" style={{ opacity: 0.6 }}>
                (empty message)
              </span>
            )}
          </div>
        )}

        {isStreaming && content && (
          <div className="message-streaming-indicator">
            <span className="streaming-dot" />
            <span className="streaming-dot" />
            <span className="streaming-dot" />
          </div>
        )}
      </div>
    )
  },
)

MessageBubble.displayName = 'MessageBubble'

export default MessageBubble
