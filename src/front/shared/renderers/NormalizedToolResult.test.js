/**
 * Tests for NormalizedToolResult contract helpers.
 */
import { describe, it, expect } from 'vitest'
import {
  classifyTool,
  normalizeStatus,
  createToolResult,
  parseDiffLines,
} from './NormalizedToolResult'

describe('classifyTool', () => {
  it('returns bash for "bash" (case-insensitive)', () => {
    expect(classifyTool('bash')).toBe('bash')
    expect(classifyTool('Bash')).toBe('bash')
    expect(classifyTool('BASH')).toBe('bash')
  })

  it('returns read for "read"', () => {
    expect(classifyTool('read')).toBe('read')
    expect(classifyTool('Read')).toBe('read')
  })

  it('returns write for "write"', () => {
    expect(classifyTool('write')).toBe('write')
  })

  it('returns edit for "edit"', () => {
    expect(classifyTool('edit')).toBe('edit')
  })

  it('returns grep for "grep"', () => {
    expect(classifyTool('grep')).toBe('grep')
  })

  it('returns glob for "glob"', () => {
    expect(classifyTool('glob')).toBe('glob')
  })

  it('returns generic for unknown tool names', () => {
    expect(classifyTool('custom_tool')).toBe('generic')
    expect(classifyTool('WebSearch')).toBe('generic')
  })

  it('returns generic for null/undefined/empty', () => {
    expect(classifyTool(null)).toBe('generic')
    expect(classifyTool(undefined)).toBe('generic')
    expect(classifyTool('')).toBe('generic')
  })
})

describe('normalizeStatus', () => {
  it('maps Claude statuses', () => {
    expect(normalizeStatus('pending')).toBe('pending')
    expect(normalizeStatus('running')).toBe('running')
    expect(normalizeStatus('streaming')).toBe('running')
    expect(normalizeStatus('complete')).toBe('complete')
    expect(normalizeStatus('error')).toBe('error')
  })

  it('maps Sandbox statuses', () => {
    expect(normalizeStatus('in_progress')).toBe('running')
    expect(normalizeStatus('completed')).toBe('complete')
    expect(normalizeStatus('failed')).toBe('error')
  })

  it('returns complete for null/undefined', () => {
    expect(normalizeStatus(null)).toBe('complete')
    expect(normalizeStatus(undefined)).toBe('complete')
  })

  it('forces error when opts.isError is true', () => {
    expect(normalizeStatus('complete', { isError: true })).toBe('error')
    expect(normalizeStatus('running', { isError: true })).toBe('error')
  })

  it('returns complete for unrecognized status', () => {
    expect(normalizeStatus('unknown_status')).toBe('complete')
  })
})

describe('createToolResult', () => {
  it('creates a result with defaults', () => {
    const result = createToolResult({ toolName: 'Bash' })
    expect(result).toEqual({
      toolType: 'bash',
      status: 'complete',
      toolName: 'Bash',
      input: {},
    })
  })

  it('merges provided fields over defaults', () => {
    const result = createToolResult({
      toolName: 'Read',
      status: 'running',
      input: { path: 'src/foo.js' },
      description: 'Reading file',
    })
    expect(result.toolType).toBe('read')
    expect(result.status).toBe('running')
    expect(result.input).toEqual({ path: 'src/foo.js' })
    expect(result.description).toBe('Reading file')
  })

  it('classifies unknown tool as generic', () => {
    const result = createToolResult({ toolName: 'WebSearch' })
    expect(result.toolType).toBe('generic')
  })

  it('allows toolType override', () => {
    const result = createToolResult({ toolName: 'CustomBash', toolType: 'bash' })
    expect(result.toolType).toBe('bash')
  })
})

describe('parseDiffLines', () => {
  it('classifies additions', () => {
    const lines = parseDiffLines('+added line')
    expect(lines).toEqual([{ content: '+added line', type: 'add' }])
  })

  it('classifies removals', () => {
    const lines = parseDiffLines('-removed line')
    expect(lines).toEqual([{ content: '-removed line', type: 'remove' }])
  })

  it('classifies context lines', () => {
    const lines = parseDiffLines(' context line')
    expect(lines).toEqual([{ content: ' context line', type: 'context' }])
  })

  it('classifies header lines', () => {
    const lines = parseDiffLines('@@ -1,3 +1,4 @@\n--- a/file.js\n+++ b/file.js')
    expect(lines[0].type).toBe('header')
    expect(lines[1].type).toBe('header')
    expect(lines[2].type).toBe('header')
  })

  it('does not classify +++ as addition', () => {
    const lines = parseDiffLines('+++ b/file.js')
    expect(lines[0].type).toBe('header')
  })

  it('does not classify --- as removal', () => {
    const lines = parseDiffLines('--- a/file.js')
    expect(lines[0].type).toBe('header')
  })

  it('handles multi-line diff string', () => {
    const diff = '@@ -1,2 +1,3 @@\n context\n-old\n+new\n+extra'
    const lines = parseDiffLines(diff)
    expect(lines).toHaveLength(5)
    expect(lines.map((l) => l.type)).toEqual(['header', 'context', 'remove', 'add', 'add'])
  })

  it('handles array input', () => {
    const lines = parseDiffLines(['+added', '-removed', ' context'])
    expect(lines).toHaveLength(3)
    expect(lines[0].type).toBe('add')
    expect(lines[1].type).toBe('remove')
    expect(lines[2].type).toBe('context')
  })

  it('returns empty array for null/undefined', () => {
    expect(parseDiffLines(null)).toEqual([])
    expect(parseDiffLines(undefined)).toEqual([])
    expect(parseDiffLines('')).toEqual([])
  })
})
