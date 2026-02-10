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
