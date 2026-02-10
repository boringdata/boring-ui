/**
 * Tests for shared GlobRenderer component.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import GlobRenderer from './GlobRenderer'

// Mock fileIcons utility
vi.mock('../../utils/fileIcons', () => ({
  getFileIcon: (file, size) => `[icon-${size}]`,
}))

describe('GlobRenderer', () => {
  it('renders tool name "Glob"', () => {
    render(<GlobRenderer pattern="*.js" />)
    expect(screen.getByText('Glob')).toBeTruthy()
  })

  it('shows pattern', () => {
    render(<GlobRenderer pattern="**/*.tsx" />)
    expect(screen.getByText('**/*.tsx')).toBeTruthy()
  })

  it('shows "No files found" for empty results', () => {
    render(<GlobRenderer pattern="*.js" files={[]} status="complete" />)
    expect(screen.getByText('No files found')).toBeTruthy()
  })

  it('shows file list', () => {
    const files = ['src/foo.js', 'src/bar.js', 'src/baz.js']
    render(<GlobRenderer pattern="*.js" files={files} />)
    expect(screen.getByText('src/foo.js')).toBeTruthy()
    expect(screen.getByText('src/bar.js')).toBeTruthy()
    expect(screen.getByText('src/baz.js')).toBeTruthy()
  })

  it('shows running state', () => {
    render(<GlobRenderer pattern="*.js" status="running" />)
    expect(screen.getByText(/Searching files/)).toBeTruthy()
  })

  it('shows error message', () => {
    render(<GlobRenderer pattern="*.js" error="Pattern error" />)
    expect(screen.getByText('Pattern error')).toBeTruthy()
  })

  it('extracts from NormalizedToolResult', () => {
    const result = {
      toolType: 'glob',
      toolName: 'Glob',
      status: 'complete',
      input: { pattern: '**/*.ts' },
      output: { files: ['a.ts', 'b.ts'] },
    }
    render(<GlobRenderer result={result} />)
    expect(screen.getByText('a.ts')).toBeTruthy()
    expect(screen.getByText('b.ts')).toBeTruthy()
  })
})
