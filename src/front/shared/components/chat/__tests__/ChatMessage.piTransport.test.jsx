/**
 * Integration tests for ChatMessage — PI transport custom part types
 * and tool deduplication logic.
 *
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import ChatMessage from '../ChatMessage'

afterEach(() => {
  cleanup()
})

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeMessage(role, parts, overrides = {}) {
  return {
    id: `msg-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    role,
    parts,
    ...overrides,
  }
}

// ---------------------------------------------------------------------------
// 1. PI transport: tool-input-available renders as tool card
// ---------------------------------------------------------------------------

describe('PI transport tool-input-available', () => {
  it('renders a tool card with tool name and running status', () => {
    const msg = makeMessage('assistant', [
      {
        type: 'tool-input-available',
        toolCallId: 'tc-pi-1',
        toolName: 'read_file',
        input: { path: '/src/main.js' },
      },
    ])

    const { container } = render(<ChatMessage message={msg} />)

    // ReadToolRenderer renders toolName="Read" and the basename as description
    expect(screen.getByText('Read')).toBeInTheDocument()
    expect(screen.getByText('main.js')).toBeInTheDocument()

    // tool-input-available normalizes to status: 'running'
    const block = container.querySelector('.tool-use-block')
    expect(block).not.toBeNull()
    expect(block).toHaveClass('status-running')
  })

  it('renders a fallback tool card for unknown tool names', () => {
    const msg = makeMessage('assistant', [
      {
        type: 'tool-input-available',
        toolCallId: 'tc-pi-2',
        toolName: 'custom_tool',
        input: { foo: 'bar' },
      },
    ])

    render(<ChatMessage message={msg} />)

    // ToolFallback renders the raw tool name
    expect(screen.getByText('custom_tool')).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// 2. PI transport: tool-output-available renders as tool card
// ---------------------------------------------------------------------------

describe('PI transport tool-output-available', () => {
  it('renders a completed tool card with output', () => {
    const msg = makeMessage('assistant', [
      {
        type: 'tool-output-available',
        toolCallId: 'tc-pi-3',
        toolName: 'bash',
        output: 'hello world',
      },
    ])

    const { container } = render(<ChatMessage message={msg} />)

    const block = container.querySelector('.tool-use-block')
    expect(block).not.toBeNull()
    // Status should be complete (not running) since preliminary is falsy
    expect(block).toHaveClass('status-complete')
  })

  it('renders as running when preliminary flag is set', () => {
    const msg = makeMessage('assistant', [
      {
        type: 'tool-output-available',
        toolCallId: 'tc-pi-4',
        toolName: 'bash',
        output: 'partial output',
        preliminary: true,
      },
    ])

    const { container } = render(<ChatMessage message={msg} />)

    const block = container.querySelector('.tool-use-block')
    expect(block).not.toBeNull()
    expect(block).toHaveClass('status-running')
  })
})

// ---------------------------------------------------------------------------
// 3. PI transport: tool-output-error renders as error card
// ---------------------------------------------------------------------------

describe('PI transport tool-output-error', () => {
  it('renders a tool card in error state with error text', () => {
    const msg = makeMessage('assistant', [
      {
        type: 'tool-output-error',
        toolCallId: 'tc-pi-5',
        toolName: 'bash',
        errorText: 'command not found: foobar',
      },
    ])

    const { container } = render(<ChatMessage message={msg} />)

    const block = container.querySelector('.tool-use-block')
    expect(block).not.toBeNull()
    expect(block).toHaveClass('status-error')
    // The error text should appear in a ToolError element
    expect(screen.getByText('command not found: foobar')).toBeInTheDocument()
  })

  it('uses default error text when errorText is empty', () => {
    const msg = makeMessage('assistant', [
      {
        type: 'tool-output-error',
        toolCallId: 'tc-pi-6',
        toolName: 'bash',
        errorText: '',
      },
    ])

    render(<ChatMessage message={msg} />)

    expect(screen.getByText('Tool failed')).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// 4. File links only show on last assistant message
// ---------------------------------------------------------------------------

describe('File links on last assistant message', () => {
  it('does NOT render inline file link buttons when isLastAssistantMessage is false', () => {
    const onOpenArtifact = vi.fn()
    const msg = makeMessage('assistant', [
      { type: 'text', text: 'Check out src/main.js for details.' },
    ])

    render(
      <ChatMessage
        message={msg}
        onOpenArtifact={onOpenArtifact}
        activeSessionId="session-1"
        isLastAssistantMessage={false}
      />,
    )

    expect(screen.queryByRole('button', { name: 'src/main.js' })).not.toBeInTheDocument()
  })

  it('renders inline file link buttons when isLastAssistantMessage is true', () => {
    const onOpenArtifact = vi.fn()
    const msg = makeMessage('assistant', [
      { type: 'text', text: 'Check out src/main.js for details.' },
    ])

    render(
      <ChatMessage
        message={msg}
        onOpenArtifact={onOpenArtifact}
        activeSessionId="session-1"
        isLastAssistantMessage={true}
      />,
    )

    expect(screen.getByRole('button', { name: 'src/main.js' })).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// 5. Tool dedup: standard tool-result supersedes tool-call for same toolCallId
//    Note: PI transport types (tool-input-available, tool-output-available,
//    tool-output-error) do not participate in the renderPart dedup filter —
//    they always render. The dedup filter only applies to standard AI SDK
//    types (tool-call, tool-result, tool-error, tool_use).
// ---------------------------------------------------------------------------

describe('Tool deduplication', () => {
  it('standard tool-result supersedes tool-call for the same toolCallId', () => {
    const msg = makeMessage('assistant', [
      {
        type: 'tool-call',
        toolCallId: 'tc-dedup-1',
        toolName: 'read_file',
        input: { path: '/src/index.js' },
      },
      {
        type: 'tool-result',
        toolCallId: 'tc-dedup-1',
        toolName: 'read_file',
        input: { path: '/src/index.js' },
        output: 'file contents here',
      },
    ])

    const { container } = render(<ChatMessage message={msg} />)

    // Only one tool-use-block should be rendered (the result which has higher priority)
    const blocks = container.querySelectorAll('.tool-use-block')
    expect(blocks).toHaveLength(1)

    // The surviving block should be in complete status (result, not running call)
    expect(blocks[0]).toHaveClass('status-complete')
  })

  it('standard tool-error supersedes tool-call for the same toolCallId', () => {
    const msg = makeMessage('assistant', [
      {
        type: 'tool-call',
        toolCallId: 'tc-dedup-2',
        toolName: 'bash',
        input: { command: 'rm -rf /' },
      },
      {
        type: 'tool-error',
        toolCallId: 'tc-dedup-2',
        toolName: 'bash',
        input: { command: 'rm -rf /' },
        error: 'Permission denied',
      },
    ])

    const { container } = render(<ChatMessage message={msg} />)

    const blocks = container.querySelectorAll('.tool-use-block')
    expect(blocks).toHaveLength(1)
    expect(blocks[0]).toHaveClass('status-error')
    expect(screen.getByText('Permission denied')).toBeInTheDocument()
  })

  it('PI transport parts with same toolCallId both render (no dedup filter)', () => {
    // PI transport types are not filtered by selectVisibleToolParts in renderPart,
    // so both parts render even when they share the same toolCallId.
    const msg = makeMessage('assistant', [
      {
        type: 'tool-input-available',
        toolCallId: 'tc-dedup-3',
        toolName: 'read_file',
        input: { path: '/src/index.js' },
      },
      {
        type: 'tool-output-available',
        toolCallId: 'tc-dedup-3',
        toolName: 'read_file',
        output: 'file contents here',
      },
    ])

    const { container } = render(<ChatMessage message={msg} />)

    // Both parts render — PI transport types bypass the dedup filter
    const blocks = container.querySelectorAll('.tool-use-block')
    expect(blocks).toHaveLength(2)
  })
})

// ---------------------------------------------------------------------------
// 6. Standard tool-call and tool-result parts still render
// ---------------------------------------------------------------------------

describe('Standard AI SDK tool parts', () => {
  it('renders a tool-call part as a running tool card', () => {
    const msg = makeMessage('assistant', [
      {
        type: 'tool-call',
        toolCallId: 'tc-std-1',
        toolName: 'read_file',
        input: { path: '/src/app.js' },
      },
    ])

    const { container } = render(<ChatMessage message={msg} />)

    expect(screen.getByText('Read')).toBeInTheDocument()
    expect(screen.getByText('app.js')).toBeInTheDocument()

    const block = container.querySelector('.tool-use-block')
    expect(block).not.toBeNull()
    expect(block).toHaveClass('status-running')
  })

  it('renders a tool-result part as a completed tool card', () => {
    const msg = makeMessage('assistant', [
      {
        type: 'tool-result',
        toolCallId: 'tc-std-2',
        toolName: 'read_file',
        input: { path: '/src/main.js' },
        output: 'file contents',
      },
    ])

    const { container } = render(<ChatMessage message={msg} />)

    expect(screen.getByText('Read')).toBeInTheDocument()
    expect(screen.getByText('main.js')).toBeInTheDocument()

    const block = container.querySelector('.tool-use-block')
    expect(block).not.toBeNull()
    expect(block).toHaveClass('status-complete')
  })

  it('renders a tool-result that supersedes a tool-call with the same toolCallId', () => {
    const msg = makeMessage('assistant', [
      {
        type: 'tool-call',
        toolCallId: 'tc-std-3',
        toolName: 'read_file',
        input: { path: '/src/utils.js' },
      },
      {
        type: 'tool-result',
        toolCallId: 'tc-std-3',
        toolName: 'read_file',
        input: { path: '/src/utils.js' },
        output: 'export default {}',
      },
    ])

    const { container } = render(<ChatMessage message={msg} />)

    // Only one block rendered (result supersedes call)
    const blocks = container.querySelectorAll('.tool-use-block')
    expect(blocks).toHaveLength(1)
    expect(blocks[0]).toHaveClass('status-complete')
  })
})
