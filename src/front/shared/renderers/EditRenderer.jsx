/**
 * Shared EditRenderer — Displays file edit operations with diff view.
 *
 * Features:
 *   - Header: "Edit FILENAME" + "Added X lines" / "Removed X lines"
 *   - Unified diff with green additions and red deletions
 *   - Simple before/after fallback when no unified diff available
 *   - Collapsible for large diffs
 *
 * @module shared/renderers/EditRenderer
 */
import ToolUseBlock, { ToolError } from './ToolUseBlock'
import DiffView, { SimpleDiff } from './DiffView'

/**
 * @param {Object} props
 * @param {import('./NormalizedToolResult').NormalizedToolResult} [props.result]
 * @param {string} [props.filePath]
 * @param {string} [props.oldContent]
 * @param {string} [props.newContent]
 * @param {string|string[]} [props.diff]
 * @param {number} [props.linesAdded]
 * @param {number} [props.linesRemoved]
 * @param {string} [props.error]
 * @param {import('./NormalizedToolResult').ToolStatus} [props.status]
 */
const EditRenderer = ({
  result,
  filePath,
  oldContent,
  newContent,
  diff,
  linesAdded = 0,
  linesRemoved = 0,
  error,
  status = 'complete',
}) => {
  const path = filePath ?? result?.input?.file_path ?? result?.input?.path
  const d = diff ?? result?.output?.diff
  const old = oldContent ?? result?.output?.oldContent ?? result?.input?.old_string
  const nw = newContent ?? result?.output?.newContent ?? result?.input?.new_string
  const added = linesAdded || result?.output?.linesAdded || 0
  const removed = linesRemoved || result?.output?.linesRemoved || 0
  const err = error ?? result?.output?.error
  const st = status !== 'complete' ? status : (result?.status ?? status)

  const fileName = path?.split('/').pop() || path

  const changes = []
  if (added > 0) changes.push(`Added ${added} line${added > 1 ? 's' : ''}`)
  if (removed > 0) changes.push(`Removed ${removed} line${removed > 1 ? 's' : ''}`)
  const subtitle = changes.join(', ')

  // Parse diff lines for collapsibility check
  const diffLines = typeof d === 'string' ? d.split('\n') : (d || [])

  return (
    <ToolUseBlock
      toolName="Edit"
      description={fileName}
      subtitle={subtitle}
      status={st}
      collapsible={diffLines.length > 20}
      defaultExpanded={true}
    >
      {err ? (
        <ToolError message={err} />
      ) : diffLines.length > 0 ? (
        <DiffView diff={d} />
      ) : old && nw ? (
        <SimpleDiff oldContent={old} newContent={nw} />
      ) : st === 'pending' ? (
        <div style={{ color: 'var(--chat-text-muted, #888)', fontSize: 'var(--text-sm, 13px)', fontStyle: 'italic' }}>
          Waiting for permission...
        </div>
      ) : st === 'running' ? (
        <div style={{ color: 'var(--chat-text-muted, #888)', fontSize: 'var(--text-sm, 13px)', fontStyle: 'italic' }}>
          Editing file...
        </div>
      ) : null}
    </ToolUseBlock>
  )
}

export default EditRenderer
