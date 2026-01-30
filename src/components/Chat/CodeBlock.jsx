import React, { useState, useRef, useCallback, useEffect, memo } from 'react'
import { Copy, ChevronDown } from 'lucide-react'
import SyntaxHighlighter from './SyntaxHighlighter'
import '../../styles/code-blocks.css'

/**
 * CodeBlock Component - Premium code display with syntax highlighting
 *
 * Features:
 * - Syntax highlighting for 50+ languages
 * - Copy-to-clipboard with visual feedback
 * - Line numbers (optional)
 * - Language badges
 * - Diff highlighting
 * - Expand/collapse for long blocks
 * - Terminal-style variants
 * - Light/dark theme support
 *
 * @param {Object} props
 * @param {string} props.code - Code content to display
 * @param {string} props.language - Programming language (js, py, jsx, etc.)
 * @param {boolean} props.showLineNumbers - Show line numbers (default: true for >5 lines)
 * @param {boolean} props.collapsible - Allow collapse/expand (default: auto for >20 lines)
 * @param {boolean} props.isDiff - Highlight as diff (default: false)
 * @param {string} props.title - Optional title/filename
 * @param {string} props.className - Additional CSS classes
 * @param {number} props.maxLines - Lines before collapse option appears (default: 20)
 * @returns {React.ReactElement}
 */
const CodeBlock = memo(
  ({
    code = '',
    language = 'plaintext',
    showLineNumbers = null,
    collapsible = null,
    isDiff = false,
    title = null,
    className = '',
    maxLines = 20,
  }) => {
    const [isExpanded, setIsExpanded] = useState(true)
    const [copied, setCopied] = useState(false)
    const [highlightError, setHighlightError] = useState(false)
    const codeRef = useRef(null)
    const copyTimeoutRef = useRef(null)

    // Auto-detect line number display
    const lineCount = code.split('\n').length
    const shouldShowLineNumbers = showLineNumbers ?? lineCount > 5
    const canCollapse = collapsible ?? lineCount > maxLines
    const displayedCode = isExpanded ? code : code.split('\n').slice(0, maxLines).join('\n')

    // Handle copy to clipboard with feedback
    const handleCopy = useCallback(async () => {
      try {
        await navigator.clipboard.writeText(code)
        setCopied(true)

        // Clear existing timeout
        if (copyTimeoutRef.current) {
          clearTimeout(copyTimeoutRef.current)
        }

        // Reset after 2 seconds
        copyTimeoutRef.current = setTimeout(() => {
          setCopied(false)
        }, 2000)
      } catch (err) {
        console.error('Failed to copy code:', err)
      }
    }, [code])

    // Cleanup timeout on unmount
    useEffect(() => {
      return () => {
        if (copyTimeoutRef.current) {
          clearTimeout(copyTimeoutRef.current)
        }
      }
    }, [])

    // Determine if this is a terminal/bash block
    const isTerminal =
      language === 'bash' ||
      language === 'sh' ||
      language === 'shell' ||
      language === 'zsh'

    const containerClasses = `
      code-block-container
      code-block-lang-${language}
      ${isDiff ? 'code-block-diff' : ''}
      ${isTerminal ? 'code-block-terminal' : ''}
      ${highlightError ? 'code-block-error' : ''}
      ${className}
    `.trim()

    return (
      <div className={containerClasses}>
        {/* Header with language badge and actions */}
        {title || language !== 'plaintext' ? (
          <div className="code-block-header">
            <div className="code-block-info">
              {title && <span className="code-block-title">{title}</span>}
              {!title && (
                <span className="code-block-badge">{getLanguageLabel(language)}</span>
              )}
            </div>

            <div className="code-block-actions">
              {canCollapse && (
                <button
                  className="code-block-action-btn code-block-expand-btn"
                  onClick={() => setIsExpanded(!isExpanded)}
                  title={isExpanded ? 'Collapse' : 'Expand'}
                  aria-label={isExpanded ? 'Collapse code' : 'Expand code'}
                >
                  <ChevronDown
                    size={16}
                    style={{
                      transform: isExpanded ? 'rotate(0deg)' : 'rotate(-90deg)',
                      transition: 'transform 200ms var(--ease-spring)',
                    }}
                  />
                </button>
              )}

              <button
                className={`code-block-action-btn code-block-copy-btn ${copied ? 'copied' : ''}`}
                onClick={handleCopy}
                title="Copy code"
                aria-label="Copy code to clipboard"
              >
                <Copy size={16} />
                <span className="copy-feedback">
                  {copied ? 'Copied!' : 'Copy'}
                </span>
              </button>
            </div>
          </div>
        ) : null}

        {/* Code content */}
        <div className="code-block-content" ref={codeRef}>
          <SyntaxHighlighter
            code={displayedCode}
            language={language}
            showLineNumbers={shouldShowLineNumbers}
            isDiff={isDiff}
            onError={(err) => {
              console.warn(`Syntax highlight error for ${language}:`, err)
              setHighlightError(true)
            }}
          />

          {/* Collapse hint */}
          {canCollapse && !isExpanded && (
            <div className="code-block-collapsed-hint">
              <span>
                {lineCount - maxLines} more lines... Click to expand
              </span>
            </div>
          )}
        </div>

        {/* Line count indicator */}
        {shouldShowLineNumbers && lineCount > 1 && (
          <div className="code-block-footer">
            <span className="code-block-line-count">
              {lineCount} {lineCount === 1 ? 'line' : 'lines'}
            </span>
          </div>
        )}
      </div>
    )
  },
)

CodeBlock.displayName = 'CodeBlock'

/**
 * Get human-readable label for language code
 * @param {string} lang - Language code
 * @returns {string} Language label
 */
function getLanguageLabel(lang) {
  const labels = {
    js: 'JavaScript',
    jsx: 'JSX',
    ts: 'TypeScript',
    tsx: 'TSX',
    py: 'Python',
    java: 'Java',
    cpp: 'C++',
    c: 'C',
    cs: 'C#',
    rb: 'Ruby',
    go: 'Go',
    rust: 'Rust',
    php: 'PHP',
    sql: 'SQL',
    bash: 'Bash',
    sh: 'Shell',
    zsh: 'Zsh',
    html: 'HTML',
    xml: 'XML',
    css: 'CSS',
    scss: 'SCSS',
    json: 'JSON',
    yaml: 'YAML',
    yml: 'YAML',
    toml: 'TOML',
    markdown: 'Markdown',
    md: 'Markdown',
    diff: 'Diff',
    patch: 'Patch',
    plaintext: 'Text',
    text: 'Text',
  }

  return labels[lang] || lang.toUpperCase()
}

export default CodeBlock
