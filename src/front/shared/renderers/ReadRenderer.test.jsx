/**
 * Tests for shared ReadRenderer component.
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import ReadRenderer from './ReadRenderer'

describe('ReadRenderer', () => {
  it('renders tool name "Read"', () => {
    render(<ReadRenderer filePath="src/foo.js" />)
    expect(screen.getByText('Read')).toBeTruthy()
  })

  it('shows filename from path', () => {
    render(<ReadRenderer filePath="src/deep/nested/foo.js" />)
    expect(screen.getByText(/foo\.js/)).toBeTruthy()
  })

  it('shows file content when not hidden', () => {
    render(<ReadRenderer filePath="f.js" content="const x = 1" />)
    expect(screen.getByText('const x = 1')).toBeTruthy()
  })

  it('hides content and shows line count when hideContent is true', () => {
    render(
      <ReadRenderer filePath="f.js" content="code" lineCount={42} hideContent />,
    )
    expect(screen.getByText(/42 lines read/)).toBeTruthy()
    expect(screen.queryByText('code')).toBeNull()
  })

  it('shows line count in description', () => {
    render(<ReadRenderer filePath="f.js" lineCount={100} />)
    expect(screen.getByText(/100 lines/)).toBeTruthy()
  })

  it('shows truncated indicator', () => {
    render(<ReadRenderer filePath="f.js" truncated />)
    expect(screen.getByText(/truncated/)).toBeTruthy()
  })

  it('shows error message', () => {
    render(<ReadRenderer filePath="f.js" error="File not found" />)
    expect(screen.getByText('File not found')).toBeTruthy()
  })

  it('shows running state', () => {
    render(<ReadRenderer filePath="f.js" status="running" />)
    expect(screen.getByText(/Reading file/)).toBeTruthy()
  })

  it('extracts from NormalizedToolResult', () => {
    const result = {
      toolType: 'read',
      toolName: 'Read',
      status: 'complete',
      input: { file_path: 'src/bar.js' },
      output: { content: 'bar content', lineCount: 10 },
    }
    render(<ReadRenderer result={result} />)
    expect(screen.getByText('bar content')).toBeTruthy()
    expect(screen.getByText(/10 lines/)).toBeTruthy()
  })

  it('uses singular "line" for lineCount=1', () => {
    render(<ReadRenderer filePath="f.js" lineCount={1} hideContent />)
    expect(screen.getByText('1 line read')).toBeTruthy()
  })
})
