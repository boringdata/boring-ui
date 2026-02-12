/**
 * Tests for Companion content normalizer.
 */
import { describe, it, expect } from 'vitest'
import { normalizeCompanionTool } from './companion'

describe('normalizeCompanionTool', () => {
  describe('bash tools', () => {
    it('normalizes a bash tool_use with result', () => {
      const result = normalizeCompanionTool(
        { name: 'Bash', input: { command: 'ls', description: 'List files' } },
        { content: 'file1.txt\nfile2.txt', is_error: false },
      )
      expect(result.toolType).toBe('bash')
      expect(result.status).toBe('complete')
      expect(result.toolName).toBe('Bash')
      expect(result.description).toBe('List files')
      expect(result.output.content).toBe('file1.txt\nfile2.txt')
      expect(result.output.error).toBeUndefined()
    })

    it('uses command as description when no description', () => {
      const result = normalizeCompanionTool(
        { name: 'Bash', input: { command: 'pwd' } },
        { content: '/home', is_error: false },
      )
      expect(result.description).toBe('pwd')
    })

    it('marks error when is_error true', () => {
      const result = normalizeCompanionTool(
        { name: 'Bash', input: { command: 'bad' } },
        { content: 'command not found', is_error: true },
      )
      expect(result.status).toBe('error')
      expect(result.output.error).toBe('command not found')
    })
  })

  describe('read tools', () => {
    it('normalizes a read tool_use', () => {
      const result = normalizeCompanionTool(
        { name: 'Read', input: { file_path: 'src/foo.js' } },
        { content: 'const x = 1', is_error: false },
      )
      expect(result.toolType).toBe('read')
      expect(result.description).toBe('foo.js')
      expect(result.output.content).toBe('const x = 1')
    })

    it('handles path field variant', () => {
      const result = normalizeCompanionTool(
        { name: 'Read', input: { path: 'src/bar.js' } },
        { content: 'data', is_error: false },
      )
      expect(result.description).toBe('bar.js')
    })

    it('handles read error', () => {
      const result = normalizeCompanionTool(
        { name: 'Read', input: { file_path: 'missing.js' } },
        { content: 'File not found', is_error: true },
      )
      expect(result.status).toBe('error')
      expect(result.output.error).toBe('File not found')
    })
  })

  describe('write tools', () => {
    it('normalizes a write tool_use', () => {
      const result = normalizeCompanionTool(
        { name: 'Write', input: { file_path: 'out.txt', content: 'hello world' } },
        { content: 'Written', is_error: false },
      )
      expect(result.toolType).toBe('write')
      expect(result.description).toBe('out.txt')
      // Prefers input.content over result content
      expect(result.output.content).toBe('hello world')
    })

    it('falls back to result content when input.content missing', () => {
      const result = normalizeCompanionTool(
        { name: 'Write', input: { file_path: 'out.txt' } },
        { content: 'file written', is_error: false },
      )
      expect(result.output.content).toBe('file written')
    })
  })

  describe('edit tools', () => {
    it('normalizes an edit with diff from input', () => {
      const result = normalizeCompanionTool(
        { name: 'Edit', input: { file_path: 'x.js', diff: '+line' } },
        { content: 'ok', is_error: false },
      )
      expect(result.toolType).toBe('edit')
      expect(result.description).toBe('x.js')
      expect(result.output.diff).toBe('+line')
    })

    it('preserves old_string and new_string', () => {
      const result = normalizeCompanionTool(
        { name: 'Edit', input: { file_path: 'x.js', old_string: 'old', new_string: 'new' } },
        { content: 'ok', is_error: false },
      )
      expect(result.output.oldContent).toBe('old')
      expect(result.output.newContent).toBe('new')
    })

    it('falls back to result content as diff', () => {
      const result = normalizeCompanionTool(
        { name: 'Edit', input: { file_path: 'x.js' } },
        { content: '+added\n-removed', is_error: false },
      )
      expect(result.output.diff).toBe('+added\n-removed')
    })
  })

  describe('grep tools', () => {
    it('normalizes a grep tool_use', () => {
      const result = normalizeCompanionTool(
        { name: 'Grep', input: { pattern: 'foo' } },
        { content: 'search results', is_error: false },
      )
      expect(result.toolType).toBe('grep')
      expect(result.output.content).toBe('search results')
    })
  })

  describe('glob tools', () => {
    it('normalizes a glob tool_use with file list', () => {
      const result = normalizeCompanionTool(
        { name: 'Glob', input: { pattern: '*.js' } },
        { content: 'a.js\nb.js\nc.js', is_error: false },
      )
      expect(result.toolType).toBe('glob')
      expect(result.output.files).toEqual(['a.js', 'b.js', 'c.js'])
    })

    it('handles empty glob results', () => {
      const result = normalizeCompanionTool(
        { name: 'Glob', input: { pattern: '*.xyz' } },
        { content: '', is_error: false },
      )
      expect(result.output.files).toEqual([])
    })
  })

  describe('status mapping', () => {
    it('returns running when no tool_result provided', () => {
      const result = normalizeCompanionTool(
        { name: 'Bash', input: { command: 'ls' } },
      )
      expect(result.status).toBe('running')
    })

    it('returns complete for successful result', () => {
      const result = normalizeCompanionTool(
        { name: 'Bash', input: {} },
        { content: 'ok', is_error: false },
      )
      expect(result.status).toBe('complete')
    })

    it('returns error for is_error=true', () => {
      const result = normalizeCompanionTool(
        { name: 'Bash', input: {} },
        { content: 'failed', is_error: true },
      )
      expect(result.status).toBe('error')
    })
  })

  describe('unknown/generic tools', () => {
    it('falls back to generic for unknown tool names', () => {
      const result = normalizeCompanionTool(
        { name: 'WebSearch', input: { query: 'test' } },
        { content: 'results', is_error: false },
      )
      expect(result.toolType).toBe('generic')
      expect(result.toolName).toBe('WebSearch')
      expect(result.output.content).toBe('results')
    })

    it('describes generic tool from input fields', () => {
      const result = normalizeCompanionTool(
        { name: 'Custom', input: { command: 'custom-cmd' } },
        { content: 'ok', is_error: false },
      )
      expect(result.description).toBe('custom-cmd')
    })

    it('handles missing name', () => {
      const result = normalizeCompanionTool(
        { input: {} },
        { content: 'ok', is_error: false },
      )
      expect(result.toolName).toBe('Tool')
    })
  })

  describe('non-string content', () => {
    it('JSON-stringifies object content', () => {
      const result = normalizeCompanionTool(
        { name: 'Bash', input: {} },
        { content: { key: 'value' }, is_error: false },
      )
      expect(result.output.content).toContain('"key"')
      expect(result.output.content).toContain('"value"')
    })

    it('handles null content', () => {
      const result = normalizeCompanionTool(
        { name: 'Bash', input: {} },
        { content: null, is_error: false },
      )
      expect(result.output.content).toBe('')
    })
  })
})
