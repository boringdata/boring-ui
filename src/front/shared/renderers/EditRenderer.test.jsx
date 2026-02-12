/**
 * Tests for shared EditRenderer component.
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import EditRenderer from './EditRenderer'

describe('EditRenderer', () => {
  it('renders tool name "Edit"', () => {
    render(<EditRenderer filePath="f.js" diff="+added" />)
    expect(screen.getByText('Edit')).toBeTruthy()
  })

  it('shows filename from path', () => {
    render(<EditRenderer filePath="src/deep/foo.js" diff="+x" />)
    expect(screen.getByText(/foo\.js/)).toBeTruthy()
  })

  it('shows diff with additions and removals', () => {
    const diff = '+new line\n-old line'
    const { container } = render(<EditRenderer filePath="f.js" diff={diff} />)
    expect(container.textContent).toContain('+new line')
    expect(container.textContent).toContain('-old line')
  })

  it('shows line change subtitle', () => {
    render(
      <EditRenderer filePath="f.js" diff="+x" linesAdded={3} linesRemoved={1} />,
    )
    expect(screen.getByText(/Added 3 lines/)).toBeTruthy()
    expect(screen.getByText(/Removed 1 line$/)).toBeTruthy()
  })

  it('falls back to SimpleDiff for old/new content', () => {
    const { container } = render(
      <EditRenderer filePath="f.js" oldContent="old" newContent="new" />,
    )
    // SimpleDiff renders lines with -/+ prefixes
    expect(container.textContent).toContain('-old')
    expect(container.textContent).toContain('+new')
  })

  it('shows error message', () => {
    render(<EditRenderer filePath="f.js" error="Permission denied" />)
    expect(screen.getByText('Permission denied')).toBeTruthy()
  })

  it('shows pending state', () => {
    render(<EditRenderer filePath="f.js" status="pending" />)
    expect(screen.getByText(/Waiting for permission/)).toBeTruthy()
  })

  it('shows running state', () => {
    render(<EditRenderer filePath="f.js" status="running" />)
    expect(screen.getByText(/Editing file/)).toBeTruthy()
  })

  it('extracts from NormalizedToolResult', () => {
    const result = {
      toolType: 'edit',
      toolName: 'Edit',
      status: 'complete',
      input: { file_path: 'bar.js' },
      output: { diff: '+added line', linesAdded: 1 },
    }
    render(<EditRenderer result={result} />)
    expect(screen.getByText(/bar\.js/)).toBeTruthy()
    expect(screen.getByText(/Added 1 line$/)).toBeTruthy()
  })

  it('accepts diff as string array', () => {
    const diff = ['+line1', '-line2']
    const { container } = render(<EditRenderer filePath="f.js" diff={diff} />)
    expect(container.textContent).toContain('+line1')
    expect(container.textContent).toContain('-line2')
  })
})
