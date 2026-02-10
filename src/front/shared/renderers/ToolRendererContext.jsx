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

// ─── Context ────────────────────────────────────────────────────────

/**
 * @typedef {Object} ToolRendererContextValue
 * @property {(result: import('./NormalizedToolResult').NormalizedToolResult) => JSX.Element|null} renderTool
 *   Render a normalized tool result into JSX.
 */

const ToolRendererContext = createContext(/** @type {ToolRendererContextValue|null} */ (null))
ToolRendererContext.displayName = 'ToolRendererContext'

// ─── Default renderer ───────────────────────────────────────────────

/**
 * Default renderTool implementation.
 *
 * Maps toolType → shared renderer component. This is a placeholder that
 * returns a simple display until the shared renderer components are built
 * (bd-3drr.2.x). Once those exist, this function will import and dispatch
 * to them.
 *
 * @param {import('./NormalizedToolResult').NormalizedToolResult} result
 * @returns {JSX.Element|null}
 */
function defaultRenderTool(result) {
  if (!result) return null

  // Temporary fallback until shared renderer components are built.
  // Each bd-3drr.2.x task will register its renderer here.
  return (
    <div
      className="shared-tool-fallback"
      style={{
        padding: '8px 12px',
        borderRadius: '6px',
        backgroundColor: 'var(--chat-input-bg, #1a1a2e)',
        border: '1px solid var(--chat-border, #333)',
        fontFamily: 'var(--font-mono)',
        fontSize: 'var(--text-sm)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
        <span
          style={{
            color: result.status === 'error'
              ? 'var(--color-error, #f44)'
              : result.status === 'complete'
                ? 'var(--color-success, #4f4)'
                : 'var(--color-text-secondary, #888)',
          }}
        >
          ●
        </span>
        <strong>{result.toolName}</strong>
        {result.description && (
          <span style={{ color: 'var(--chat-text-muted, #888)' }}>{result.description}</span>
        )}
      </div>
      {result.output?.content && (
        <pre style={{ margin: 0, whiteSpace: 'pre-wrap', maxHeight: '200px', overflow: 'auto' }}>
          {result.output.content}
        </pre>
      )}
      {result.output?.error && (
        <div style={{ color: 'var(--color-error, #f44)' }}>{result.output.error}</div>
      )}
    </div>
  )
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
