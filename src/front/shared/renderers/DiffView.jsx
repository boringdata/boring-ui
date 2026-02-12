/**
 * Shared DiffView — Unified diff display with colored lines.
 *
 * Renders diff content with:
 *   - Green background for additions (+)
 *   - Red background for deletions (-)
 *   - Muted text for headers (@@, ---, +++)
 *   - Neutral background for context lines
 *   - Optional line numbers
 *   - Scrollable/collapsible container
 *
 * Accepts either raw text, a string array, or parsed DiffLine objects.
 *
 * CSS variables used:
 *   --chat-diff-add-bg, --chat-diff-add-text
 *   --chat-diff-remove-bg, --chat-diff-remove-text
 *   --chat-text-muted, --chat-text, --font-mono, --text-sm
 *
 * @module shared/renderers/DiffView
 */
import { parseDiffLines } from './NormalizedToolResult'

// ─── DiffView ───────────────────────────────────────────────────────

/**
 * @param {Object} props
 * @param {string|string[]|import('./NormalizedToolResult').DiffLine[]} props.diff
 *   Raw diff text (string), array of line strings, or parsed DiffLine[].
 * @param {number} [props.linesAdded] - Count of added lines (display only)
 * @param {number} [props.linesRemoved] - Count of removed lines (display only)
 * @param {number} [props.maxHeight] - Max container height in px (default: none)
 * @param {boolean} [props.showLineNumbers] - Show line numbers (default: false)
 * @param {string} [props.className] - Additional CSS class
 */
const DiffView = ({
  diff,
  maxHeight,
  showLineNumbers = false,
  className = '',
}) => {
  if (!diff) return null

  // Normalize input to DiffLine[] array
  let lines
  if (typeof diff === 'string') {
    lines = parseDiffLines(diff)
  } else if (Array.isArray(diff) && diff.length > 0) {
    // Check if already parsed DiffLine objects or raw strings
    if (typeof diff[0] === 'string') {
      lines = parseDiffLines(diff)
    } else {
      lines = diff
    }
  } else {
    return null
  }

  if (lines.length === 0) return null

  return (
    <div
      className={`shared-diff-view ${className}`}
      style={{
        fontFamily: 'var(--font-mono, monospace)',
        fontSize: 'var(--text-sm, 13px)',
        lineHeight: '1.5',
        borderRadius: 'var(--radius-sm, 4px)',
        overflow: maxHeight ? 'auto' : 'hidden',
        maxHeight: maxHeight ? `${maxHeight}px` : undefined,
      }}
    >
      {lines.map((line, i) => (
        <DiffLine key={i} line={line} index={i} showLineNumber={showLineNumbers} />
      ))}
    </div>
  )
}

// ─── DiffLine ───────────────────────────────────────────────────────

const LINE_STYLES = {
  add: {
    backgroundColor: 'var(--chat-diff-add-bg, rgba(46, 160, 67, 0.15))',
    color: 'var(--chat-diff-add-text, #3fb950)',
  },
  remove: {
    backgroundColor: 'var(--chat-diff-remove-bg, rgba(248, 81, 73, 0.15))',
    color: 'var(--chat-diff-remove-text, #f85149)',
  },
  header: {
    backgroundColor: 'transparent',
    color: 'var(--chat-text-muted, #888)',
  },
  context: {
    backgroundColor: 'transparent',
    color: 'var(--chat-text, #e0e0e0)',
  },
}

/** Single diff line with type-based styling. */
const DiffLine = ({ line, index, showLineNumber }) => {
  const style = LINE_STYLES[line.type] || LINE_STYLES.context

  return (
    <div
      style={{
        ...style,
        display: 'flex',
        padding: '0 8px',
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
      }}
    >
      {showLineNumber && (
        <span
          style={{
            minWidth: '36px',
            textAlign: 'right',
            paddingRight: '8px',
            color: 'var(--chat-text-muted, #888)',
            userSelect: 'none',
            flexShrink: 0,
          }}
        >
          {index + 1}
        </span>
      )}
      <span style={{ flex: 1 }}>{line.content || ' '}</span>
    </div>
  )
}

// ─── SimpleDiff ─────────────────────────────────────────────────────

/**
 * Before/after diff when no unified diff is available.
 * Shows all old lines as removals, then all new lines as additions.
 *
 * @param {Object} props
 * @param {string} props.oldContent
 * @param {string} props.newContent
 */
export const SimpleDiff = ({ oldContent, newContent }) => {
  if (!oldContent && !newContent) return null

  const oldLines = (oldContent || '').split('\n')
  const newLines = (newContent || '').split('\n')

  const diffLines = [
    ...oldLines.map((content) => ({ content: `-${content}`, type: 'remove' })),
    ...newLines.map((content) => ({ content: `+${content}`, type: 'add' })),
  ]

  return <DiffView diff={diffLines} />
}

export default DiffView
