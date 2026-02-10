/**
 * NormalizedToolResult — Shared data contract for tool rendering.
 *
 * All chat providers (Claude, Companion, Inspector, Sandbox) produce
 * tool use/result data in different shapes. Each provider's normalizer
 * converts its native format into this shared contract so that shared
 * renderers can display tools consistently.
 *
 * Adoption is OPT-IN: providers that don't want shared renderers
 * simply don't import or normalize.
 *
 * @module shared/renderers/NormalizedToolResult
 */

// ─── Tool type classification ───────────────────────────────────────

/**
 * Recognized tool types that have specialized renderers.
 * Tools not matching these get the 'generic' fallback.
 *
 * @typedef {'bash'|'read'|'write'|'edit'|'grep'|'glob'|'generic'} ToolType
 */

/**
 * Tool execution lifecycle status.
 *
 * @typedef {'pending'|'running'|'complete'|'error'} ToolStatus
 */

// ─── Output sub-types ───────────────────────────────────────────────

/**
 * A single line in a unified diff.
 *
 * @typedef {Object} DiffLine
 * @property {string} content - Full line text (including +/- prefix)
 * @property {'add'|'remove'|'context'|'header'} type
 */

/**
 * A single match line within a grep file result.
 *
 * @typedef {Object} GrepMatchLine
 * @property {number} line - 1-based line number
 * @property {string} content - Line text
 */

/**
 * Grep results grouped by file.
 *
 * @typedef {Object} GrepFileResult
 * @property {string} file - File path
 * @property {GrepMatchLine[]} matches - Matching lines in this file
 */

// ─── Main contract ──────────────────────────────────────────────────

/**
 * The normalized representation of a tool invocation and its result.
 *
 * This is the single input type accepted by all shared renderers.
 * Provider normalizers produce this from their native data.
 *
 * @typedef {Object} NormalizedToolResult
 *
 * @property {ToolType} toolType
 *   Determines which renderer handles this result.
 *   Normalizers map provider-specific tool names → ToolType.
 *
 * @property {ToolStatus} status
 *   Execution lifecycle. 'pending' = awaiting permission,
 *   'running' = in progress, 'complete' = done, 'error' = failed.
 *
 * @property {string} toolName
 *   Display name exactly as the provider reports it (e.g. "Bash", "Read").
 *   Shared renderers show this in the ToolUseBlock header.
 *
 * @property {string} [description]
 *   Short human-readable summary shown after toolName in the header.
 *   Example: the bash command, the file path, the search pattern.
 *
 * @property {string} [subtitle]
 *   Secondary info line below the header (e.g. "Added 5 lines").
 *
 * @property {Record<string, any>} input
 *   Original tool input parameters. Provider-specific; renderers use
 *   named fields when available, ignore the rest.
 *
 * @property {ToolOutput} [output]
 *   Structured output from the tool execution. All fields are optional;
 *   renderers check for presence before using.
 */

/**
 * Structured output from a tool execution.
 *
 * @typedef {Object} ToolOutput
 *
 * @property {string} [content]
 *   Raw text output (bash stdout, file content, etc.).
 *
 * @property {string|string[]} [diff]
 *   Unified diff. String is split on \n; string[] is used as-is.
 *   For EditToolRenderer: lines prefixed with +/-/@@.
 *
 * @property {number} [linesAdded]
 *   Number of lines added (for edit diffs).
 *
 * @property {number} [linesRemoved]
 *   Number of lines removed (for edit diffs).
 *
 * @property {string} [oldContent]
 *   Previous file content (for simple before/after diffs).
 *
 * @property {string} [newContent]
 *   New file content (for simple before/after diffs).
 *
 * @property {GrepFileResult[]} [searchResults]
 *   Grep results grouped by file.
 *
 * @property {number} [matchCount]
 *   Total number of search matches across all files.
 *
 * @property {string[]} [files]
 *   Glob file list.
 *
 * @property {number} [exitCode]
 *   Bash command exit code (0 = success).
 *
 * @property {string} [error]
 *   Error message from failed execution.
 *
 * @property {number} [lineCount]
 *   Number of lines read/written.
 *
 * @property {boolean} [truncated]
 *   Whether the output was truncated.
 */

// ─── Helpers ────────────────────────────────────────────────────────

/**
 * Map a raw tool name string → canonical ToolType.
 *
 * Each provider may use different casing or naming for the same tool.
 * This function normalizes them all to the enum values used by renderers.
 *
 * @param {string} name - Raw tool name from the provider
 * @returns {ToolType}
 */
export function classifyTool(name) {
  if (!name) return 'generic'
  const lower = name.toLowerCase()

  if (lower === 'bash') return 'bash'
  if (lower === 'read') return 'read'
  if (lower === 'write') return 'write'
  if (lower === 'edit') return 'edit'
  if (lower === 'grep') return 'grep'
  if (lower === 'glob') return 'glob'

  return 'generic'
}

/**
 * Map a raw provider status → canonical ToolStatus.
 *
 * Providers use different status strings:
 *   Claude:     pending, running, streaming, complete, error
 *   Sandbox:    in_progress, completed, failed
 *   Inspector:  in_progress, completed, failed
 *   Companion:  (inferred from is_error boolean)
 *
 * @param {string} rawStatus - Provider-specific status string
 * @param {Object} [opts]
 * @param {boolean} [opts.isError] - Force error status
 * @returns {ToolStatus}
 */
export function normalizeStatus(rawStatus, opts = {}) {
  if (opts.isError) return 'error'
  if (!rawStatus) return 'complete'

  const lower = rawStatus.toLowerCase()

  if (lower === 'pending') return 'pending'
  if (lower === 'running' || lower === 'streaming' || lower === 'in_progress') return 'running'
  if (lower === 'complete' || lower === 'completed') return 'complete'
  if (lower === 'error' || lower === 'failed') return 'error'

  return 'complete'
}

/**
 * Create a NormalizedToolResult with sensible defaults.
 *
 * @param {Partial<NormalizedToolResult> & {toolName: string}} fields
 * @returns {NormalizedToolResult}
 */
export function createToolResult(fields) {
  return {
    toolType: classifyTool(fields.toolName),
    status: 'complete',
    input: {},
    ...fields,
  }
}

/**
 * Parse a unified diff string into an array of classified DiffLine objects.
 *
 * @param {string} diffText - Raw unified diff text
 * @returns {DiffLine[]}
 */
export function parseDiffLines(diffText) {
  if (!diffText) return []
  const rawLines = typeof diffText === 'string' ? diffText.split('\n') : diffText
  return rawLines.map((content) => {
    let type = 'context'
    if (content.startsWith('+') && !content.startsWith('+++')) type = 'add'
    else if (content.startsWith('-') && !content.startsWith('---')) type = 'remove'
    else if (content.startsWith('@@') || content.startsWith('---') || content.startsWith('+++')) type = 'header'
    return { content, type }
  })
}
