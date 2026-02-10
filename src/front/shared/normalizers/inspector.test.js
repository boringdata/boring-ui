/**
 * Tests for Inspector content normalizer.
 */
import { describe, it, expect } from 'vitest'
import {
  normalizeInspectorToolCall,
  normalizeInspectorFileRef,
  normalizeInspectorItem,
} from './inspector'

describe('normalizeInspectorToolCall', () => {
  it('normalizes a bash tool_call', () => {
    const result = normalizeInspectorToolCall(
      { name: 'Bash', arguments: '{"command":"ls"}', call_id: '1' },
      { output: 'file.txt' },
    )
    expect(result.toolType).toBe('bash')
    expect(result.status).toBe('complete')
    expect(result.toolName).toBe('Bash')
    expect(result.input.command).toBe('ls')
    expect(result.output.content).toBe('file.txt')
    expect(result.description).toBe('ls')
  })

  it('returns running when no tool_result provided', () => {
    const result = normalizeInspectorToolCall(
      { name: 'Read', arguments: '{"file_path":"foo.js"}', call_id: '2' },
    )
    expect(result.status).toBe('running')
  })

  it('handles malformed JSON arguments gracefully', () => {
    const result = normalizeInspectorToolCall(
      { name: 'Bash', arguments: 'not json', call_id: '3' },
      { output: 'ok' },
    )
    expect(result.input).toEqual({ raw: 'not json' })
    expect(result.toolType).toBe('bash')
  })

  it('handles empty arguments', () => {
    const result = normalizeInspectorToolCall(
      { name: 'Bash', arguments: '', call_id: '4' },
    )
    expect(result.input).toEqual({})
  })

  it('normalizes read tool with description', () => {
    const result = normalizeInspectorToolCall(
      { name: 'Read', arguments: '{"file_path":"src/bar.js"}', call_id: '5' },
      { output: 'content' },
    )
    expect(result.toolType).toBe('read')
    expect(result.description).toBe('bar.js')
  })

  it('normalizes grep tool with description', () => {
    const result = normalizeInspectorToolCall(
      { name: 'Grep', arguments: '{"pattern":"foo"}', call_id: '6' },
      { output: 'results' },
    )
    expect(result.toolType).toBe('grep')
    expect(result.description).toBe('foo')
  })

  it('normalizes unknown tool as generic', () => {
    const result = normalizeInspectorToolCall(
      { name: 'WebSearch', arguments: '{"query":"test"}', call_id: '7' },
      { output: 'data' },
    )
    expect(result.toolType).toBe('generic')
    expect(result.toolName).toBe('WebSearch')
  })

  it('handles missing tool name', () => {
    const result = normalizeInspectorToolCall(
      { arguments: '{}', call_id: '8' },
      { output: '' },
    )
    expect(result.toolName).toBe('Tool')
    expect(result.toolType).toBe('generic')
  })
})

describe('normalizeInspectorFileRef', () => {
  it('normalizes a read file_ref', () => {
    const result = normalizeInspectorFileRef({
      path: 'src/foo.js',
      action: 'read',
    })
    expect(result.toolType).toBe('read')
    expect(result.toolName).toBe('Read')
    expect(result.description).toBe('foo.js')
    expect(result.input.file_path).toBe('src/foo.js')
    expect(result.status).toBe('complete')
  })

  it('normalizes a write file_ref', () => {
    const result = normalizeInspectorFileRef({
      path: 'out.txt',
      action: 'write',
    })
    expect(result.toolType).toBe('write')
    expect(result.toolName).toBe('Write')
  })

  it('normalizes a create file_ref as write', () => {
    const result = normalizeInspectorFileRef({
      path: 'new.txt',
      action: 'create',
    })
    expect(result.toolType).toBe('write')
  })

  it('normalizes an edit file_ref with diff', () => {
    const result = normalizeInspectorFileRef({
      path: 'src/x.js',
      action: 'edit',
      diff: '+added\n-removed',
    })
    expect(result.toolType).toBe('edit')
    expect(result.toolName).toBe('Edit')
    expect(result.output.diff).toBe('+added\n-removed')
  })

  it('normalizes modify action as edit', () => {
    const result = normalizeInspectorFileRef({
      path: 'src/x.js',
      action: 'modify',
    })
    expect(result.toolType).toBe('edit')
  })

  it('puts diff in content for non-edit actions', () => {
    const result = normalizeInspectorFileRef({
      path: 'src/x.js',
      action: 'read',
      diff: 'some content',
    })
    expect(result.output.content).toBe('some content')
    expect(result.output.diff).toBeUndefined()
  })

  it('handles unknown action as generic', () => {
    const result = normalizeInspectorFileRef({
      path: 'file',
      action: 'delete',
    })
    expect(result.toolType).toBe('generic')
    expect(result.toolName).toBe('delete')
  })
})

describe('normalizeInspectorItem', () => {
  it('normalizes a tool_call UniversalItem', () => {
    const result = normalizeInspectorItem({
      item_id: 'item1',
      kind: 'tool_call',
      status: 'completed',
      content: [
        { type: 'tool_call', name: 'Bash', arguments: '{"command":"pwd"}', call_id: 'c1' },
      ],
    })
    expect(result.toolType).toBe('bash')
    expect(result.status).toBe('running') // no tool_result = running
  })

  it('normalizes a combined tool_call+tool_result item', () => {
    const result = normalizeInspectorItem({
      item_id: 'item2',
      kind: 'tool_call',
      status: 'completed',
      content: [
        { type: 'tool_call', name: 'Read', arguments: '{"file_path":"f.js"}', call_id: 'c2' },
        { type: 'tool_result', call_id: 'c2', output: 'file content' },
      ],
    })
    expect(result.toolType).toBe('read')
    expect(result.status).toBe('complete')
    expect(result.output.content).toBe('file content')
  })

  it('normalizes a standalone tool_result item', () => {
    const result = normalizeInspectorItem({
      item_id: 'item3',
      kind: 'tool_result',
      status: 'completed',
      content: [
        { type: 'tool_result', call_id: 'c3', output: 'some output' },
      ],
    })
    expect(result.toolType).toBe('generic')
    expect(result.toolName).toBe('Result')
    expect(result.output.content).toBe('some output')
  })

  it('returns null for null/empty items', () => {
    expect(normalizeInspectorItem(null)).toBeNull()
    expect(normalizeInspectorItem({})).toBeNull()
    expect(normalizeInspectorItem({ content: [] })).toBeNull()
  })

  it('returns null for items without tool content', () => {
    const result = normalizeInspectorItem({
      item_id: 'item4',
      kind: 'message',
      content: [{ type: 'text', text: 'hello' }],
    })
    expect(result).toBeNull()
  })
})
