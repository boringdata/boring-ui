/**
 * Shared ToolUseBlock — Base wrapper for all tool renderers.
 *
 * Provides consistent chrome around any tool display:
 *   - Colored status bullet (green=complete, grey=pending/running, red=error)
 *   - Tool name + description header row
 *   - Optional subtitle (e.g. "Added 5 lines")
 *   - Collapsible content area with chevron toggle
 *
 * Accepts either explicit props (backward-compatible with Claude renderers)
 * OR a `result` NormalizedToolResult (extracts props automatically).
 *
 * CSS: requires tool-use-block.css (or the full chat/styles.css).
 *
 * @module shared/renderers/ToolUseBlock
 */
import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'

// ─── Status colors ──────────────────────────────────────────────────

/** @type {Record<import('./NormalizedToolResult').ToolStatus, string>} */
const STATUS_COLORS = {
  running: 'var(--color-text-secondary)',
  complete: 'var(--color-success)',
  error: 'var(--color-error)',
  pending: 'var(--color-text-secondary)',
}

// ─── ToolUseBlock ───────────────────────────────────────────────────

/**
 * @param {Object} props
 * @param {import('./NormalizedToolResult').NormalizedToolResult} [props.result]
 *   If provided, extracts toolName/description/subtitle/status from it.
 *   Explicit props override result fields when both are given.
 * @param {string} [props.toolName]
 * @param {string|React.ReactNode} [props.description]
 * @param {string} [props.subtitle]
 * @param {import('./NormalizedToolResult').ToolStatus} [props.status]
 * @param {boolean} [props.collapsible]
 * @param {boolean} [props.defaultExpanded]
 * @param {string} [props.className]
 * @param {React.ReactNode} [props.children]
 */
const ToolUseBlock = ({
  result,
  toolName,
  description,
  subtitle,
  status = 'complete',
  children,
  collapsible = false,
  defaultExpanded = true,
  className = '',
}) => {
  // Extract from NormalizedToolResult if provided, with explicit props taking priority
  const effectiveName = toolName ?? result?.toolName ?? ''
  const effectiveDesc = description ?? result?.description
  const effectiveSub = subtitle ?? result?.subtitle
  const effectiveStatus = status !== 'complete' ? status : (result?.status ?? status)

  const [isExpanded, setIsExpanded] = useState(defaultExpanded)
  const bulletColor = STATUS_COLORS[effectiveStatus] || STATUS_COLORS.complete

  return (
    <div className={`tool-use-block ${className}`}>
      {/* Header row with bullet, tool name, and description */}
      <div
        className={`tool-use-header ${collapsible ? 'clickable' : ''}`}
        onClick={collapsible ? () => setIsExpanded(!isExpanded) : undefined}
      >
        {/* Status bullet */}
        <span className="tool-use-bullet" style={{ color: bulletColor }}>
          ●
        </span>

        {/* Tool name, description, and subtitle */}
        <div className="tool-use-info">
          <div className="tool-use-title-row">
            <span className="tool-use-name">{effectiveName}</span>
            {effectiveDesc && (
              <span className="tool-use-description">{effectiveDesc}</span>
            )}
            {collapsible && (
              <span className="tool-use-collapse-icon">
                {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
              </span>
            )}
          </div>
          {effectiveSub && <span className="tool-use-subtitle">{effectiveSub}</span>}
        </div>
      </div>

      {/* Content area (collapsible) */}
      {(!collapsible || isExpanded) && children && (
        <div className="tool-use-content">{children}</div>
      )}
    </div>
  )
}

// ─── Sub-components ─────────────────────────────────────────────────

/** Styled container for tool output/results. */
export const ToolOutput = ({ children, style = {}, className = '' }) => (
  <div className={`tool-output ${className}`} style={style}>
    {children}
  </div>
)

/** Styled command/input display with optional language badge. */
export const ToolCommand = ({ command, language }) => (
  <div className="tool-command">
    {language && <span className="tool-command-language">{language}</span>}
    <code className="tool-command-code">{command}</code>
  </div>
)

/** Styled error message display. */
export const ToolError = ({ message }) => (
  <div className="tool-error">{message}</div>
)

/** Styled inline code element. */
export const InlineCode = ({ children }) => (
  <code className="inline-code">{children}</code>
)

export default ToolUseBlock
