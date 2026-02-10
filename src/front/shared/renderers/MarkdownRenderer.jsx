/**
 * Shared MarkdownRenderer — Renders markdown text with optional thinking blocks.
 *
 * Uses markdown-it for safe HTML rendering (no raw HTML injection).
 * Thinking blocks (<thinking>...</thinking>) are extracted and shown
 * as collapsible sections with a brain icon.
 *
 * CSS: requires `.markdown-content` and `.thinking-*` classes
 * (defined in chat/styles.css or can be standalone).
 *
 * @module shared/renderers/MarkdownRenderer
 */
import { useMemo, useState } from 'react'
import { ChevronRight, ChevronDown, Brain } from 'lucide-react'
import MarkdownIt from 'markdown-it'

// ─── Markdown-it instance ───────────────────────────────────────────

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  breaks: true,
})

// ─── Thinking block parser ──────────────────────────────────────────

/**
 * Parse text to separate thinking blocks from regular content.
 * @param {string} text
 * @returns {Array<{type: 'text'|'thinking', content: string}>}
 */
function parseThinkingBlocks(text) {
  if (!text) return []

  const parts = []
  const regex = /<thinking>([\s\S]*?)<\/thinking>/g
  let lastIndex = 0
  let match

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      const before = text.slice(lastIndex, match.index).trim()
      if (before) parts.push({ type: 'text', content: before })
    }
    parts.push({ type: 'thinking', content: match[1].trim() })
    lastIndex = regex.lastIndex
  }

  if (lastIndex < text.length) {
    const after = text.slice(lastIndex).trim()
    if (after) parts.push({ type: 'text', content: after })
  }

  return parts
}

// ─── ThinkingBlock ──────────────────────────────────────────────────

const ThinkingBlock = ({ content, index, expanded, onToggle }) => {
  const html = useMemo(() => md.render(content), [content])

  return (
    <div className="thinking-block">
      <button className="thinking-header" onClick={() => onToggle(index)} type="button">
        {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <Brain size={14} />
        <span>Thinking</span>
      </button>
      {expanded && (
        <div className="thinking-content markdown-content" dangerouslySetInnerHTML={{ __html: html }} />
      )}
    </div>
  )
}

// ─── MarkdownRenderer ───────────────────────────────────────────────

/**
 * Render markdown text, optionally extracting and collapsing thinking blocks.
 *
 * @param {Object} props
 * @param {string} props.text - Markdown text to render
 * @param {string} [props.className] - Additional CSS class
 * @param {boolean} [props.parseThinking=true] - Whether to extract thinking blocks
 */
const MarkdownRenderer = ({ text, className = '', parseThinking = true }) => {
  const [expandedBlocks, setExpandedBlocks] = useState({})

  const parts = useMemo(
    () => (parseThinking ? parseThinkingBlocks(text) : []),
    [text, parseThinking],
  )

  const toggleBlock = (index) => {
    setExpandedBlocks((prev) => ({ ...prev, [index]: !prev[index] }))
  }

  if (!text) return null

  // Simple case: no thinking blocks or parsing disabled
  if (!parseThinking || parts.length === 0 || (parts.length === 1 && parts[0].type === 'text')) {
    const html = md.render(text)
    return (
      <div
        className={`text-block markdown-content ${className}`}
        dangerouslySetInnerHTML={{ __html: html }}
      />
    )
  }

  // Complex case: interleaved text and thinking blocks
  let thinkingIndex = 0
  return (
    <div className={`text-block ${className}`}>
      {parts.map((part, i) => {
        if (part.type === 'thinking') {
          const idx = thinkingIndex++
          return (
            <ThinkingBlock
              key={i}
              content={part.content}
              index={idx}
              expanded={!!expandedBlocks[idx]}
              onToggle={toggleBlock}
            />
          )
        }
        const html = md.render(part.content)
        return (
          <div key={i} className="markdown-content" dangerouslySetInnerHTML={{ __html: html }} />
        )
      })}
    </div>
  )
}

export default MarkdownRenderer
