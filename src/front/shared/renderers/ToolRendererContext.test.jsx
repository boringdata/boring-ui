/**
 * Tests for ToolRendererContext.
 */
import { describe, it, expect, vi } from 'vitest'
import { renderHook } from '@testing-library/react'
import { render, screen } from '@testing-library/react'
import {
  ToolRendererProvider,
  useToolRenderer,
  ToolResultView,
} from './ToolRendererContext'

function createResult(overrides = {}) {
  return {
    toolType: 'bash',
    status: 'complete',
    toolName: 'Bash',
    input: { command: 'ls' },
    output: { content: 'file.txt' },
    ...overrides,
  }
}

describe('useToolRenderer', () => {
  it('returns default renderTool without a provider', () => {
    const { result } = renderHook(() => useToolRenderer())
    expect(result.current.renderTool).toBeTypeOf('function')
  })

  it('default renderTool renders a fallback for a result', () => {
    const { result } = renderHook(() => useToolRenderer())
    const jsx = result.current.renderTool(createResult())
    expect(jsx).not.toBeNull()
  })

  it('default renderTool returns null for null result', () => {
    const { result } = renderHook(() => useToolRenderer())
    expect(result.current.renderTool(null)).toBeNull()
  })
})

describe('ToolRendererProvider', () => {
  it('provides custom renderTool to descendants', () => {
    const customRender = vi.fn(() => <span>custom</span>)

    const wrapper = ({ children }) => (
      <ToolRendererProvider renderTool={customRender}>
        {children}
      </ToolRendererProvider>
    )

    const { result } = renderHook(() => useToolRenderer(), { wrapper })

    const toolResult = createResult()
    result.current.renderTool(toolResult)
    expect(customRender).toHaveBeenCalledWith(toolResult)
  })

  it('falls back to default when renderTool prop is not provided', () => {
    const wrapper = ({ children }) => (
      <ToolRendererProvider>{children}</ToolRendererProvider>
    )

    const { result } = renderHook(() => useToolRenderer(), { wrapper })
    const jsx = result.current.renderTool(createResult())
    expect(jsx).not.toBeNull()
  })
})

describe('ToolResultView', () => {
  it('renders a tool result using context renderer', () => {
    const customRender = vi.fn(() => <span data-testid="rendered">OK</span>)

    render(
      <ToolRendererProvider renderTool={customRender}>
        <ToolResultView result={createResult()} />
      </ToolRendererProvider>,
    )

    expect(customRender).toHaveBeenCalled()
    expect(screen.getByTestId('rendered')).toBeTruthy()
  })

  it('renders with default renderer when no provider', () => {
    // ToolResultView uses useToolRenderer which falls back to default
    // Default renderer dispatches to real renderers via RENDERER_MAP
    const toolResult = createResult({ toolType: 'generic', toolName: 'TestTool' })
    render(<ToolResultView result={toolResult} />)

    // GenericRenderer shows the tool name
    expect(screen.getByText('TestTool')).toBeTruthy()
  })
})

describe('default renderer', () => {
  it('shows tool name and description', () => {
    const result = createResult({
      toolType: 'generic',
      toolName: 'CustomTool',
      description: 'doing stuff',
    })
    render(<ToolResultView result={result} />)

    expect(screen.getByText('CustomTool')).toBeTruthy()
    expect(screen.getByText('doing stuff')).toBeTruthy()
  })

  it('shows output content', () => {
    const result = createResult({
      output: { content: 'hello world' },
    })
    render(<ToolResultView result={result} />)
    expect(screen.getByText('hello world')).toBeTruthy()
  })

  it('shows error output', () => {
    const result = createResult({
      status: 'error',
      output: { error: 'File not found' },
    })
    render(<ToolResultView result={result} />)
    expect(screen.getByText('File not found')).toBeTruthy()
  })

  it('applies status colors', () => {
    const result = createResult({ status: 'error' })
    const { container } = render(<ToolResultView result={result} />)
    const bullet = container.querySelector('span')
    expect(bullet.style.color).toContain('error')
  })
})
