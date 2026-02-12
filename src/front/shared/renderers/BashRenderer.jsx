/**
 * Shared BashRenderer — Displays bash command execution results.
 *
 * Features:
 *   - Command display with $ prefix in monospace code block
 *   - Scrollable output with expand/collapse for long output
 *   - Exit code indicator (green/red)
 *   - Status states: pending, running, complete, error
 *   - Compact mode (3-line summary)
 *
 * Accepts either explicit props or a NormalizedToolResult.
 *
 * @module shared/renderers/BashRenderer
 */
import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import ToolUseBlock, { ToolOutput, ToolError } from './ToolUseBlock'

const MAX_LINES = 8

/**
 * @param {Object} props
 * @param {import('./NormalizedToolResult').NormalizedToolResult} [props.result]
 * @param {string} [props.command]
 * @param {string} [props.description]
 * @param {string} [props.output]
 * @param {number} [props.exitCode]
 * @param {string} [props.error]
 * @param {import('./NormalizedToolResult').ToolStatus} [props.status]
 * @param {boolean} [props.compact]
 */
const BashRenderer = ({
  result,
  command,
  description,
  output,
  exitCode,
  error,
  status = 'complete',
  compact = false,
}) => {
  const [isExpanded, setIsExpanded] = useState(false)

  // Extract from result if provided
  const cmd = command ?? result?.input?.command
  const desc = description ?? result?.description ?? (cmd?.length > 60 ? cmd.slice(0, 60) + '...' : cmd)
  const out = output ?? result?.output?.content
  const exit = exitCode ?? result?.output?.exitCode
  const err = error ?? result?.output?.error
  const st = status !== 'complete' ? status : (result?.status ?? status)

  const getOutputInfo = (text) => {
    if (!text) return { lines: [], totalLines: 0, hasMore: false }
    const lines = text.split('\n')
    return { lines, totalLines: lines.length, hasMore: lines.length > MAX_LINES }
  }

  const outputInfo = getOutputInfo(out)

  // Determine status from exit code if not explicit
  const hasExitCode = typeof exit === 'number'
  const effectiveStatus = err ? 'error' : (hasExitCode && exit !== 0) ? 'error' : st
  const isStreaming = ['pending', 'running'].includes(effectiveStatus)

  return (
    <ToolUseBlock
      toolName="Bash"
      description={desc}
      status={effectiveStatus}
      collapsible={out && out.length > 300}
      defaultExpanded={true}
    >
      {/* Command display */}
      {cmd && !compact && (
        <div style={{ marginBottom: 'var(--space-2, 8px)' }}>
          <code
            style={{
              display: 'block',
              fontFamily: 'var(--font-mono, monospace)',
              fontSize: 'var(--text-sm, 13px)',
              color: 'var(--chat-text, var(--color-text-primary, #e0e0e0))',
              backgroundColor: 'var(--chat-command-bg, var(--chat-input-bg, var(--color-bg-tertiary, #1a1a2e)))',
              padding: 'var(--space-3, 12px) var(--space-4, 16px)',
              borderRadius: 'var(--radius-md, 8px)',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              border: '1px solid var(--chat-border, var(--color-border, #333))',
              lineHeight: '1.5',
            }}
          >
            <span style={{ color: 'var(--chat-text-tertiary, var(--color-text-secondary, #888))', marginRight: '8px', userSelect: 'none' }}>$</span>
            {cmd}
          </code>
        </div>
      )}

      {/* Error display */}
      {err && <ToolError message={err} />}

      {/* Compact output (3-line summary) */}
      {out && !err && compact && (
        <pre
          style={{
            margin: 0,
            fontFamily: 'var(--font-mono, monospace)',
            fontSize: 'var(--text-sm, 13px)',
            color: 'var(--chat-text-muted, var(--color-text-secondary, #888))',
            lineHeight: '1.4',
          }}
        >
          {(() => {
            const rawLines = out.split('\n')
            const maxLines = 3
            const shown = rawLines.slice(0, maxLines)
            const formatted = shown.map((line, idx) =>
              `${idx === 0 ? '\u2514' : ' '} ${line}`.trimEnd(),
            )
            if (rawLines.length > maxLines) {
              formatted.push(`  ... +${rawLines.length - maxLines} lines`)
            }
            return formatted.join('\n')
          })()}
          {isStreaming && <span aria-hidden="true">{'\u258C'}</span>}
        </pre>
      )}

      {/* Full output display */}
      {out && !err && !compact && (
        <ToolOutput style={{ maxHeight: isExpanded ? '500px' : '220px' }}>
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word', lineHeight: '1.4' }}>
            {isExpanded ? out : outputInfo.lines.slice(0, MAX_LINES).join('\n')}
          </pre>
          {outputInfo.hasMore && (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                marginTop: 'var(--space-2, 8px)',
                padding: '6px 12px',
                background: 'var(--color-bg-active, rgba(255,255,255,0.1))',
                border: '1px solid var(--chat-border, var(--color-border, #333))',
                borderRadius: 'var(--radius-md, 8px)',
                color: 'var(--chat-text-muted, var(--color-text-secondary, #888))',
                fontSize: '12px',
                fontFamily: 'var(--font-mono, monospace)',
                cursor: 'pointer',
              }}
            >
              {isExpanded ? (
                <><ChevronDown size={14} /><span>Show less</span></>
              ) : (
                <><ChevronRight size={14} /><span>+{outputInfo.totalLines - MAX_LINES} more lines</span></>
              )}
            </button>
          )}
        </ToolOutput>
      )}

      {/* Exit code indicator */}
      {exit !== undefined && exit !== 0 && !err && (
        <div style={{ marginTop: 'var(--space-1, 4px)', fontSize: '12px', color: 'var(--color-error, #f44)' }}>
          Exit code: {exit}
        </div>
      )}

      {/* Pending state */}
      {effectiveStatus === 'pending' && !out && (
        <div style={{ color: 'var(--chat-text-muted, #888)', fontSize: 'var(--text-sm, 13px)', fontStyle: 'italic' }}>
          Waiting for permission...
        </div>
      )}

      {/* Running state */}
      {effectiveStatus === 'running' && !out && (
        <div style={{ color: 'var(--chat-text-muted, #888)', fontSize: 'var(--text-sm, 13px)', fontStyle: 'italic' }}>
          Running command...
        </div>
      )}
    </ToolUseBlock>
  )
}

export default BashRenderer
