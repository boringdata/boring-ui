/**
 * Shared ReadRenderer — Displays file read operations.
 *
 * Features:
 *   - Header: "Read FILENAME" with line count
 *   - Scrollable content with truncation indicator
 *   - Collapsible for large files
 *   - Error and loading states
 *
 * @module shared/renderers/ReadRenderer
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
 * @param {boolean} [props.truncated]
 * @param {boolean} [props.hideContent]
 */
const ReadRenderer = ({
  result,
  filePath,
  content,
  error,
  status = 'complete',
  lineCount,
  truncated = false,
  hideContent = false,
}) => {
  const path = filePath ?? result?.input?.file_path ?? result?.input?.path
  const text = content ?? result?.output?.content
  const err = error ?? result?.output?.error
  const st = status !== 'complete' ? status : (result?.status ?? status)
  const lines = lineCount ?? result?.output?.lineCount
  const isTruncated = truncated ?? result?.output?.truncated ?? false

  const fileName = path?.split('/').pop() || path

  let description = fileName
  if (lines) description = `${fileName} (${lines} lines)`
  if (isTruncated) description = `${fileName} (truncated)`

  return (
    <ToolUseBlock
      toolName="Read"
      description={description}
      status={st}
      collapsible={text && text.length > 500}
      defaultExpanded={!isTruncated}
    >
      {err ? (
        <ToolError message={err} />
      ) : text && !hideContent ? (
        <ToolOutput>
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word', lineHeight: '1.5' }}>
            {text}
          </pre>
        </ToolOutput>
      ) : hideContent && lines ? (
        <div style={{ color: 'var(--chat-text-muted, #888)', fontSize: 'var(--text-sm, 13px)' }}>
          {lines} line{lines === 1 ? '' : 's'} read
        </div>
      ) : st === 'running' ? (
        <div style={{ color: 'var(--chat-text-muted, #888)', fontSize: 'var(--text-sm, 13px)', fontStyle: 'italic' }}>
          Reading file...
        </div>
      ) : null}
    </ToolUseBlock>
  )
}

export default ReadRenderer
