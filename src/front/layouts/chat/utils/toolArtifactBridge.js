/**
 * toolArtifactBridge — Maps tool call results to Surface artifacts.
 *
 * Given a tool name, its arguments, and its result, determines whether
 * the tool result should open an artifact in the Surface and, if so,
 * produces a SurfaceArtifact descriptor ready for useArtifactController.open().
 *
 * Artifact-producing tools:
 *   write_file  -> kind: 'code',     canonicalKey: args.path
 *   edit_file   -> kind: 'code',     canonicalKey: args.path
 *   open_file   -> kind: 'code',     canonicalKey: args.path
 *   open_review -> kind: 'review',   canonicalKey: 'review:' + args.path
 *   open_chart  -> kind: 'chart',    canonicalKey: 'chart:' + args.id
 *   open_table  -> kind: 'table',    canonicalKey: 'table:' + args.id
 *   open_panel  -> kind: args.type,  canonicalKey: derived from args
 *
 * Non-artifact tools (read_file, bash, search_files, etc.) return shouldOpen: false.
 *
 * Usage:
 *   import { bridgeToolResultToArtifact } from '../shell/toolArtifactBridge'
 *   const { shouldOpen, artifact } = bridgeToolResultToArtifact(toolName, args, result, activeSessionId)
 *   if (shouldOpen && artifact) {
 *     artifactController.open(artifact)
 *   }
 */

// ---------------------------------------------------------------------------
// Tool -> artifact kind mapping
// ---------------------------------------------------------------------------

/**
 * Map of tool names to artifact configuration.
 * Each entry specifies how to derive the artifact kind and canonical key.
 */
const TOOL_ARTIFACT_MAP = {
  read_file: { kind: 'code', keyFn: (args) => args?.path },
  write_file: { kind: 'code', keyFn: (args) => args?.path },
  edit_file: { kind: 'code', keyFn: (args) => args?.path },
  open_file: { kind: 'code', keyFn: (args) => args?.path },
  open_review: { kind: 'review', keyFn: (args) => `review:${args?.path || 'unknown'}` },
  open_chart: { kind: 'chart', keyFn: (args) => `chart:${args?.id || args?.title || 'unknown'}` },
  open_table: { kind: 'table', keyFn: (args) => `table:${args?.id || args?.title || 'unknown'}` },
}

/**
 * Extract the filename from a file path.
 * @param {string} filePath
 * @returns {string}
 */
function basename(filePath) {
  if (!filePath) return 'untitled'
  const parts = filePath.split('/')
  return parts[parts.length - 1] || 'untitled'
}

/**
 * Generate a unique artifact ID.
 * @returns {string}
 */
function generateArtifactId() {
  return `art-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

/**
 * Derive a human-readable title for an artifact.
 */
function deriveTitle(kind, args) {
  if (args?.title) return args.title
  if (args?.path) return basename(args.path)
  if (args?.id) return String(args.id)
  return kind || 'untitled'
}

/**
 * Create a SurfaceArtifact from tool arguments.
 *
 * @param {string} kind - Artifact kind (code, review, chart, table, etc.)
 * @param {string} canonicalKey - Dedup key
 * @param {object} args - Tool input arguments
 * @param {string} activeSessionId - Current session for provenance
 * @param {string} [messageId] - Originating message ID for provenance
 * @returns {object} SurfaceArtifact
 */
function createArtifact(kind, canonicalKey, args, activeSessionId, messageId) {
  return {
    id: generateArtifactId(),
    canonicalKey,
    kind,
    title: deriveTitle(kind, args),
    source: 'tool',
    sourceSessionId: activeSessionId || null,
    sourceMessageId: messageId || null,
    rendererKey: kind,
    params: { ...(args || {}) },
    status: 'ready',
    dirty: false,
    createdAt: Date.now(),
  }
}

/**
 * Bridge a tool call result to a Surface artifact descriptor.
 *
 * @param {string} toolName - The name of the tool that was called
 * @param {object} args - The tool's input arguments
 * @param {object} result - The tool's output result
 * @param {string} activeSessionId - The current session ID
 * @param {string} [messageId] - The originating message ID (for provenance)
 * @returns {{ shouldOpen: boolean, artifact: object | null }}
 */
export function bridgeToolResultToArtifact(toolName, args, result, activeSessionId, messageId) {
  const mapping = TOOL_ARTIFACT_MAP[toolName]
  if (!mapping) {
    return { shouldOpen: false, artifact: null }
  }

  const canonicalKey = mapping.keyFn(args)
  if (!canonicalKey) {
    return { shouldOpen: false, artifact: null }
  }

  return {
    shouldOpen: true,
    artifact: createArtifact(mapping.kind, canonicalKey, args, activeSessionId, messageId),
  }
}

/**
 * Bridge an open_panel tool call to a Surface artifact.
 * This handles the generic `open_panel` tool that can open any type of panel.
 *
 * @param {object} payload - { type, params, id, title }
 * @param {string} activeSessionId - The current session ID
 * @param {string} [messageId] - The originating message ID
 * @returns {{ shouldOpen: boolean, artifact: object | null }}
 */
export function bridgeOpenPanelToArtifact(payload, activeSessionId, messageId) {
  if (!payload || typeof payload !== 'object') {
    return { shouldOpen: false, artifact: null }
  }

  const type = payload.type || payload.component || 'code'
  const params = payload.params || {}
  const canonicalKey = params.path || payload.id || `panel:${type}:${payload.title || 'unknown'}`

  const title = payload.title || params.title
  const args = title ? { ...params, title } : { ...params }

  return {
    shouldOpen: true,
    artifact: createArtifact(type, canonicalKey, args, activeSessionId, messageId),
  }
}

/**
 * Create a SurfaceArtifact from an ArtifactCard's data.
 * Used when a user clicks an artifact card in the chat timeline.
 *
 * @param {object} cardData - { title, kind, icon, id, ... }
 * @param {string} activeSessionId - The current session ID
 * @param {string} [messageId] - The originating message ID
 * @returns {object} SurfaceArtifact
 */
export function bridgeArtifactCardToArtifact(cardData, activeSessionId, messageId) {
  if (!cardData) return null

  const kind = cardData.kind || 'document'
  const canonicalKey = cardData.canonicalKey || cardData.id || `card:${kind}:${cardData.title || 'unknown'}`

  return createArtifact(kind, canonicalKey, cardData, activeSessionId, messageId)
}
