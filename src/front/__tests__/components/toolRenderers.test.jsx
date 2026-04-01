import { describe, it, expect, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { renderToolPart, normalizeToolName, parseGlobFiles, parseGrepResults } from '../../shared/components/chat/toolRenderers'

vi.mock('../../shared/config', () => ({
  getConfig: () => ({ branding: { name: 'Test' } }),
}))

describe('normalizeToolName', () => {
  it('maps exec_bash to bash', () => {
    expect(normalizeToolName('exec_bash')).toBe('bash')
  })

  it('maps structured AI SDK tools onto existing renderer families', () => {
    expect(normalizeToolName('run_command')).toBe('bash')
    expect(normalizeToolName('read_file')).toBe('read')
    expect(normalizeToolName('write_file')).toBe('write')
    expect(normalizeToolName('search_files')).toBe('glob')
    expect(normalizeToolName('git_diff')).toBe('edit')
    expect(normalizeToolName('list_dir')).toBe('list_dir')
    expect(normalizeToolName('git_status')).toBe('git_status')
  })

  it('lowercases tool names', () => {
    expect(normalizeToolName('Bash')).toBe('bash')
    expect(normalizeToolName('READ')).toBe('read')
  })

  it('returns empty string for falsy input', () => {
    expect(normalizeToolName('')).toBe('')
    expect(normalizeToolName(null)).toBe('')
    expect(normalizeToolName(undefined)).toBe('')
  })
})

describe('parseGlobFiles', () => {
  it('splits newlines into file list', () => {
    expect(parseGlobFiles('a.js\nb.ts\n')).toEqual(['a.js', 'b.ts'])
  })

  it('returns empty array for empty input', () => {
    expect(parseGlobFiles('')).toEqual([])
    expect(parseGlobFiles(null)).toEqual([])
  })
})

describe('parseGrepResults', () => {
  it('parses file:line:content format', () => {
    const results = parseGrepResults('src/a.js:10:const x = 1')
    expect(results).toHaveLength(1)
    expect(results[0].file).toBe('src/a.js')
    expect(results[0].matches[0].line).toBe(10)
  })

  it('returns empty array for empty input', () => {
    expect(parseGrepResults('')).toEqual([])
    expect(parseGrepResults(null)).toEqual([])
  })
})

describe('renderToolPart', () => {
  it('renders bash tool with command', () => {
    const { container } = render(renderToolPart({
      name: 'bash',
      input: { command: 'echo hello' },
      output: 'hello',
      status: 'complete',
    }))
    expect(container.textContent).toContain('echo hello')
  })

  it('renders exec_bash as bash tool', () => {
    const { container } = render(renderToolPart({
      name: 'exec_bash',
      input: { command: 'ls -la' },
      output: 'total 0',
      status: 'complete',
    }))
    expect(container.textContent).toContain('ls -la')
  })

  it('renders read tool with file path', () => {
    const { container } = render(renderToolPart({
      name: 'read',
      input: { file_path: '/src/app.js' },
      status: 'complete',
    }))
    // ReadToolRenderer extracts basename for display
    expect(container.textContent).toContain('app.js')
  })

  it('renders structured aliases using the shared renderer set', () => {
    const { container } = render(renderToolPart({
      name: 'run_command',
      input: { command: 'pwd' },
      output: '/workspace',
      status: 'complete',
    }))
    expect(container.textContent).toContain('pwd')

    const read = render(renderToolPart({
      name: 'read_file',
      input: { path: 'src/app.js' },
      status: 'complete',
    }))
    expect(read.container.textContent).toContain('app.js')

    const list = render(renderToolPart({
      name: 'list_dir',
      input: { path: '.' },
      output: 'src/\nREADME.md',
      status: 'complete',
    }))
    fireEvent.click(screen.getByRole('button', { name: /list directory/i }))
    expect(list.container.textContent).toContain('README.md')
  })

  it('renders git status with a clearer label than the generic fallback', () => {
    const status = render(renderToolPart({
      name: 'git_status',
      input: {},
      output: 'modified tracked.txt\nuntracked notes/todo.txt',
      status: 'complete',
    }))
    fireEvent.click(screen.getByRole('button', { name: /git status/i }))
    expect(status.container.textContent).toContain('modified tracked.txt')
  })

  it('renders unknown tool with fallback', () => {
    const { container } = render(renderToolPart({
      name: 'custom_tool',
      input: { foo: 'bar' },
      output: 'result',
      status: 'complete',
    }))
    expect(container.textContent).toContain('custom_tool')
  })

  it('renders in-progress bash tool', () => {
    const { container } = render(renderToolPart({
      name: 'bash',
      input: { command: 'sleep 10' },
      output: '',
      status: 'running',
    }))
    expect(container.textContent).toContain('sleep 10')
  })
})
