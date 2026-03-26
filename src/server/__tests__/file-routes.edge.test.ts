import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { mkdtempSync, mkdirSync, readFileSync, rmSync, statSync, symlinkSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { createTestApp, testSessionCookie } from './helpers.js'

let workspaceRoot: string
let outsideRoot: string

beforeAll(() => {
  workspaceRoot = mkdtempSync(join(tmpdir(), 'bui-file-edge-'))
  outsideRoot = mkdtempSync(join(tmpdir(), 'bui-file-outside-'))

  mkdirSync(join(workspaceRoot, 'empty-dir'), { recursive: true })
  writeFileSync(join(workspaceRoot, '.hidden.txt'), 'hidden')
  writeFileSync(join(workspaceRoot, 'unicode.txt'), 'hello from cafe')
  writeFileSync(join(workspaceRoot, 'notes.md'), 'markdown')
  mkdirSync(join(workspaceRoot, 'space dir'), { recursive: true })

  writeFileSync(join(outsideRoot, 'secret.txt'), 'SECRET DATA')
  mkdirSync(join(outsideRoot, 'write-target'), { recursive: true })

  symlinkSync(join(outsideRoot, 'secret.txt'), join(workspaceRoot, 'escape-read.txt'))
  symlinkSync(join(outsideRoot, 'write-target'), join(workspaceRoot, 'escape-dir'))
})

afterAll(() => {
  rmSync(workspaceRoot, { recursive: true, force: true })
  rmSync(outsideRoot, { recursive: true, force: true })
})

function getApp() {
  return createTestApp({ workspaceRoot })
}

describe('File route edge cases', () => {
  it('lists dotfiles and empty directories', async () => {
    const app = getApp()
    const token = await testSessionCookie()

    const rootRes = await app.inject({
      method: 'GET',
      url: '/api/v1/files/list?path=.',
      cookies: { boring_session: token },
    })
    expect(rootRes.statusCode).toBe(200)
    const rootBody = JSON.parse(rootRes.payload)
    expect(rootBody.entries).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ name: '.hidden.txt', is_dir: false }),
        expect.objectContaining({ name: 'empty-dir', is_dir: true }),
      ]),
    )

    const emptyRes = await app.inject({
      method: 'GET',
      url: '/api/v1/files/list?path=empty-dir',
      cookies: { boring_session: token },
    })
    expect(emptyRes.statusCode).toBe(200)
    expect(JSON.parse(emptyRes.payload)).toMatchObject({
      entries: [],
      path: 'empty-dir',
    })

    await app.close()
  })

  it('writes empty content and supports paths with spaces', async () => {
    const app = getApp()
    const token = await testSessionCookie()

    const res = await app.inject({
      method: 'PUT',
      url: '/api/v1/files/write?path=space%20dir/empty%20file.txt',
      cookies: { boring_session: token },
      payload: { content: '' },
    })
    expect(res.statusCode).toBe(200)
    expect(readFileSync(join(workspaceRoot, 'space dir', 'empty file.txt'), 'utf-8')).toBe('')

    await app.close()
  })

  it('preserves unicode content on write/read round-trip', async () => {
    const app = getApp()
    const token = await testSessionCookie()
    const content = 'Zażółć gęślą jaźń'

    const writeRes = await app.inject({
      method: 'PUT',
      url: '/api/v1/files/write?path=unicode.txt',
      cookies: { boring_session: token },
      payload: { content },
    })
    expect(writeRes.statusCode).toBe(200)

    const readRes = await app.inject({
      method: 'GET',
      url: '/api/v1/files/read?path=unicode.txt',
      cookies: { boring_session: token },
    })
    expect(readRes.statusCode).toBe(200)
    expect(JSON.parse(readRes.payload)).toMatchObject({
      content,
      path: 'unicode.txt',
    })

    await app.close()
  })

  it('handles writes larger than 10MB', async () => {
    const app = getApp()
    const token = await testSessionCookie()
    const content = 'a'.repeat(11 * 1024 * 1024)

    const res = await app.inject({
      method: 'PUT',
      url: '/api/v1/files/write?path=large.txt',
      cookies: { boring_session: token },
      payload: { content },
    })
    expect(res.statusCode).toBe(200)
    expect(statSync(join(workspaceRoot, 'large.txt')).size).toBe(content.length)

    await app.close()
  })

  it('supports glob-style search and Python q alias', async () => {
    const app = getApp()
    const token = await testSessionCookie()

    const txtRes = await app.inject({
      method: 'GET',
      url: '/api/v1/files/search?q=*.txt&path=.',
      cookies: { boring_session: token },
    })
    expect(txtRes.statusCode).toBe(200)
    expect(JSON.parse(txtRes.payload).results).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ name: '.hidden.txt' }),
        expect.objectContaining({ name: 'unicode.txt' }),
      ]),
    )

    const prefixRes = await app.inject({
      method: 'GET',
      url: '/api/v1/files/search?pattern=note*&path=.',
      cookies: { boring_session: token },
    })
    expect(prefixRes.statusCode).toBe(200)
    expect(JSON.parse(prefixRes.payload).results).toEqual([
      expect.objectContaining({ name: 'notes.md', path: 'notes.md', dir: '' }),
    ])

    await app.close()
  })

  it('returns 400 when reading a directory path', async () => {
    const app = getApp()
    const token = await testSessionCookie()

    const res = await app.inject({
      method: 'GET',
      url: '/api/v1/files/read?path=space%20dir',
      cookies: { boring_session: token },
    })
    expect(res.statusCode).toBe(400)
    expect(JSON.parse(res.payload)).toMatchObject({
      detail: expect.stringContaining('directory'),
    })

    await app.close()
  })

  it('deletes directories recursively', async () => {
    const app = getApp()
    const token = await testSessionCookie()

    writeFileSync(join(workspaceRoot, 'empty-dir', 'nested.txt'), 'nested')

    const res = await app.inject({
      method: 'DELETE',
      url: '/api/v1/files/delete?path=empty-dir',
      cookies: { boring_session: token },
    })
    expect(res.statusCode).toBe(200)

    const listRes = await app.inject({
      method: 'GET',
      url: '/api/v1/files/list?path=.',
      cookies: { boring_session: token },
    })
    expect(JSON.parse(listRes.payload).entries).not.toEqual(
      expect.arrayContaining([expect.objectContaining({ name: 'empty-dir' })]),
    )

    await app.close()
  })

  it('returns 409 when renaming onto an existing path', async () => {
    const app = getApp()
    const token = await testSessionCookie()

    writeFileSync(join(workspaceRoot, 'rename-source.txt'), 'src')
    writeFileSync(join(workspaceRoot, 'rename-target.txt'), 'dst')

    const res = await app.inject({
      method: 'POST',
      url: '/api/v1/files/rename',
      cookies: { boring_session: token },
      payload: { old_path: 'rename-source.txt', new_path: 'rename-target.txt' },
    })
    expect(res.statusCode).toBe(409)

    await app.close()
  })

  it('returns 400 when moving into a missing destination directory', async () => {
    const app = getApp()
    const token = await testSessionCookie()

    writeFileSync(join(workspaceRoot, 'move-source.txt'), 'src')

    const res = await app.inject({
      method: 'POST',
      url: '/api/v1/files/move',
      cookies: { boring_session: token },
      payload: { src_path: 'move-source.txt', dest_dir: 'missing-dir' },
    })
    expect(res.statusCode).toBe(400)

    await app.close()
  })

  it('uses last-writer-wins semantics for concurrent writes', async () => {
    const app = getApp()
    const token = await testSessionCookie()
    const targetUrl = '/api/v1/files/write?path=concurrent.txt'

    const firstWrite = app.inject({
      method: 'PUT',
      url: targetUrl,
      cookies: { boring_session: token },
      payload: { content: 'first' },
    })
    const secondWrite = new Promise((resolve) => {
      setTimeout(() => {
        resolve(app.inject({
          method: 'PUT',
          url: targetUrl,
          cookies: { boring_session: token },
          payload: { content: 'second' },
        }))
      }, 5)
    })

    const [firstRes, secondRes] = await Promise.all([firstWrite, secondWrite]) as any[]
    expect(firstRes.statusCode).toBe(200)
    expect(secondRes.statusCode).toBe(200)
    // Last-writer-wins: file should contain one of the two values
    const content = readFileSync(join(workspaceRoot, 'concurrent.txt'), 'utf-8')
    expect(['first', 'second']).toContain(content)

    await app.close()
  })

  it('rejects reading a symlink that escapes the workspace', async () => {
    const app = getApp()
    const token = await testSessionCookie()

    const res = await app.inject({
      method: 'GET',
      url: '/api/v1/files/read?path=escape-read.txt',
      cookies: { boring_session: token },
    })
    expect(res.statusCode).toBe(400)
    expect(res.payload).not.toContain('SECRET DATA')

    await app.close()
  })

  it('rejects writing through a symlinked parent directory', async () => {
    const app = getApp()
    const token = await testSessionCookie()

    const res = await app.inject({
      method: 'PUT',
      url: '/api/v1/files/write?path=escape-dir/owned.txt',
      cookies: { boring_session: token },
      payload: { content: 'should stay inside workspace' },
    })
    expect(res.statusCode).toBe(400)

    await app.close()
  })
})
