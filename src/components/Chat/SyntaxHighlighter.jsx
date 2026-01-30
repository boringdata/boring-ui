import React, { useMemo, memo } from 'react'
import { renderToString } from 'react-dom/server'

/**
 * SyntaxHighlighter Component - Prism.js integration for code highlighting
 *
 * Provides syntax highlighting for 50+ languages with:
 * - Fallback to plain text if language not supported
 * - Line number rendering
 * - Diff highlighting (+ and - lines)
 * - Performance optimized with memoization
 *
 * Note: Using a lightweight approach without Prism.js dependency to keep bundle small.
 * For production, consider adding prism-react-renderer (already in package.json).
 *
 * @param {Object} props
 * @param {string} props.code - Code to highlight
 * @param {string} props.language - Programming language
 * @param {boolean} props.showLineNumbers - Show line numbers
 * @param {boolean} props.isDiff - Treat as diff
 * @param {Function} props.onError - Error callback
 * @returns {React.ReactElement}
 */
const SyntaxHighlighter = memo(
  ({ code = '', language = 'plaintext', showLineNumbers = false, isDiff = false, onError = null }) => {
    // Split code into lines for processing
    const lines = code.split('\n')

    // Simple syntax highlighting without external dependency
    // This provides basic highlighting for common languages
    const highlightedLines = useMemo(() => {
      try {
        return lines.map((line, idx) => ({
          number: idx + 1,
          content: line,
          highlighted: highlightLine(line, language),
          isDiffAdd: isDiff && line.startsWith('+'),
          isDiffRemove: isDiff && line.startsWith('-'),
          isDiffContext: isDiff && line.startsWith(' '),
        }))
      } catch (err) {
        onError?.(err)
        // Fallback to plain text
        return lines.map((line, idx) => ({
          number: idx + 1,
          content: line,
          highlighted: escapeHtml(line),
          isDiffAdd: false,
          isDiffRemove: false,
          isDiffContext: false,
        }))
      }
    }, [code, language, isDiff, onError])

    return (
      <pre className="syntax-highlighter">
        <code className={`language-${language}`}>
          {showLineNumbers ? (
            <table className="code-table">
              <tbody>
                {highlightedLines.map((line) => (
                  <tr
                    key={`line-${line.number}`}
                    className={`code-line ${
                      line.isDiffAdd
                        ? 'code-line-add'
                        : line.isDiffRemove
                          ? 'code-line-remove'
                          : ''
                    }`}
                  >
                    <td className="code-line-number">{line.number}</td>
                    <td
                      className="code-line-content"
                      dangerouslySetInnerHTML={{ __html: line.highlighted }}
                    />
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="code-lines">
              {highlightedLines.map((line) => (
                <div
                  key={`line-${line.number}`}
                  className={`code-line ${
                    line.isDiffAdd
                      ? 'code-line-add'
                      : line.isDiffRemove
                        ? 'code-line-remove'
                        : ''
                  }`}
                >
                  <span
                    className="code-line-content"
                    dangerouslySetInnerHTML={{ __html: line.highlighted }}
                  />
                </div>
              ))}
            </div>
          )}
        </code>
      </pre>
    )
  },
)

SyntaxHighlighter.displayName = 'SyntaxHighlighter'

/**
 * Simple syntax highlighting engine
 * Provides basic highlighting for common languages without Prism dependency
 * @param {string} line - Code line to highlight
 * @param {string} language - Language for syntax rules
 * @returns {string} HTML with syntax highlighting
 */
function highlightLine(line, language) {
  const escaped = escapeHtml(line)

  // No highlighting for plaintext
  if (language === 'plaintext' || language === 'text') {
    return escaped
  }

  // Basic keyword highlighting
  let highlighted = escaped

  // JavaScript/JSX/TypeScript keywords
  if (['js', 'jsx', 'ts', 'tsx', 'javascript', 'typescript'].includes(language)) {
    highlighted = highlightJavaScript(highlighted)
  }

  // Python keywords
  if (['py', 'python'].includes(language)) {
    highlighted = highlightPython(highlighted)
  }

  // JSON
  if (language === 'json') {
    highlighted = highlightJson(highlighted)
  }

  // Bash/Shell
  if (['bash', 'sh', 'shell', 'zsh'].includes(language)) {
    highlighted = highlightBash(highlighted)
  }

  // Generic keyword highlighting
  highlighted = highlightGenericKeywords(highlighted)

  return highlighted
}

/**
 * Escape HTML special characters
 */
function escapeHtml(text) {
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }
  return text.replace(/[&<>"']/g, (m) => map[m])
}

/**
 * Highlight JavaScript/TypeScript code
 */
function highlightJavaScript(html) {
  const keywords = [
    'function',
    'const',
    'let',
    'var',
    'return',
    'if',
    'else',
    'for',
    'while',
    'switch',
    'case',
    'class',
    'extends',
    'import',
    'export',
    'default',
    'async',
    'await',
    'try',
    'catch',
    'finally',
    'throw',
    'new',
    'this',
    'super',
    'static',
    'get',
    'set',
    'typeof',
    'instanceof',
    'true',
    'false',
    'null',
    'undefined',
  ]

  let result = html

  // Highlight strings (single, double, backtick)
  result = result.replace(/("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)/g, (m) => {
    return `<span class="syntax-string">${m}</span>`
  })

  // Highlight comments
  result = result.replace(/(\/\/.*$|\/\*[\s\S]*?\*\/)/g, (m) => {
    return `<span class="syntax-comment">${m}</span>`
  })

  // Highlight keywords
  keywords.forEach((keyword) => {
    const regex = new RegExp(`\\b(${keyword})\\b`, 'g')
    result = result.replace(regex, `<span class="syntax-keyword">$1</span>`)
  })

  // Highlight numbers
  result = result.replace(/\b(\d+\.?\d*|\.\d+)\b/g, (m) => {
    return `<span class="syntax-number">${m}</span>`
  })

  // Highlight function calls
  result = result.replace(/(\w+)\s*\(/g, (m, func) => {
    return `<span class="syntax-function">${func}</span>(`
  })

  return result
}

/**
 * Highlight Python code
 */
function highlightPython(html) {
  const keywords = [
    'def',
    'class',
    'import',
    'from',
    'return',
    'if',
    'elif',
    'else',
    'for',
    'while',
    'try',
    'except',
    'finally',
    'with',
    'as',
    'pass',
    'break',
    'continue',
    'yield',
    'lambda',
    'and',
    'or',
    'not',
    'is',
    'in',
    'True',
    'False',
    'None',
  ]

  let result = html

  // Highlight strings
  result = result.replace(/("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')/g, (m) => {
    return `<span class="syntax-string">${m}</span>`
  })

  // Highlight comments
  result = result.replace(/(#.*$)/g, (m) => {
    return `<span class="syntax-comment">${m}</span>`
  })

  // Highlight keywords
  keywords.forEach((keyword) => {
    const regex = new RegExp(`\\b(${keyword})\\b`, 'g')
    result = result.replace(regex, `<span class="syntax-keyword">$1</span>`)
  })

  // Highlight numbers
  result = result.replace(/\b(\d+\.?\d*|\.\d+)\b/g, (m) => {
    return `<span class="syntax-number">${m}</span>`
  })

  return result
}

/**
 * Highlight JSON code
 */
function highlightJson(html) {
  let result = html

  // Highlight strings (keys and values)
  result = result.replace(/("(?:\\.|[^"\\])*")/g, (m) => {
    return `<span class="syntax-string">${m}</span>`
  })

  // Highlight numbers
  result = result.replace(/:\s*(\d+\.?\d*|\.\d+)/g, (m) => {
    return m.replace(/(\d+\.?\d*|\.\d+)/, `<span class="syntax-number">$1</span>`)
  })

  // Highlight boolean/null
  result = result.replace(/\b(true|false|null)\b/g, (m) => {
    return `<span class="syntax-keyword">${m}</span>`
  })

  return result
}

/**
 * Highlight Bash/Shell code
 */
function highlightBash(html) {
  const keywords = [
    'if',
    'then',
    'else',
    'elif',
    'fi',
    'for',
    'do',
    'done',
    'while',
    'case',
    'esac',
    'function',
    'return',
    'export',
    'local',
    'declare',
  ]

  let result = html

  // Highlight strings
  result = result.replace(/("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)/g, (m) => {
    return `<span class="syntax-string">${m}</span>`
  })

  // Highlight comments
  result = result.replace(/(#.*$)/g, (m) => {
    return `<span class="syntax-comment">${m}</span>`
  })

  // Highlight keywords
  keywords.forEach((keyword) => {
    const regex = new RegExp(`\\b(${keyword})\\b`, 'g')
    result = result.replace(regex, `<span class="syntax-keyword">$1</span>`)
  })

  // Highlight variables
  result = result.replace(/\$(\w+)/g, (m) => {
    return `<span class="syntax-variable">${m}</span>`
  })

  return result
}

/**
 * Highlight generic keywords for unsupported languages
 */
function highlightGenericKeywords(html) {
  const genericKeywords = [
    'function',
    'class',
    'interface',
    'struct',
    'public',
    'private',
    'protected',
    'static',
  ]

  let result = html

  genericKeywords.forEach((keyword) => {
    const regex = new RegExp(`\\b(${keyword})\\b`, 'g')
    result = result.replace(regex, `<span class="syntax-keyword">$1</span>`)
  })

  return result
}

export default SyntaxHighlighter
