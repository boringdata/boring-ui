/**
 * Inspector content normalizer.
 *
 * Converts Inspector/Sandbox-agent ContentPart tool_call/tool_result
 * into NormalizedToolResult objects for shared rendering.
 *
 * Inspector ContentParts:
 *   { type: 'tool_call', name, arguments: string, call_id }
 *   { type: 'tool_result', call_id, output: string }
 *   { type: 'file_ref', path, action, diff? }
 *
 * @module shared/normalizers/inspector
 */
import { classifyTool, createToolResult } from '../renderers/NormalizedToolResult'

/**
 * Normalize an Inspector tool_call ContentPart (optionally paired with its result).
 *
 * @param {Object} toolCall - Inspector tool_call part
 * @param {string} toolCall.name - Tool name
 * @param {string} toolCall.arguments - JSON-encoded arguments string
 * @param {string} toolCall.call_id - Call identifier
 * @param {Object} [toolResultPart] - Inspector tool_result part
 * @param {string} [toolResultPart.output] - Result output
 * @returns {import('../renderers/NormalizedToolResult').NormalizedToolResult}
 */
export function normalizeInspectorToolCall(toolCall, toolResultPart) {
  let input = {}
  try {
    input = toolCall.arguments ? JSON.parse(toolCall.arguments) : {}
  } catch {
    input = { raw: toolCall.arguments }
  }

  const toolType = classifyTool(toolCall.name)
  const output = toolResultPart?.output || ''
  const status = !toolResultPart ? 'running' : 'complete'

  return createToolResult({
    toolType,
    status,
    toolName: toolCall.name || 'Tool',
    description: extractDescription(toolType, input),
    input,
    output: {
      content: output || undefined,
    },
  })
}

/**
 * Normalize an Inspector file_ref ContentPart into a NormalizedToolResult.
 *
 * file_ref parts represent file operations (read, write, edit) with
 * optional diff content.
 *
 * @param {Object} fileRef
 * @param {string} fileRef.path - File path
 * @param {string} fileRef.action - Action type (read, write, edit, create, delete)
 * @param {string} [fileRef.diff] - Diff content if available
 * @returns {import('../renderers/NormalizedToolResult').NormalizedToolResult}
 */
export function normalizeInspectorFileRef(fileRef) {
  const action = (fileRef.action || '').toLowerCase()
  let toolType = 'generic'
  let toolName = fileRef.action || 'File'

  if (action === 'read') { toolType = 'read'; toolName = 'Read' }
  else if (action === 'write' || action === 'create') { toolType = 'write'; toolName = 'Write' }
  else if (action === 'edit' || action === 'modify') { toolType = 'edit'; toolName = 'Edit' }

  const result = createToolResult({
    toolType,
    status: 'complete',
    toolName,
    description: extractFileName(fileRef.path),
    input: { file_path: fileRef.path },
    output: {},
  })

  if (fileRef.diff && toolType === 'edit') {
    result.output.diff = fileRef.diff
  } else if (fileRef.diff) {
    result.output.content = fileRef.diff
  }

  return result
}

/**
 * Normalize a sandbox-agent UniversalItem tool into a NormalizedToolResult.
 *
 * UniversalItem:
 *   { item_id, kind: 'tool_call'|'tool_result', status, content: ContentPart[] }
 *
 * @param {Object} item - Sandbox-agent UniversalItem
 * @returns {import('../renderers/NormalizedToolResult').NormalizedToolResult|null}
 */
export function normalizeInspectorItem(item) {
  if (!item || !item.content || item.content.length === 0) return null

  const toolCallPart = item.content.find((c) => c.type === 'tool_call')
  const toolResultPart = item.content.find((c) => c.type === 'tool_result')

  if (toolCallPart) {
    return normalizeInspectorToolCall(toolCallPart, toolResultPart)
  }

  // tool_result without matching tool_call
  if (toolResultPart) {
    return createToolResult({
      toolType: 'generic',
      status: 'complete',
      toolName: 'Result',
      input: {},
      output: { content: toolResultPart.output },
    })
  }

  return null
}

function extractFileName(filePath) {
  if (!filePath) return undefined
  return filePath.split('/').pop() || filePath
}

function extractDescription(toolType, input) {
  switch (toolType) {
    case 'bash':
      return input.command
    case 'read':
    case 'write':
    case 'edit':
      return extractFileName(input.file_path || input.path)
    case 'grep':
      return input.pattern || input.query
    case 'glob':
      return input.pattern
    default:
      return undefined
  }
}
