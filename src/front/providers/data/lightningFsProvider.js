/**
 * LightningFS-backed DataProvider (files only).
 *
 * Implements the FilesProvider contract from types.js using
 * @isomorphic-git/lightning-fs (IndexedDB storage).
 *
 * @module providers/data/lightningFsProvider
 */
import { pfs } from './lightningFs.js'

const throwIfAborted = (signal) => {
  if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')
}

const absPath = (relativePath) => {
  const trimmed = String(relativePath || '').trim()
  if (!trimmed || trimmed === '.') return '/'
  if (trimmed.startsWith('/')) return trimmed
  return `/${trimmed}`
}

const relPath = (absolutePath) => absolutePath.replace(/^\//, '')

const ensureParentDirs = async (fsApi, filePath, signal) => {
  const parts = filePath.split('/').filter(Boolean)
  let current = ''
  for (let i = 0; i < parts.length - 1; i += 1) {
    throwIfAborted(signal)
    current += `/${parts[i]}`
    try {
      await fsApi.stat(current)
    } catch {
      await fsApi.mkdir(current)
    }
  }
}

const removeRecursive = async (fsApi, targetPath, signal) => {
  throwIfAborted(signal)
  const stat = await fsApi.stat(targetPath)
  if (stat.isDirectory()) {
    const entries = await fsApi.readdir(targetPath)
    for (const entry of entries) {
      const child = targetPath === '/' ? `/${entry}` : `${targetPath}/${entry}`
      await removeRecursive(fsApi, child, signal)
    }
    await fsApi.rmdir(targetPath)
    return
  }
  await fsApi.unlink(targetPath)
}

const walkSearch = async (fsApi, dirPath, query, results, signal, limit = 500) => {
  if (results.length >= limit) return
  throwIfAborted(signal)

  let names = []
  try {
    names = await fsApi.readdir(dirPath)
  } catch {
    return
  }

  for (const name of names) {
    if (results.length >= limit) return
    throwIfAborted(signal)

    const full = dirPath === '/' ? `/${name}` : `${dirPath}/${name}`
    const stat = await fsApi.stat(full)
    const isDir = stat.isDirectory()

    if (name.toLowerCase().includes(query)) {
      results.push({ path: relPath(full), name, is_dir: isDir })
    }

    if (isDir) {
      await walkSearch(fsApi, full, query, results, signal, limit)
    }
  }
}

/**
 * Create a LightningFS-backed FilesProvider.
 *
 * @param {object} [fsApi] - Promisified fs API (defaults to shared pfs instance).
 * @returns {import('./types').FilesProvider}
 */
export const createLightningFsProvider = (fsApi = pfs) => ({
  list: async (dir, opts = {}) => {
    throwIfAborted(opts.signal)
    const dirPath = absPath(dir)
    const names = await fsApi.readdir(dirPath)
    const entries = []

    for (const name of names) {
      throwIfAborted(opts.signal)
      const full = dirPath === '/' ? `/${name}` : `${dirPath}/${name}`
      const stat = await fsApi.stat(full)
      entries.push({
        name,
        path: relPath(full),
        is_dir: stat.isDirectory(),
        size: stat.isFile() ? Number(stat.size || 0) : 0,
      })
    }
    return entries
  },

  read: async (path, opts = {}) => {
    throwIfAborted(opts.signal)
    const content = await fsApi.readFile(absPath(path), { encoding: 'utf8' })
    throwIfAborted(opts.signal)
    return typeof content === 'string' ? content : String(content || '')
  },

  write: async (path, content, opts = {}) => {
    throwIfAborted(opts.signal)
    const filePath = absPath(path)
    await ensureParentDirs(fsApi, filePath, opts.signal)
    await fsApi.writeFile(filePath, content ?? '', { encoding: 'utf8' })
  },

  delete: async (path, opts = {}) => {
    await removeRecursive(fsApi, absPath(path), opts.signal)
  },

  rename: async (oldPath, newName, opts = {}) => {
    throwIfAborted(opts.signal)
    const source = absPath(oldPath)
    const parent = source.includes('/') ? source.slice(0, source.lastIndexOf('/')) : ''
    const destination = parent ? `${parent}/${newName}` : `/${newName}`
    await fsApi.rename(source, destination)
  },

  move: async (srcPath, destPath, opts = {}) => {
    throwIfAborted(opts.signal)
    const source = absPath(srcPath)
    const destinationDir = absPath(destPath)
    const filename = source.split('/').filter(Boolean).pop()
    if (!filename) throw new Error('Invalid source path')
    const destination = destinationDir === '/' ? `/${filename}` : `${destinationDir}/${filename}`
    await fsApi.rename(source, destination)
  },

  search: async (query, opts = {}) => {
    throwIfAborted(opts.signal)
    const normalized = String(query || '').trim().toLowerCase()
    if (!normalized) return []
    const results = []
    await walkSearch(fsApi, '/', normalized, results, opts.signal)
    return results
  },
})
