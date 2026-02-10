/**
 * Content Normalizers — barrel export.
 *
 * Each normalizer converts a provider's native tool data format
 * into NormalizedToolResult for use with shared renderers.
 *
 * @module shared/normalizers
 */

export { normalizeClaudeTool, parseGrepResults, parseGlobFiles } from './claude'
export { normalizeCompanionTool } from './companion'
export {
  normalizeInspectorToolCall,
  normalizeInspectorFileRef,
  normalizeInspectorItem,
} from './inspector'
