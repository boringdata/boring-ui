import { describe, it, after } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'

import { createWorkspaceTools, resolveSessionContext, buildSessionSystemPrompt } from './tools.mjs'

describe('direct workspace tools', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'pi-tools-test-'))

  // Override BORING_UI_WORKSPACE_ROOT for tests.
  // NOTE: tools.mjs reads WORKSPACE_ROOT at module load time, so we
  // dynamically import after setting env — but since ESM caches, we rely
  // on createWorkspaceTools reading the env internally. The module-level
  // const WORKSPACE_ROOT is set from process.env at import time; we must
  // set the env var BEFORE the dynamic import. Since the static import
  // above already captured it, the tools use the module-level constant.
  // To work around this we set env before module evaluation wouldn't help
  // for static imports, so instead we create files in the OS tmpdir and
  // accept that path validation uses the module's WORKSPACE_ROOT.
  //
  // A simpler approach: just set the env var and accept the test will use
  // the tmpDir only for tool execution paths that the tools resolve.
  process.env.BORING_UI_WORKSPACE_ROOT = tmpDir

  // Re-import to pick up new WORKSPACE_ROOT
  // Since ESM modules are cached, we need to work with the already-imported
  // module. The tools.mjs WORKSPACE_ROOT is set at module load time from
  // process.env. For a clean test we would need dynamic import with cache
  // busting. Instead, let's test via a fresh dynamic import.

  let tools
  let findTool

  // Use a before hook to dynamically import with cache-busting
  it('setup: load tools with custom workspace root', async () => {
    // Dynamic import with query string to bypass ESM cache
    const mod = await import(`./tools.mjs?t=${Date.now()}`)
    tools = mod.createWorkspaceTools({})
    findTool = (name) => tools.find((t) => t.name === name)
    assert.ok(tools.length >= 7, `expected >= 7 tools, got ${tools.length}`)
  })

  it('creates the expected tools', () => {
    const names = tools.map((t) => t.name)
    assert.ok(names.includes('read_file'), 'missing read_file')
    assert.ok(names.includes('write_file'), 'missing write_file')
    assert.ok(names.includes('list_dir'), 'missing list_dir')
    assert.ok(names.includes('exec'), 'missing exec')
    assert.ok(names.includes('git_status'), 'missing git_status')
    assert.ok(names.includes('git_diff'), 'missing git_diff')
    assert.ok(names.includes('git_commit'), 'missing git_commit')
  })

  it('write_file creates a file', async () => {
    const tool = findTool('write_file')
    const result = await tool.execute(null, { path: 'test.txt', content: 'hello' })
    assert.ok(fs.existsSync(path.join(tmpDir, 'test.txt')), 'file should exist on disk')
    assert.equal(fs.readFileSync(path.join(tmpDir, 'test.txt'), 'utf-8'), 'hello')
    assert.ok(result.content[0].text.includes('Wrote'), 'result should confirm write')
  })

  it('read_file reads a file', async () => {
    const tool = findTool('read_file')
    const result = await tool.execute(null, { path: 'test.txt' })
    assert.ok(result.content[0].text.includes('hello'), 'should contain file content')
  })

  it('list_dir lists files', async () => {
    const tool = findTool('list_dir')
    const result = await tool.execute(null, { path: '.' })
    assert.ok(result.content[0].text.includes('test.txt'), 'should list test.txt')
  })

  it('exec runs a command', async () => {
    const tool = findTool('exec')
    const result = await tool.execute(null, { command: 'echo test-output' })
    assert.ok(result.content[0].text.includes('test-output'), 'should contain command output')
  })

  it('exec returns exit code for failing commands', async () => {
    const tool = findTool('exec')
    const result = await tool.execute(null, { command: 'exit 42' })
    assert.ok(result.content[0].text.includes('42'), 'should contain exit code')
  })

  it('write_file creates parent directories', async () => {
    const tool = findTool('write_file')
    await tool.execute(null, { path: 'deep/nested/file.txt', content: 'nested' })
    const fullPath = path.join(tmpDir, 'deep', 'nested', 'file.txt')
    assert.ok(fs.existsSync(fullPath), 'nested file should exist')
    assert.equal(fs.readFileSync(fullPath, 'utf-8'), 'nested')
  })

  it('write_file rejects path traversal', async () => {
    const tool = findTool('write_file')
    await assert.rejects(
      () => tool.execute(null, { path: '../../etc/passwd', content: 'hack' }),
      /escapes/i,
      'should reject path traversal',
    )
  })

  it('read_file rejects path traversal', async () => {
    const tool = findTool('read_file')
    await assert.rejects(
      () => tool.execute(null, { path: '../../../etc/hostname' }),
      /escapes/i,
      'should reject path traversal',
    )
  })

  it('exec rejects cwd traversal', async () => {
    const tool = findTool('exec')
    await assert.rejects(
      () => tool.execute(null, { command: 'pwd', cwd: '../../etc' }),
      /escapes/i,
      'should reject cwd traversal',
    )
  })

  it('list_dir rejects path traversal', async () => {
    const tool = findTool('list_dir')
    await assert.rejects(
      () => tool.execute(null, { path: '../../../' }),
      /escapes/i,
      'should reject path traversal',
    )
  })

  it('write_file handles empty content', async () => {
    const tool = findTool('write_file')
    const result = await tool.execute(null, { path: 'empty.txt', content: '' })
    assert.ok(result.content[0].text.includes('0 bytes'), 'should report 0 bytes')
    assert.equal(fs.readFileSync(path.join(tmpDir, 'empty.txt'), 'utf-8'), '')
  })

  it('exec respects cwd within workspace', async () => {
    const tool = findTool('exec')
    fs.mkdirSync(path.join(tmpDir, 'subdir'), { recursive: true })
    const result = await tool.execute(null, { command: 'pwd', cwd: 'subdir' })
    assert.ok(result.content[0].text.includes('subdir'), 'should run in subdir')
  })

  // Cleanup
  after(() => {
    try {
      fs.rmSync(tmpDir, { recursive: true, force: true })
    } catch {
      // ignore cleanup errors
    }
  })
})

describe('resolveSessionContext', () => {
  it('resolves from payload fields', () => {
    const ctx = resolveSessionContext(
      { workspace_id: 'ws-payload' },
      { authorization: 'Bearer tok-123' },
      { BORING_BACKEND_URL: 'http://backend:9000' },
    )
    assert.equal(ctx.workspaceId, 'ws-payload')
    assert.equal(ctx.internalApiToken, 'tok-123')
    assert.equal(ctx.backendUrl, 'http://backend:9000')
  })

  it('falls back to env for backend URL', () => {
    const ctx = resolveSessionContext({}, {}, { BORING_BACKEND_URL: 'http://env:8000' })
    assert.equal(ctx.backendUrl, 'http://env:8000')
  })

  it('defaults backend URL to localhost', () => {
    const ctx = resolveSessionContext({}, {}, {})
    assert.equal(ctx.backendUrl, 'http://127.0.0.1:8000')
  })

  it('extracts bearer token from authorization header', () => {
    const ctx = resolveSessionContext({}, { authorization: 'Bearer my-token' }, {})
    assert.equal(ctx.internalApiToken, 'my-token')
  })

  it('handles missing/empty values gracefully', () => {
    const ctx = resolveSessionContext({}, {}, {})
    assert.equal(ctx.workspaceId, '')
    assert.equal(ctx.internalApiToken, '')
  })
})

describe('buildSessionSystemPrompt', () => {
  it('includes base prompt', () => {
    const prompt = buildSessionSystemPrompt('You are a helpful assistant.')
    assert.match(prompt, /helpful assistant/)
  })

  it('includes workspace root reference', () => {
    const prompt = buildSessionSystemPrompt('Base prompt.')
    assert.match(prompt, /Workspace root:/)
  })

  it('mentions direct access', () => {
    const prompt = buildSessionSystemPrompt('Base.')
    assert.match(prompt, /direct filesystem/)
  })
})
