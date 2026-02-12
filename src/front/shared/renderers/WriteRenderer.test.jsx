/**
 * Tests for shared WriteRenderer component.
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import WriteRenderer from './WriteRenderer'

describe('WriteRenderer', () => {
  it('renders tool name "Write"', () => {
    render(<WriteRenderer filePath="f.js" content="code" />)
    expect(screen.getByText('Write')).toBeTruthy()
  })

  it('shows filename from path', () => {
    render(<WriteRenderer filePath="src/deep/foo.js" content="x" />)
    expect(screen.getByText(/foo\.js/)).toBeTruthy()
  })

  it('shows content', () => {
    render(<WriteRenderer filePath="f.js" content="const x = 1" />)
    expect(screen.getByText('const x = 1')).toBeTruthy()
  })

  it('shows line count subtitle', () => {
    render(<WriteRenderer filePath="f.js" content={'a\nb\nc'} />)
    expect(screen.getByText('3 lines')).toBeTruthy()
  })

  it('shows singular line subtitle', () => {
    render(<WriteRenderer filePath="f.js" content="one" lineCount={1} />)
    expect(screen.getByText('1 line')).toBeTruthy()
  })

  it('shows error message', () => {
    render(<WriteRenderer filePath="f.js" error="Permission denied" />)
    expect(screen.getByText('Permission denied')).toBeTruthy()
  })

  it('shows pending state', () => {
    render(<WriteRenderer filePath="f.js" status="pending" />)
    expect(screen.getByText(/Waiting for permission/)).toBeTruthy()
  })

  it('shows running state', () => {
    render(<WriteRenderer filePath="f.js" status="running" />)
    expect(screen.getByText(/Writing file/)).toBeTruthy()
  })

  it('extracts from NormalizedToolResult', () => {
    const result = {
      toolType: 'write',
      toolName: 'Write',
      status: 'complete',
      input: { file_path: 'out.txt', content: 'hello' },
      output: {},
    }
    render(<WriteRenderer result={result} />)
    expect(screen.getByText('hello')).toBeTruthy()
    expect(screen.getByText(/out\.txt/)).toBeTruthy()
  })
})
