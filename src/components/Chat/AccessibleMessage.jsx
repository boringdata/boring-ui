import { forwardRef } from 'react'

/**
 * AccessibleMessage - Screen reader optimized message component
 *
 * Features:
 * - Semantic HTML structure (article element)
 * - ARIA labels for roles and timestamps
 * - High contrast support
 * - Focus management
 * - Keyboard navigation
 * - Semantic emphasis for code blocks
 * - Proper link handling with target="_blank" attributes
 *
 * @param {Object} props
 * @param {React.ReactNode} props.children - Message content
 * @param {'user' | 'assistant'} props.role - Message author role
 * @param {string} [props.timestamp] - Message timestamp for screen readers
 * @param {string} [props.messageId] - Unique message ID
 * @param {boolean} [props.isLoading] - Whether message is still loading
 * @param {Array<Object>} [props.actions] - Action buttons for the message
 * @param {Function} [props.onActionClick] - Callback for action clicks
 * @param {string} [props.className] - Additional CSS classes
 * @returns {React.ReactElement}
 *
 * @example
 * ```jsx
 * <AccessibleMessage
 *   role="assistant"
 *   timestamp="2:45 PM"
 *   messageId="msg-1"
 * >
 *   <p>Hello! How can I help you?</p>
 * </AccessibleMessage>
 * ```
 */
const AccessibleMessage = forwardRef(
  (
    {
      children,
      role = 'assistant',
      timestamp,
      messageId,
      isLoading = false,
      actions = [],
      onActionClick,
      className = '',
    },
    ref
  ) => {
    const isUser = role === 'user'
    const roleLabel = isUser ? 'You' : 'Assistant'

    // Generate unique ID for aria-labelledby
    const headerId = messageId ? `${messageId}-header` : undefined
    const contentId = messageId ? `${messageId}-content` : undefined

    return (
      <article
        ref={ref}
        className={`accessible-message accessible-message-${role} ${className}`}
        role="article"
        aria-label={`Message from ${roleLabel}${timestamp ? ` at ${timestamp}` : ''}`}
        aria-labelledby={headerId}
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--space-2)',
          padding: 'var(--space-3) var(--space-4)',
          borderRadius: 'var(--radius-lg)',
          backgroundColor: isUser
            ? 'var(--color-accent)'
            : 'var(--color-bg-tertiary)',
          color: isUser ? 'white' : 'var(--color-text-primary)',
          wordBreak: 'break-word',
          overflowWrap: 'break-word',
          hyphens: 'auto',
          border: '1px solid transparent',
          outline: 'none',
        }}
        tabIndex={0}
      >
        {/* Semantic header with role and timestamp */}
        <header
          id={headerId}
          className="accessible-message-header"
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            fontSize: 'var(--text-xs)',
            opacity: 0.8,
            gap: 'var(--space-2)',
          }}
        >
          <span
            className="message-role"
            style={{ fontWeight: 'var(--font-semibold)' }}
          >
            {roleLabel}
          </span>
          {timestamp && (
            <time
              className="message-timestamp"
              dateTime={timestamp}
              style={{ opacity: 0.7 }}
            >
              {timestamp}
            </time>
          )}
          {isLoading && (
            <span
              className="message-loading"
              aria-label="Message loading"
              style={{ opacity: 0.6 }}
            >
              ●
            </span>
          )}
        </header>

        {/* Main content */}
        <div
          id={contentId}
          className="accessible-message-content"
          style={{
            lineHeight: 'var(--leading-relaxed)',
            fontSize: 'var(--text-sm)',
          }}
        >
          {children}
        </div>

        {/* Actions (if provided) */}
        {actions.length > 0 && (
          <footer
            className="accessible-message-actions"
            role="toolbar"
            aria-label={`Actions for message from ${roleLabel}`}
            style={{
              display: 'flex',
              gap: 'var(--space-2)',
              marginTop: 'var(--space-2)',
              paddingTop: 'var(--space-2)',
              borderTop: '1px solid currentColor',
              opacity: 0.8,
            }}
          >
            {actions.map((action) => (
              <button
                key={action.id}
                className={`message-action-button ${action.className || ''}`}
                onClick={() => onActionClick?.(action.id)}
                aria-label={action.label}
                title={action.label}
                style={{
                  padding: 'var(--space-2) var(--space-3)',
                  minWidth: '44px',
                  minHeight: '44px',
                  backgroundColor: 'transparent',
                  border: '1px solid currentColor',
                  borderRadius: 'var(--radius-md)',
                  color: 'inherit',
                  cursor: 'pointer',
                  fontSize: 'var(--text-xs)',
                  fontWeight: 'var(--font-medium)',
                  transition: 'all 150ms ease',
                  opacity: 0.8,
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.opacity = '1'
                  e.currentTarget.style.backgroundColor = 'currentColor'
                  e.currentTarget.style.color = isUser
                    ? 'var(--color-accent)'
                    : 'var(--color-bg-tertiary)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.opacity = '0.8'
                  e.currentTarget.style.backgroundColor = 'transparent'
                  e.currentTarget.style.color = 'inherit'
                }}
              >
                {action.icon && <span style={{ marginRight: 'var(--space-1)' }}>{action.icon}</span>}
                {action.label}
              </button>
            ))}
          </footer>
        )}
      </article>
    )
  }
)

AccessibleMessage.displayName = 'AccessibleMessage'

/**
 * AccessibleCodeBlock - Screen reader optimized code block
 * Announces language and line count for screen readers
 *
 * @param {Object} props
 * @param {string} props.code - Code content
 * @param {string} [props.language] - Programming language
 * @param {number} [props.lineCount] - Number of lines
 * @returns {React.ReactElement}
 */
export function AccessibleCodeBlock({
  code,
  language = 'text',
  lineCount = 0,
}) {
  const lines = code.split('\n').length

  return (
    <figure
      className="accessible-code-block"
      style={{
        margin: 'var(--space-3) 0',
        backgroundColor: 'var(--color-code-bg)',
        borderRadius: 'var(--radius-md)',
        overflow: 'hidden',
      }}
    >
      <figcaption
        className="code-block-caption"
        style={{
          padding: 'var(--space-2) var(--space-3)',
          backgroundColor: 'var(--color-bg-secondary)',
          fontSize: 'var(--text-xs)',
          fontFamily: 'var(--font-mono)',
          color: 'var(--color-text-secondary)',
          borderBottom: '1px solid var(--color-border)',
        }}
      >
        <span className="language-name" style={{ fontWeight: 'var(--font-semibold)' }}>
          {language}
        </span>
        <span
          className="line-count"
          style={{
            marginLeft: 'var(--space-3)',
            opacity: 0.7,
          }}
          aria-label={`${lines} lines of code`}
        >
          {lines} lines
        </span>
      </figcaption>
      <pre
        style={{
          padding: 'var(--space-4)',
          overflowX: 'auto',
          fontSize: 'var(--text-sm)',
          lineHeight: 'var(--leading-relaxed)',
          margin: 0,
        }}
        aria-label={`Code block in ${language}`}
      >
        <code
          style={{
            fontFamily: 'var(--font-mono)',
            color: 'var(--color-text-primary)',
          }}
        >
          {code}
        </code>
      </pre>
    </figure>
  )
}

/**
 * AccessibleLink - Accessible external link component
 * Announces when link opens in new tab/window
 *
 * @param {Object} props
 * @param {string} props.href - Link URL
 * @param {React.ReactNode} props.children - Link text
 * @param {boolean} [props.external] - Whether link opens in new tab
 * @param {string} [props.className] - Additional CSS classes
 * @returns {React.ReactElement}
 */
export function AccessibleLink({
  href,
  children,
  external = false,
  className = '',
}) {
  const externalProps = external
    ? {
        target: '_blank',
        rel: 'noopener noreferrer',
      }
    : {}

  return (
    <a
      href={href}
      className={`accessible-link ${className}`}
      style={{
        color: 'var(--color-accent)',
        textDecoration: 'underline',
        textDecorationThickness: '2px',
        textUnderlineOffset: '3px',
        cursor: 'pointer',
        transition: 'color 150ms ease',
        outline: 'none',
      }}
      aria-label={`${children}${external ? ' (opens in new window)' : ''}`}
      onMouseEnter={(e) => {
        e.currentTarget.style.color = 'var(--color-accent-hover)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.color = 'var(--color-accent)'
      }}
      onFocus={(e) => {
        e.currentTarget.style.outlineWidth = '2px'
        e.currentTarget.style.outlineStyle = 'solid'
        e.currentTarget.style.outlineColor = 'var(--color-accent)'
        e.currentTarget.style.outlineOffset = '2px'
      }}
      onBlur={(e) => {
        e.currentTarget.style.outline = 'none'
      }}
      {...externalProps}
    >
      {children}
      {external && (
        <span
          className="external-icon"
          aria-hidden="true"
          style={{ marginLeft: '0.25em' }}
        >
          ↗
        </span>
      )}
    </a>
  )
}

/**
 * AccessibleList - Accessible list component with semantic structure
 * Announces list context to screen readers
 *
 * @param {Object} props
 * @param {React.ReactNode} props.children - List items
 * @param {string} [props.type] - 'ordered' or 'unordered'
 * @param {string} [props.aria-label] - List label for screen readers
 * @returns {React.ReactElement}
 */
export function AccessibleList({
  children,
  type = 'unordered',
  'aria-label': ariaLabel,
}) {
  const Component = type === 'ordered' ? 'ol' : 'ul'

  return (
    <Component
      className={`accessible-list accessible-list-${type}`}
      aria-label={ariaLabel}
      style={{
        margin: 'var(--space-3) 0',
        paddingLeft: 'var(--space-6)',
        lineHeight: 'var(--leading-relaxed)',
      }}
    >
      {children}
    </Component>
  )
}

/**
 * AccessibleListItem - Accessible list item with proper semantics
 *
 * @param {Object} props
 * @param {React.ReactNode} props.children - Item content
 * @param {string} [props.className] - Additional CSS classes
 * @returns {React.ReactElement}
 */
export function AccessibleListItem({ children, className = '' }) {
  return (
    <li
      className={`accessible-list-item ${className}`}
      style={{
        marginBottom: 'var(--space-2)',
        color: 'var(--color-text-primary)',
      }}
    >
      {children}
    </li>
  )
}

/**
 * AccessibleHeading - Semantic heading with proper hierarchy
 *
 * @param {Object} props
 * @param {React.ReactNode} props.children - Heading text
 * @param {1|2|3|4|5|6} [props.level] - Heading level (1-6)
 * @param {string} [props.className] - Additional CSS classes
 * @returns {React.ReactElement}
 */
export function AccessibleHeading({
  children,
  level = 2,
  className = '',
}) {
  const Component = `h${level}`
  const sizes = {
    1: 'var(--text-2xl)',
    2: 'var(--text-xl)',
    3: 'var(--text-lg)',
    4: 'var(--text-base)',
    5: 'var(--text-sm)',
    6: 'var(--text-xs)',
  }

  return (
    <Component
      className={`accessible-heading h${level} ${className}`}
      style={{
        fontSize: sizes[level],
        fontWeight: 'var(--font-semibold)',
        marginTop: 'var(--space-4)',
        marginBottom: 'var(--space-2)',
        lineHeight: 'var(--leading-tight)',
        color: 'var(--color-text-primary)',
      }}
    >
      {children}
    </Component>
  )
}

/**
 * AccessibleParagraph - Semantic paragraph with proper spacing
 *
 * @param {Object} props
 * @param {React.ReactNode} props.children - Paragraph content
 * @param {string} [props.className] - Additional CSS classes
 * @returns {React.ReactElement}
 */
export function AccessibleParagraph({ children, className = '' }) {
  return (
    <p
      className={`accessible-paragraph ${className}`}
      style={{
        marginBottom: 'var(--space-3)',
        lineHeight: 'var(--leading-relaxed)',
        color: 'var(--color-text-primary)',
      }}
    >
      {children}
    </p>
  )
}

/**
 * AccessibleEmphasis - Semantic emphasis/strong tags
 *
 * @param {Object} props
 * @param {React.ReactNode} props.children - Content to emphasize
 * @param {'emphasis' | 'strong'} [props.type] - Type of emphasis
 * @returns {React.ReactElement}
 */
export function AccessibleEmphasis({
  children,
  type = 'emphasis',
}) {
  const Component = type === 'strong' ? 'strong' : 'em'

  return (
    <Component
      style={{
        fontStyle: type === 'emphasis' ? 'italic' : 'normal',
        fontWeight: type === 'strong' ? 'var(--font-semibold)' : 'normal',
      }}
    >
      {children}
    </Component>
  )
}

export default AccessibleMessage
