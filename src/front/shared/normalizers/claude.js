/**
 * Claude content normalizer.
 *
 * Converts the Claude WebSocket stream's tool_use parts (as built by
 * ClaudeStreamChat) into NormalizedToolResult objects that the shared
 * renderers can display.
 *
 * Claude tool_use parts have this shape:
 *   { type: 'tool_use', id, name, input, output?, error?, status?, lineCount? }
 *
 * @module shared/normalizers/claude
 */
import { classifyTool, normalizeStatus, createToolResult } from '../renderers/NormalizedToolResult'

// ─── Output parsers (ported from ClaudeStreamChat) ──────────────────

/**
 * Parse grep-style output into structured results.
 * Each line: "filepath:linenum:content"
 *
 * @param {string} output
 * @returns {import('../renderers/NormalizedToolResult').GrepFileResult[]}
 */
export function parseGrepResults(output) {
  if (!output) return []
  return output
    .split('\n')
    .filter(Boolean)
    .map((line) => {
      const match = line.match(/^(.*?):(\d+):(.*)$/)
      if (!match) return { file: 'output', matches: [{ line: 1, content: line }] }
      return {
        file: match[1],
        matches: [{ line: Number(match[2]), content: match[3] }],
      }
    })
}

/**
 * Parse glob output into file list.
 * @param {string} output
 * @returns {string[]}
 */
export function parseGlobFiles(output) {
  if (!output) return []
  return output.split('\n').map((l) => l.trim()).filter(Boolean)
}

// ─── Main normalizer ────────────────────────────────────────────────

/**
 * Normalize a Claude tool_use part into a NormalizedToolResult.
 *
 * @param {Object} part - Claude tool_use part from WebSocket stream
 * @param {string} part.name - Tool name (Bash, Read, Write, Edit, Grep, Glob)
 * @param {Record<string, any>} part.input - Tool input parameters
 * @param {string} [part.output] - Tool output text
 * @param {string} [part.error] - Error message
 * @param {string} [part.status] - Lifecycle status
 * @param {number} [part.lineCount] - Lines read/written
 * @returns {import('../renderers/NormalizedToolResult').NormalizedToolResult}
 */
export function normalizeClaudeTool(part) {
  const input = part.input || {}
  const output = part.output || ''
  const toolType = classifyTool(part.name)
  const status = normalizeStatus(part.status, { isError: !!part.error })

  const base = {
    toolType,
    status,
    toolName: part.name || 'Tool',
    input,
  }

  switch (toolType) {
    case 'bash':
      return createToolResult({
        ...base,
        description: input.description || (input.command?.length > 60 ? input.command.slice(0, 60) + '...' : input.command),
        output: {
          content: output,
          exitCode: part.exitCode,
          error: part.error,
        },
      })

    case 'read':
      return createToolResult({
        ...base,
        description: extractFileName(input.path || input.file_path),
        output: {
          lineCount: part.lineCount,
        },
      })

    case 'write':
      return createToolResult({
        ...base,
        description: extractFileName(input.path || input.file_path),
        output: {
          content: input.content || output,
          error: part.error,
        },
      })

    case 'edit':
      return createToolResult({
        ...base,
        description: extractFileName(input.path || input.file_path),
        output: {
          diff: input.diff || output,
          error: part.error,
        },
      })

    case 'grep':
      return createToolResult({
        ...base,
        output: {
          searchResults: parseGrepResults(output),
        },
      })

    case 'glob':
      return createToolResult({
        ...base,
        output: {
          files: parseGlobFiles(output),
        },
      })

    default:
      return createToolResult({
        ...base,
        output: {
          content: output,
          error: part.error,
        },
      })
  }
}

/** Extract filename from path for display. */
function extractFileName(filePath) {
  if (!filePath) return undefined
  return filePath.split('/').pop() || filePath
}
