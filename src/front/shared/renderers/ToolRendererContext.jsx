/**
 * ToolRendererContext — React context for rendering NormalizedToolResults.
 *
 * Provides a `renderTool(result)` function that maps a NormalizedToolResult
 * to the appropriate shared renderer component. Providers wrap their chat
 * UI with <ToolRendererProvider> to opt into shared rendering.
 *
 * The default renderer dispatches to the shared renderer library based
 * on toolType. Providers can override the renderer by passing a custom
 * `renderTool` function (e.g. to add provider-specific chrome).
 *
 * @module shared/renderers/ToolRendererContext
 */
import { createContext, useContext, useMemo } from 'react'
import BashRenderer from './BashRenderer'
import ReadRenderer from './ReadRenderer'
import WriteRenderer from './WriteRenderer'
import EditRenderer from './EditRenderer'
import GrepRenderer from './GrepRenderer'
import GlobRenderer from './GlobRenderer'
import GenericRenderer from './GenericRenderer'

// ─── Context ────────────────────────────────────────────────────────

/**
 * @typedef {Object} ToolRendererContextValue
 * @property {(result: import('./NormalizedToolResult').NormalizedToolResult) => JSX.Element|null} renderTool
 *   Render a normalized tool result into JSX.
 */

const ToolRendererContext = createContext(/** @type {ToolRendererContextValue|null} */ (null))
ToolRendererContext.displayName = 'ToolRendererContext'

// ─── Renderer dispatch map ──────────────────────────────────────────

/** @type {Record<import('./NormalizedToolResult').ToolType, React.ComponentType>} */
const RENDERER_MAP = {
  bash: BashRenderer,
  read: ReadRenderer,
  write: WriteRenderer,
  edit: EditRenderer,
  grep: GrepRenderer,
  glob: GlobRenderer,
  generic: GenericRenderer,
}

// ─── Default renderer ───────────────────────────────────────────────

/**
 * Default renderTool implementation.
 *
 * Maps toolType → shared renderer component via RENDERER_MAP.
 *
 * @param {import('./NormalizedToolResult').NormalizedToolResult} result
 * @returns {JSX.Element|null}
 */
function defaultRenderTool(result) {
  if (!result) return null

  const Renderer = RENDERER_MAP[result.toolType] || GenericRenderer
  return <Renderer result={result} />
}

// ─── Provider ───────────────────────────────────────────────────────

/**
 * Provider component that makes shared tool rendering available
 * to any descendant component.
 *
 * @param {Object} props
 * @param {Function} [props.renderTool] - Custom render function override
 * @param {React.ReactNode} props.children
 */
export function ToolRendererProvider({ renderTool, children }) {
  const value = useMemo(
    () => ({ renderTool: renderTool || defaultRenderTool }),
    [renderTool],
  )
  return (
    <ToolRendererContext.Provider value={value}>
      {children}
    </ToolRendererContext.Provider>
  )
}

// ─── Hook ───────────────────────────────────────────────────────────

/**
 * Access the tool renderer from any descendant component.
 *
 * Falls back to the default renderer if no provider is in the tree,
 * so providers can use shared renderers without wrapping in a provider.
 *
 * @returns {ToolRendererContextValue}
 */
export function useToolRenderer() {
  const ctx = useContext(ToolRendererContext)
  if (ctx) return ctx
  // Graceful fallback: return default renderer even without provider
  return { renderTool: defaultRenderTool }
}

// ─── Convenience component ──────────────────────────────────────────

/**
 * Render a single NormalizedToolResult using the context's renderer.
 *
 * <ToolResultView result={normalizedResult} />
 *
 * @param {Object} props
 * @param {import('./NormalizedToolResult').NormalizedToolResult} props.result
 */
export function ToolResultView({ result }) {
  const { renderTool } = useToolRenderer()
  return renderTool(result)
}

export default ToolRendererContext
