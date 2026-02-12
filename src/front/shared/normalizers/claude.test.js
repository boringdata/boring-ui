/**
 * Tests for Claude content normalizer.
 */
import { describe, it, expect } from 'vitest'
import { normalizeClaudeTool, parseGrepResults, parseGlobFiles } from './claude'

describe('parseGrepResults', () => {
  it('returns empty array for null/empty input', () => {
    expect(parseGrepResults(null)).toEqual([])
    expect(parseGrepResults('')).toEqual([])
    expect(parseGrepResults(undefined)).toEqual([])
  })

  it('parses "file:line:content" format', () => {
    const output = 'src/foo.js:10:const foo = bar'
    const results = parseGrepResults(output)
    expect(results).toEqual([
      { file: 'src/foo.js', matches: [{ line: 10, content: 'const foo = bar' }] },
    ])
  })

  it('parses multiple lines', () => {
    const output = 'a.js:1:line1\nb.js:2:line2\nc.js:3:line3'
    const results = parseGrepResults(output)
    expect(results).toHaveLength(3)
    expect(results[0].file).toBe('a.js')
    expect(results[1].file).toBe('b.js')
    expect(results[2].file).toBe('c.js')
  })

  it('handles lines without standard format as fallback', () => {
    const output = 'some random output'
    const results = parseGrepResults(output)
    expect(results).toEqual([
      { file: 'output', matches: [{ line: 1, content: 'some random output' }] },
    ])
  })

  it('handles lines with colons in content', () => {
    const output = 'src/foo.js:5:const obj = { key: "value" }'
    const results = parseGrepResults(output)
    expect(results[0]).toEqual({
      file: 'src/foo.js',
      matches: [{ line: 5, content: 'const obj = { key: "value" }' }],
    })
  })

  it('filters empty lines', () => {
    const output = 'a.js:1:x\n\nb.js:2:y\n'
    const results = parseGrepResults(output)
    expect(results).toHaveLength(2)
  })
})

describe('parseGlobFiles', () => {
  it('returns empty array for null/empty', () => {
    expect(parseGlobFiles(null)).toEqual([])
    expect(parseGlobFiles('')).toEqual([])
  })

  it('parses newline-separated file list', () => {
    const output = 'src/a.js\nsrc/b.js\nsrc/c.js'
    expect(parseGlobFiles(output)).toEqual(['src/a.js', 'src/b.js', 'src/c.js'])
  })

  it('trims whitespace and filters empty lines', () => {
    const output = '  src/a.js  \n\n  src/b.js\n  '
    expect(parseGlobFiles(output)).toEqual(['src/a.js', 'src/b.js'])
  })
})

describe('normalizeClaudeTool', () => {
  describe('bash tools', () => {
    it('normalizes a bash tool_use part', () => {
      const result = normalizeClaudeTool({
        name: 'Bash',
        input: { command: 'ls -la', description: 'List files' },
        output: 'file1.txt\nfile2.txt',
        status: 'complete',
      })
      expect(result.toolType).toBe('bash')
      expect(result.status).toBe('complete')
      expect(result.toolName).toBe('Bash')
      expect(result.description).toBe('List files')
      expect(result.output.content).toBe('file1.txt\nfile2.txt')
    })

    it('truncates long command for description when no description provided', () => {
      const longCmd = 'a'.repeat(100)
      const result = normalizeClaudeTool({
        name: 'Bash',
        input: { command: longCmd },
        status: 'complete',
      })
      expect(result.description).toHaveLength(63) // 60 + "..."
      expect(result.description).toMatch(/\.{3}$/)
    })

    it('uses command as description for short commands', () => {
      const result = normalizeClaudeTool({
        name: 'Bash',
        input: { command: 'ls' },
        status: 'complete',
      })
      expect(result.description).toBe('ls')
    })

    it('preserves exit code', () => {
      const result = normalizeClaudeTool({
        name: 'Bash',
        input: { command: 'bad' },
        output: '',
        exitCode: 1,
        status: 'complete',
      })
      expect(result.output.exitCode).toBe(1)
    })
  })

  describe('read tools', () => {
    it('normalizes a read tool_use part', () => {
      const result = normalizeClaudeTool({
        name: 'Read',
        input: { file_path: 'src/foo.js' },
        lineCount: 42,
        status: 'complete',
      })
      expect(result.toolType).toBe('read')
      expect(result.description).toBe('foo.js')
      expect(result.output.lineCount).toBe(42)
    })

    it('handles path field variant', () => {
      const result = normalizeClaudeTool({
        name: 'Read',
        input: { path: 'src/bar.js' },
        status: 'complete',
      })
      expect(result.description).toBe('bar.js')
    })
  })

  describe('write tools', () => {
    it('normalizes a write tool_use part', () => {
      const result = normalizeClaudeTool({
        name: 'Write',
        input: { file_path: 'out.txt', content: 'hello' },
        status: 'complete',
      })
      expect(result.toolType).toBe('write')
      expect(result.description).toBe('out.txt')
      expect(result.output.content).toBe('hello')
    })

    it('falls back to output text when input.content missing', () => {
      const result = normalizeClaudeTool({
        name: 'Write',
        input: { file_path: 'out.txt' },
        output: 'Written successfully',
        status: 'complete',
      })
      expect(result.output.content).toBe('Written successfully')
    })
  })

  describe('edit tools', () => {
    it('normalizes an edit tool with diff', () => {
      const result = normalizeClaudeTool({
        name: 'Edit',
        input: { file_path: 'src/x.js', diff: '+added\n-removed' },
        status: 'complete',
      })
      expect(result.toolType).toBe('edit')
      expect(result.description).toBe('x.js')
      expect(result.output.diff).toBe('+added\n-removed')
    })

    it('falls back to output as diff', () => {
      const result = normalizeClaudeTool({
        name: 'Edit',
        input: { file_path: 'src/x.js' },
        output: '+line',
        status: 'complete',
      })
      expect(result.output.diff).toBe('+line')
    })
  })

  describe('grep tools', () => {
    it('normalizes grep with parsed results', () => {
      const result = normalizeClaudeTool({
        name: 'Grep',
        input: { pattern: 'foo' },
        output: 'a.js:1:foo bar',
        status: 'complete',
      })
      expect(result.toolType).toBe('grep')
      expect(result.output.searchResults).toHaveLength(1)
      expect(result.output.searchResults[0].file).toBe('a.js')
    })
  })

  describe('glob tools', () => {
    it('normalizes glob with parsed file list', () => {
      const result = normalizeClaudeTool({
        name: 'Glob',
        input: { pattern: '*.js' },
        output: 'a.js\nb.js',
        status: 'complete',
      })
      expect(result.toolType).toBe('glob')
      expect(result.output.files).toEqual(['a.js', 'b.js'])
    })
  })

  describe('status mapping', () => {
    it('maps pending status', () => {
      const result = normalizeClaudeTool({ name: 'Bash', input: {}, status: 'pending' })
      expect(result.status).toBe('pending')
    })

    it('maps running status', () => {
      const result = normalizeClaudeTool({ name: 'Bash', input: {}, status: 'running' })
      expect(result.status).toBe('running')
    })

    it('maps streaming to running', () => {
      const result = normalizeClaudeTool({ name: 'Bash', input: {}, status: 'streaming' })
      expect(result.status).toBe('running')
    })

    it('forces error when error field present', () => {
      const result = normalizeClaudeTool({
        name: 'Bash',
        input: {},
        status: 'complete',
        error: 'command failed',
      })
      expect(result.status).toBe('error')
      expect(result.output.error).toBe('command failed')
    })
  })

  describe('unknown/generic tools', () => {
    it('falls back to generic for unknown tool names', () => {
      const result = normalizeClaudeTool({
        name: 'WebSearch',
        input: { query: 'hello' },
        output: 'search results',
        status: 'complete',
      })
      expect(result.toolType).toBe('generic')
      expect(result.toolName).toBe('WebSearch')
      expect(result.output.content).toBe('search results')
    })

    it('handles missing name gracefully', () => {
      const result = normalizeClaudeTool({ input: {}, status: 'complete' })
      expect(result.toolType).toBe('generic')
      expect(result.toolName).toBe('Tool')
    })

    it('handles missing input gracefully', () => {
      const result = normalizeClaudeTool({ name: 'Bash' })
      expect(result.toolType).toBe('bash')
      expect(result.input).toEqual({})
    })
  })
})
