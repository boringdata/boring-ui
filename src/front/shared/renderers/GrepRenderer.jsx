/**
 * Shared GrepRenderer — Displays code search results.
 *
 * Features:
 *   - Header: "Grep" + search pattern as inline code
 *   - Results grouped by file path (accent-colored)
 *   - Line numbers + content with pattern match highlighting
 *   - Match count summary
 *   - Collapsible for many results
 *
 * @module shared/renderers/GrepRenderer
 */
import ToolUseBlock, { ToolError, InlineCode } from './ToolUseBlock'

const escapeRegex = (str) => str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

/**
 * @param {Object} props
 * @param {import('./NormalizedToolResult').NormalizedToolResult} [props.result]
 * @param {string} [props.pattern]
 * @param {string} [props.path]
 * @param {import('./NormalizedToolResult').GrepFileResult[]} [props.results]
 * @param {number} [props.matchCount]
 * @param {string} [props.error]
 * @param {import('./NormalizedToolResult').ToolStatus} [props.status]
 */
const GrepRenderer = ({
  result,
  pattern,
  path,
  results = [],
  matchCount,
  error,
  status = 'complete',
}) => {
  const pat = pattern ?? result?.input?.pattern
  const searchPath = path ?? result?.input?.path
  const items = results.length > 0 ? results : (result?.output?.searchResults || [])
  const matches = matchCount ?? result?.output?.matchCount
  const err = error ?? result?.output?.error
  const st = status !== 'complete' ? status : (result?.status ?? status)

  const description = (
    <>
      <InlineCode>{pat}</InlineCode>
      {searchPath && (
        <span style={{ marginLeft: '6px', color: 'var(--chat-text-muted, #888)' }}>
          in {searchPath}
        </span>
      )}
    </>
  )

  const hasResults = items.length > 0
  const totalMatches = matches || items.reduce((sum, r) => sum + (r.matches?.length || 1), 0)

  return (
    <ToolUseBlock
      toolName="Grep"
      description={description}
      status={st}
      collapsible={items.length > 5}
      defaultExpanded={items.length <= 10}
    >
      {err ? (
        <ToolError message={err} />
      ) : st === 'running' ? (
        <div style={{ color: 'var(--chat-text-muted, #888)', fontSize: 'var(--text-sm, 13px)', fontStyle: 'italic' }}>
          Searching...
        </div>
      ) : hasResults ? (
        <SearchResults results={items} pattern={pat} />
      ) : (
        <div style={{ color: 'var(--chat-text-muted, #888)', fontSize: 'var(--text-sm, 13px)' }}>
          No matches found
        </div>
      )}

      {hasResults && totalMatches > 0 && (
        <div style={{ marginTop: 'var(--space-1, 4px)', fontSize: '12px', color: 'var(--chat-text-muted, #888)' }}>
          {totalMatches} match{totalMatches !== 1 ? 'es' : ''} in {items.length} file{items.length !== 1 ? 's' : ''}
        </div>
      )}
    </ToolUseBlock>
  )
}

/** Renders grouped search results by file. */
const SearchResults = ({ results, pattern }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2, 8px)' }}>
    {results.map((result, i) => (
      <FileResult key={i} result={result} pattern={pattern} />
    ))}
  </div>
)

/** Single file with its matching lines. */
const FileResult = ({ result, pattern }) => {
  const { file, matches = [] } = result
  const matchList = Array.isArray(matches) ? matches : [{ line: 1, content: matches }]

  return (
    <div>
      <div
        style={{
          fontSize: '12px',
          color: 'var(--chat-accent, var(--color-accent, #7c8cf5))',
          fontFamily: 'var(--font-mono, monospace)',
          marginBottom: '4px',
        }}
      >
        {file}
      </div>
      <div
        style={{
          backgroundColor: 'var(--chat-input-bg, var(--color-bg-tertiary, #1a1a2e))',
          borderRadius: 'var(--radius-sm, 4px)',
          overflow: 'hidden',
        }}
      >
        {matchList.map((match, i) => (
          <div
            key={i}
            style={{
              display: 'flex',
              fontSize: 'var(--text-sm, 13px)',
              fontFamily: 'var(--font-mono, monospace)',
              lineHeight: '1.5',
            }}
          >
            <span
              style={{
                minWidth: '40px',
                padding: '0 8px',
                color: 'var(--chat-text-muted, #888)',
                backgroundColor: 'var(--color-bg-active, rgba(255,255,255,0.05))',
                textAlign: 'right',
                flexShrink: 0,
              }}
            >
              {match.line || i + 1}
            </span>
            <span
              style={{
                padding: '0 8px',
                color: 'var(--chat-text, var(--color-text-primary, #e0e0e0))',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                flex: 1,
              }}
            >
              <HighlightedContent content={match.content || match} pattern={pattern} />
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

/** Highlights pattern matches in content. */
const HighlightedContent = ({ content, pattern }) => {
  if (!pattern || !content) return content

  try {
    const regex = new RegExp(`(${escapeRegex(pattern)})`, 'gi')
    const parts = content.split(regex)

    return parts.map((part, i) => {
      const isMatch = part.toLowerCase() === pattern.toLowerCase()
      return isMatch ? (
        <mark
          key={i}
          style={{
            backgroundColor: 'var(--color-highlight, rgba(255, 213, 0, 0.25))',
            color: 'var(--chat-code-inline, var(--color-accent, #7c8cf5))',
            borderRadius: '2px',
          }}
        >
          {part}
        </mark>
      ) : (
        part
      )
    })
  } catch {
    return content
  }
}

export default GrepRenderer
