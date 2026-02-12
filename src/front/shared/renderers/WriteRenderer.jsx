/**
 * Shared WriteRenderer — Displays file write operations.
 *
 * Features:
 *   - Header: "Write FILENAME" with line count subtitle
 *   - Content preview of file being written
 *   - Permission and streaming states
 *
 * @module shared/renderers/WriteRenderer
 */
import ToolUseBlock, { ToolOutput, ToolError } from './ToolUseBlock'

/**
 * @param {Object} props
 * @param {import('./NormalizedToolResult').NormalizedToolResult} [props.result]
 * @param {string} [props.filePath]
 * @param {string} [props.content]
 * @param {string} [props.error]
 * @param {import('./NormalizedToolResult').ToolStatus} [props.status]
 * @param {number} [props.lineCount]
 */
const WriteRenderer = ({
  result,
  filePath,
  content,
  error,
  status = 'complete',
  lineCount,
}) => {
  const path = filePath ?? result?.input?.file_path ?? result?.input?.path
  const text = content ?? result?.input?.content ?? result?.output?.content
  const err = error ?? result?.output?.error
  const st = status !== 'complete' ? status : (result?.status ?? status)
  const lines = lineCount ?? result?.output?.lineCount ?? (text ? text.split('\n').length : 0)

  const fileName = path?.split('/').pop() || path
  const subtitle = lines > 0 ? `${lines} line${lines !== 1 ? 's' : ''}` : null
  const isStreaming = ['pending', 'running'].includes(st)

  return (
    <ToolUseBlock
      toolName="Write"
      description={fileName}
      subtitle={subtitle}
      status={st}
      collapsible={text && text.length > 500}
      defaultExpanded={true}
    >
      {err ? (
        <ToolError message={err} />
      ) : text ? (
        <ToolOutput>
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word', lineHeight: '1.5' }}>
            {text}
          </pre>
        </ToolOutput>
      ) : st === 'pending' ? (
        <div style={{ color: 'var(--chat-text-muted, #888)', fontSize: 'var(--text-sm, 13px)', fontStyle: 'italic' }}>
          Waiting for permission...
        </div>
      ) : st === 'running' ? (
        <div style={{ color: 'var(--chat-text-muted, #888)', fontSize: 'var(--text-sm, 13px)', fontStyle: 'italic' }}>
          Writing file...
        </div>
      ) : null}
    </ToolUseBlock>
  )
}

export default WriteRenderer
