/**
 * Shared GenericRenderer — Fallback for unrecognized tool types.
 *
 * Renders any NormalizedToolResult that doesn't match a specialized
 * renderer. Shows the tool name, description, and raw output.
 *
 * @module shared/renderers/GenericRenderer
 */
import ToolUseBlock, { ToolOutput, ToolError } from './ToolUseBlock'

/**
 * @param {Object} props
 * @param {import('./NormalizedToolResult').NormalizedToolResult} [props.result]
 * @param {string} [props.toolName]
 * @param {string} [props.description]
 * @param {string} [props.output]
 * @param {string} [props.error]
 * @param {import('./NormalizedToolResult').ToolStatus} [props.status]
 */
const GenericRenderer = ({
  result,
  toolName,
  description,
  output,
  error,
  status = 'complete',
}) => {
  const name = toolName ?? result?.toolName ?? 'Tool'
  const desc = description ?? result?.description
  const out = output ?? result?.output?.content
  const err = error ?? result?.output?.error
  const st = status !== 'complete' ? status : (result?.status ?? status)

  return (
    <ToolUseBlock
      toolName={name}
      description={desc}
      status={st}
      collapsible={out && out.length > 300}
      defaultExpanded={true}
    >
      {err ? (
        <ToolError message={err} />
      ) : out ? (
        <ToolOutput>
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word', lineHeight: '1.5' }}>
            {out}
          </pre>
        </ToolOutput>
      ) : st === 'running' ? (
        <div style={{ color: 'var(--chat-text-muted, #888)', fontSize: 'var(--text-sm, 13px)', fontStyle: 'italic' }}>
          Running...
        </div>
      ) : null}
    </ToolUseBlock>
  )
}

export default GenericRenderer
