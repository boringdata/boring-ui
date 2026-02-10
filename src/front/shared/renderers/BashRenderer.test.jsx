/**
 * Tests for shared BashRenderer component.
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import BashRenderer from './BashRenderer'

describe('BashRenderer', () => {
  it('renders tool name "Bash"', () => {
    render(<BashRenderer command="ls" status="complete" />)
    expect(screen.getByText('Bash')).toBeTruthy()
  })

  it('shows command in code block when not compact', () => {
    const { container } = render(<BashRenderer command="ls -la" compact={false} />)
    expect(container.textContent).toContain('ls -la')
  })

  it('hides command display in compact mode', () => {
    const { container } = render(
      <BashRenderer command="ls -la" output="file.txt" compact={true} />,
    )
    // In compact mode, command code block is not rendered
    const codeBlock = container.querySelector('code')
    expect(codeBlock).toBeNull()
  })

  it('shows output text', () => {
    render(<BashRenderer command="echo hi" output="hi" compact={false} />)
    expect(screen.getByText('hi')).toBeTruthy()
  })

  it('shows compact output (3-line summary)', () => {
    const output = 'line1\nline2\nline3\nline4\nline5'
    render(<BashRenderer command="cmd" output={output} compact={true} />)
    // Compact shows first 3 lines with "... +N lines"
    expect(screen.getByText(/\+2 lines/)).toBeTruthy()
  })

  it('shows error message', () => {
    render(<BashRenderer command="bad" error="command not found" />)
    expect(screen.getByText('command not found')).toBeTruthy()
  })

  it('shows exit code when non-zero', () => {
    render(<BashRenderer command="bad" output="err" exitCode={1} />)
    expect(screen.getByText(/Exit code: 1/)).toBeTruthy()
  })

  it('does not show exit code for zero', () => {
    const { container } = render(
      <BashRenderer command="good" output="ok" exitCode={0} />,
    )
    expect(container.textContent).not.toContain('Exit code')
  })

  it('shows pending state', () => {
    render(<BashRenderer command="cmd" status="pending" />)
    expect(screen.getByText(/Waiting for permission/)).toBeTruthy()
  })

  it('shows running state', () => {
    render(<BashRenderer command="cmd" status="running" />)
    expect(screen.getByText(/Running command/)).toBeTruthy()
  })

  it('extracts from NormalizedToolResult', () => {
    const result = {
      toolType: 'bash',
      toolName: 'Bash',
      status: 'complete',
      input: { command: 'echo hello' },
      output: { content: 'hello', exitCode: 0 },
    }
    const { container } = render(<BashRenderer result={result} compact={false} />)
    // Command appears in code block, output in pre
    expect(container.textContent).toContain('echo hello')
    expect(container.textContent).toContain('hello')
  })

  it('truncates long description', () => {
    const longCommand = 'a'.repeat(100)
    render(<BashRenderer command={longCommand} />)
    // Description should be truncated to 60 chars + "..."
    expect(screen.getByText(/\.{3}/)).toBeTruthy()
  })

  it('uses description prop over command for header', () => {
    render(<BashRenderer command="ls" description="List files" />)
    expect(screen.getByText('List files')).toBeTruthy()
  })
})
