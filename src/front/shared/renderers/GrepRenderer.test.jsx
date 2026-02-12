/**
 * Tests for shared GrepRenderer component.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import GrepRenderer from './GrepRenderer'

// Mock fileIcons since GrepRenderer doesn't use it, but InlineCode is used
// No mocks needed for this component

describe('GrepRenderer', () => {
  it('renders tool name "Grep"', () => {
    render(<GrepRenderer pattern="foo" />)
    expect(screen.getByText('Grep')).toBeTruthy()
  })

  it('shows pattern in inline code', () => {
    render(<GrepRenderer pattern="searchTerm" />)
    expect(screen.getByText('searchTerm')).toBeTruthy()
  })

  it('shows search path', () => {
    render(<GrepRenderer pattern="foo" path="src/" />)
    expect(screen.getByText(/in src\//)).toBeTruthy()
  })

  it('shows "No matches found" when no results', () => {
    render(<GrepRenderer pattern="foo" results={[]} status="complete" />)
    expect(screen.getByText('No matches found')).toBeTruthy()
  })

  it('shows file results with match content', () => {
    const results = [
      {
        file: 'src/foo.js',
        matches: [
          { line: 10, content: 'const foo = "bar"' },
        ],
      },
    ]
    const { container } = render(<GrepRenderer pattern="foo" results={results} />)
    expect(screen.getByText('src/foo.js')).toBeTruthy()
    // Content is split across elements by pattern highlighting
    expect(container.textContent).toContain('const foo = "bar"')
  })

  it('shows match count summary', () => {
    const results = [
      { file: 'a.js', matches: [{ line: 1, content: 'a' }] },
      { file: 'b.js', matches: [{ line: 2, content: 'b' }, { line: 3, content: 'c' }] },
    ]
    render(<GrepRenderer pattern="x" results={results} />)
    expect(screen.getByText(/3 matches in 2 files/)).toBeTruthy()
  })

  it('shows running state', () => {
    render(<GrepRenderer pattern="foo" status="running" />)
    expect(screen.getByText(/Searching/)).toBeTruthy()
  })

  it('shows error message', () => {
    render(<GrepRenderer pattern="foo" error="Search failed" />)
    expect(screen.getByText('Search failed')).toBeTruthy()
  })

  it('extracts from NormalizedToolResult', () => {
    const result = {
      toolType: 'grep',
      toolName: 'Grep',
      status: 'complete',
      input: { pattern: 'test', path: 'src' },
      output: {
        searchResults: [
          { file: 'test.js', matches: [{ line: 5, content: 'test()' }] },
        ],
        matchCount: 1,
      },
    }
    const { container } = render(<GrepRenderer result={result} />)
    // "test" appears both as pattern in inline-code and as highlighted match
    expect(container.querySelector('.inline-code').textContent).toBe('test')
    expect(screen.getByText('test.js')).toBeTruthy()
  })

  it('highlights pattern matches in content', () => {
    const results = [
      { file: 'a.js', matches: [{ line: 1, content: 'hello world hello' }] },
    ]
    const { container } = render(
      <GrepRenderer pattern="hello" results={results} />,
    )
    const marks = container.querySelectorAll('mark')
    expect(marks.length).toBe(2) // Two "hello" matches highlighted
  })
})
