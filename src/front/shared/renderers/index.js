/**
 * Shared Tool Renderers — barrel export.
 *
 * Usage:
 *   import { createToolResult, classifyTool, useToolRenderer } from '@/shared/renderers'
 *
 * @module shared/renderers
 */

// Data contract + helpers
export {
  classifyTool,
  normalizeStatus,
  createToolResult,
  parseDiffLines,
} from './NormalizedToolResult'

// React context + components
export {
  ToolRendererProvider,
  useToolRenderer,
  ToolResultView,
  default as ToolRendererContext,
} from './ToolRendererContext'

// Shared base components
export {
  default as ToolUseBlock,
  ToolOutput,
  ToolCommand,
  ToolError,
  InlineCode,
} from './ToolUseBlock'

// Diff rendering
export {
  default as DiffView,
  SimpleDiff,
} from './DiffView'

// Tool-specific renderers
export { default as BashRenderer } from './BashRenderer'
export { default as ReadRenderer } from './ReadRenderer'
export { default as WriteRenderer } from './WriteRenderer'
export { default as EditRenderer } from './EditRenderer'
export { default as GrepRenderer } from './GrepRenderer'
export { default as GlobRenderer } from './GlobRenderer'
export { default as GenericRenderer } from './GenericRenderer'
