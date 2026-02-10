/**
 * Shared GlobRenderer — Displays file pattern matching results.
 *
 * Features:
 *   - Header: "Glob" + pattern as inline code
 *   - File list with file type icons
 *   - Collapsible for many results
 *   - Empty state: "No files found"
 *
 * @module shared/renderers/GlobRenderer
 */
import ToolUseBlock, { ToolError, InlineCode } from './ToolUseBlock'
import { getFileIcon } from '../../utils/fileIcons'

/**
 * @param {Object} props
 * @param {import('./NormalizedToolResult').NormalizedToolResult} [props.result]
 * @param {string} [props.pattern]
 * @param {string[]} [props.files]
 * @param {string} [props.error]
 * @param {import('./NormalizedToolResult').ToolStatus} [props.status]
 */
const GlobRenderer = ({
  result,
  pattern,
  files = [],
  error,
  status = 'complete',
}) => {
  const pat = pattern ?? result?.input?.pattern
  const fileList = files.length > 0 ? files : (result?.output?.files || [])
  const err = error ?? result?.output?.error
  const st = status !== 'complete' ? status : (result?.status ?? status)

  const description = (
    <>
      pattern: <InlineCode>{pat}</InlineCode>
    </>
  )

  const fileCount = fileList.length
  const hasResults = fileCount > 0

  return (
    <ToolUseBlock
      toolName="Glob"
      description={description}
      status={st}
      collapsible={fileCount > 10}
      defaultExpanded={fileCount <= 20}
    >
      {err ? (
        <ToolError message={err} />
      ) : st === 'running' ? (
        <div style={{ color: 'var(--chat-text-muted, #888)', fontSize: 'var(--text-sm, 13px)', fontStyle: 'italic' }}>
          Searching files...
        </div>
      ) : hasResults ? (
        <FileList files={fileList} />
      ) : (
        <div style={{ color: 'var(--chat-text-muted, #888)', fontSize: 'var(--text-sm, 13px)' }}>
          No files found
        </div>
      )}
    </ToolUseBlock>
  )
}

/** Renders list of files with icons. */
const FileList = ({ files }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
    {files.map((file, i) => (
      <div
        key={i}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          fontSize: 'var(--text-sm, 13px)',
          fontFamily: 'var(--font-mono, monospace)',
          color: 'var(--chat-text, var(--color-text-primary, #e0e0e0))',
          padding: '2px 0',
        }}
      >
        <span style={{ color: 'var(--chat-text-muted, #888)', fontSize: '12px' }}>
          {getFileIcon(file, 12)}
        </span>
        <span>{file}</span>
      </div>
    ))}
  </div>
)

export default GlobRenderer
