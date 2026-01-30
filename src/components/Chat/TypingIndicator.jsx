import React, { memo } from 'react'
import '../../styles/streaming.css'

/**
 * TypingIndicator Component - Animated typing dots
 *
 * Displays animated bouncing dots to indicate that an assistant is typing.
 * Features:
 * - Three bouncing dots with staggered animation
 * - 60fps GPU-accelerated animation
 * - Customizable colors and sizes
 * - Smooth loop animation
 * - Accessibility compliant
 *
 * @param {Object} props
 * @param {string} props.className - Additional CSS classes
 * @param {string} props.label - Accessibility label
 * @returns {React.ReactElement}
 */
const TypingIndicator = memo(
  ({
    className = '',
    label = 'Claude is typing',
  }) => {
    return (
      <div
        className={`typing-indicator ${className}`.trim()}
        role="status"
        aria-label={label}
        aria-live="polite"
      >
        <span className="typing-dot typing-dot-1" aria-hidden="true" />
        <span className="typing-dot typing-dot-2" aria-hidden="true" />
        <span className="typing-dot typing-dot-3" aria-hidden="true" />
      </div>
    )
  },
)

TypingIndicator.displayName = 'TypingIndicator'

export default TypingIndicator
