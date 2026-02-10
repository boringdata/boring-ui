/**
 * Companion content normalizer.
 *
 * Converts Companion's ContentBlock tool_use/tool_result pairs into
 * NormalizedToolResult objects for shared rendering.
 *
 * Companion ContentBlocks:
 *   { type: 'tool_use', id, name, input: Record<string, unknown> }
 *   { type: 'tool_result', content: string|unknown, is_error: boolean }
 *
 * @module shared/normalizers/companion
 */
import { classifyTool, createToolResult } from '../renderers/NormalizedToolResult'

/**
 * Normalize a Companion tool_use ContentBlock (optionally paired with its result).
 *
 * @param {Object} toolUse - Companion tool_use block
 * @param {string} toolUse.name - Tool name
 * @param {Record<string, any>} toolUse.input - Tool input
 * @param {Object} [toolResult] - Companion tool_result block (if available)
 * @param {string|any} [toolResult.content] - Result content
 * @param {boolean} [toolResult.is_error] - Whether the result is an error
 * @returns {import('../renderers/NormalizedToolResult').NormalizedToolResult}
 */
export function normalizeCompanionTool(toolUse, toolResult) {
  const input = toolUse.input || {}
  const toolType = classifyTool(toolUse.name)
  const isError = toolResult?.is_error === true
  const resultContent = typeof toolResult?.content === 'string'
    ? toolResult.content
    : toolResult?.content != null
      ? JSON.stringify(toolResult.content, null, 2)
      : ''

  const status = !toolResult ? 'running' : isError ? 'error' : 'complete'

  const base = {
    toolType,
    status,
    toolName: toolUse.name || 'Tool',
    input,
  }

  switch (toolType) {
    case 'bash':
      return createToolResult({
        ...base,
        description: input.description || input.command,
        output: {
          content: resultContent,
          error: isError ? resultContent : undefined,
        },
      })

    case 'read':
      return createToolResult({
        ...base,
        description: extractFileName(input.file_path || input.path),
        output: {
          content: resultContent,
          error: isError ? resultContent : undefined,
        },
      })

    case 'write':
      return createToolResult({
        ...base,
        description: extractFileName(input.file_path || input.path),
        output: {
          content: input.content || resultContent,
          error: isError ? resultContent : undefined,
        },
      })

    case 'edit':
      return createToolResult({
        ...base,
        description: extractFileName(input.file_path || input.path),
        output: {
          diff: input.diff || resultContent,
          oldContent: input.old_string,
          newContent: input.new_string,
          error: isError ? resultContent : undefined,
        },
      })

    case 'grep':
      return createToolResult({
        ...base,
        output: {
          content: resultContent,
          error: isError ? resultContent : undefined,
        },
      })

    case 'glob':
      return createToolResult({
        ...base,
        output: {
          files: resultContent ? resultContent.split('\n').filter(Boolean) : [],
          error: isError ? resultContent : undefined,
        },
      })

    default:
      return createToolResult({
        ...base,
        description: describeToolInput(input),
        output: {
          content: resultContent,
          error: isError ? resultContent : undefined,
        },
      })
  }
}

function extractFileName(filePath) {
  if (!filePath) return undefined
  return filePath.split('/').pop() || filePath
}

function describeToolInput(input) {
  // Pick the first string value that looks like a meaningful description
  for (const key of ['command', 'file_path', 'path', 'pattern', 'query', 'url']) {
    if (input[key] && typeof input[key] === 'string') {
      const val = input[key]
      return val.length > 60 ? val.slice(0, 60) + '...' : val
    }
  }
  return undefined
}
