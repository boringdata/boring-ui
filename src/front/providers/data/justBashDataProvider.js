/**
 * JustBash-backed DataProvider.
 *
 * Browser-only, in-memory workspace with shell builtins via just-bash.
 * Files persist for the lifetime of the provider instance only.
 */
import { Bash } from 'just-bash/browser'

const WORKSPACE_ROOT = '/home/user'
const UNSUPPORTED_GIT_MESSAGE = 'Git is unavailable for the justbash backend.'
const UNSUPPORTED_PACKAGE_MANAGER_MESSAGE = 'Package installation is unavailable for the justbash backend.'
const textDecoder = new TextDecoder()

const throwIfAborted = (signal) => {
  if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')
}

const normalizeRelativePath = (input, fallback = '.') => {
  const value = String(input || '').trim().replace(/^\/+/, '')
  return value || fallback
}

const toAbsolutePath = (relativePath, fallback = '.') => {
  const normalized = normalizeRelativePath(relativePath, fallback)
  if (!normalized || normalized === '.') return WORKSPACE_ROOT
  return `${WORKSPACE_ROOT}/${normalized}`
}

const toRelativePath = (absolutePath) => {
  const value = String(absolutePath || '').trim()
  if (!value || value === WORKSPACE_ROOT) return ''
  if (value.startsWith(`${WORKSPACE_ROOT}/`)) return value.slice(WORKSPACE_ROOT.length + 1)
  return value.replace(/^\/+/, '')
}

const decodePrintableByteString = (value) => {
  const trimmed = String(value || '').trim()
  if (!/^\d+(,\d+)+$/.test(trimmed)) return null

  const bytes = trimmed.split(',').map((part) => Number(part))
  if (bytes.length < 4 || bytes.some((part) => !Number.isInteger(part) || part < 0 || part > 255)) {
    return null
  }

  const decoded = textDecoder.decode(Uint8Array.from(bytes))
  const printable = [...decoded].every((char) => {
    const code = char.charCodeAt(0)
    return code === 9 || code === 10 || code === 13 || (code >= 32 && code <= 126)
  })

  return printable ? decoded : null
}

const normalizeShellText = (value) => {
  if (typeof value === 'string') return decodePrintableByteString(value) ?? value
  if (value instanceof Uint8Array) return textDecoder.decode(value)
  if (Array.isArray(value)) return textDecoder.decode(Uint8Array.from(value))
  if (ArrayBuffer.isView(value)) {
    return textDecoder.decode(new Uint8Array(value.buffer, value.byteOffset, value.byteLength))
  }
  if (value instanceof ArrayBuffer) return textDecoder.decode(new Uint8Array(value))
  return String(value ?? '')
}

const getUnsupportedCommandResult = (command) => {
  const trimmed = String(command || '').trim()
  if (!trimmed) return null

  if (/^git(?:\s|$)/i.test(trimmed)) {
    return {
      stdout: '',
      stderr: `${UNSUPPORTED_GIT_MESSAGE}\n`,
      exitCode: 127,
    }
  }

  if (
    /^(?:npm|pnpm|yarn|pip|pip3)(?:\s|$)/i.test(trimmed)
    || /^python(?:3)?\s+-m\s+pip(?:\s|$)/i.test(trimmed)
  ) {
    return {
      stdout: '',
      stderr: `${UNSUPPORTED_PACKAGE_MANAGER_MESSAGE}\n`,
      exitCode: 127,
    }
  }

  return null
}

const ensureParentDirs = async (fsApi, absolutePath, signal) => {
  const relative = toRelativePath(absolutePath)
  const parts = relative.split('/').filter(Boolean)
  let current = WORKSPACE_ROOT

  for (let i = 0; i < parts.length - 1; i += 1) {
    throwIfAborted(signal)
    current = `${current}/${parts[i]}`
    const exists = await fsApi.exists(current)
    if (!exists) {
      await fsApi.mkdir(current, { recursive: true })
    }
  }
}

const createUnsupportedGitProvider = () => {
  const unsupported = async () => {
    throw new Error(UNSUPPORTED_GIT_MESSAGE)
  }

  return {
    available: false,
    status: async () => ({
      available: false,
      is_repo: false,
      files: [],
    }),
    diff: unsupported,
    show: unsupported,
    init: unsupported,
    add: unsupported,
    commit: unsupported,
    push: unsupported,
    pull: unsupported,
    clone: unsupported,
    addRemote: unsupported,
    listRemotes: async () => [],
    branches: async () => ({ branches: [], current: null }),
    currentBranch: async () => null,
    createBranch: unsupported,
    checkout: unsupported,
    merge: unsupported,
  }
}

const walkSearch = async (fsApi, dirPath, query, results, signal, seen, limit = 200) => {
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

    const full = dirPath === WORKSPACE_ROOT ? `${WORKSPACE_ROOT}/${name}` : `${dirPath}/${name}`
    const stat = await fsApi.stat(full)
    const isDir = Boolean(stat?.isDirectory)
    const relativePath = toRelativePath(full)
    if (!relativePath) continue

    const lowerName = name.toLowerCase()
    const lowerPath = relativePath.toLowerCase()

    if ((lowerName.includes(query) || lowerPath.includes(query)) && !seen.has(relativePath)) {
      results.push({ path: relativePath, name, is_dir: isDir })
      seen.add(relativePath)
    }

    if (!isDir) {
      try {
        const content = await fsApi.readFile(full, { encoding: 'utf8' })
        const lines = String(content || '').split('\n')
        const matchIndex = lines.findIndex((line) => line.toLowerCase().includes(query))
        if (matchIndex !== -1 && !seen.has(relativePath)) {
          results.push({
            path: relativePath,
            name,
            is_dir: false,
            line: lines[matchIndex],
            line_number: matchIndex + 1,
          })
          seen.add(relativePath)
        }
      } catch {
        // Ignore unreadable/binary entries for search.
      }
      continue
    }

    await walkSearch(fsApi, full, query, results, signal, seen, limit)
  }
}

/**
 * Create a composed DataProvider backed by just-bash.
 *
 * @returns {import('./types').DataProvider}
 */
export const createJustBashDataProvider = () => {
  const bash = new Bash({ cwd: WORKSPACE_ROOT })
  const fsApi = bash.fs

  return {
    files: {
      list: async (dir, opts = {}) => {
        throwIfAborted(opts.signal)
        const dirPath = toAbsolutePath(dir, '.')
        const names = await fsApi.readdir(dirPath)
        const entries = []

        for (const name of names) {
          throwIfAborted(opts.signal)
          const full = dirPath === WORKSPACE_ROOT ? `${WORKSPACE_ROOT}/${name}` : `${dirPath}/${name}`
          const stat = await fsApi.stat(full)
          entries.push({
            name,
            path: toRelativePath(full),
            is_dir: Boolean(stat?.isDirectory),
            size: Number(stat?.size || 0),
            mtime: stat?.mtime instanceof Date ? stat.mtime.toISOString() : undefined,
          })
        }

        return entries
      },

      read: async (path, opts = {}) => {
        throwIfAborted(opts.signal)
        const content = await bash.readFile(toAbsolutePath(path, ''))
        return normalizeShellText(content)
      },

      write: async (path, content, opts = {}) => {
        throwIfAborted(opts.signal)
        const absolutePath = toAbsolutePath(path, '')
        await ensureParentDirs(fsApi, absolutePath, opts.signal)
        await bash.writeFile(absolutePath, String(content ?? ''))
      },

      delete: async (path, opts = {}) => {
        throwIfAborted(opts.signal)
        await fsApi.rm(toAbsolutePath(path, ''), { recursive: true, force: true })
      },

      rename: async (oldPath, newName, opts = {}) => {
        throwIfAborted(opts.signal)
        const source = toAbsolutePath(oldPath, '')
        const parent = source.includes('/') ? source.slice(0, source.lastIndexOf('/')) : WORKSPACE_ROOT
        const destination = `${parent}/${String(newName || '').trim()}`
        await fsApi.mv(source, destination)
      },

      move: async (srcPath, destPath, opts = {}) => {
        throwIfAborted(opts.signal)
        const source = toAbsolutePath(srcPath, '')
        const destinationDir = toAbsolutePath(destPath, '.')
        const filename = source.split('/').filter(Boolean).pop()
        if (!filename) throw new Error('Invalid source path')
        const destination = destinationDir === WORKSPACE_ROOT
          ? `${WORKSPACE_ROOT}/${filename}`
          : `${destinationDir}/${filename}`
        const destinationParent = destination.includes('/')
          ? destination.slice(0, destination.lastIndexOf('/'))
          : WORKSPACE_ROOT
        await fsApi.mkdir(destinationParent, { recursive: true })
        await fsApi.mv(source, destination)
      },

      search: async (query, opts = {}) => {
        throwIfAborted(opts.signal)
        const normalized = String(query || '').trim().toLowerCase()
        if (!normalized) return []
        const results = []
        const seen = new Set()
        const searchFsApi = {
          readdir: fsApi.readdir.bind(fsApi),
          stat: fsApi.stat.bind(fsApi),
          readFile: async (path) => {
            const content = await bash.readFile(path)
            return normalizeShellText(content)
          },
        }
        await walkSearch(
          searchFsApi,
          WORKSPACE_ROOT,
          normalized,
          results,
          opts.signal,
          seen,
        )
        return results
      },
    },

    git: createUnsupportedGitProvider(),

    runCommand: async (command, options = {}) => {
      const unsupported = getUnsupportedCommandResult(command)
      if (unsupported) return unsupported

      const cwd = toAbsolutePath(options?.cwd, '.')
      const result = await bash.exec(String(command || ''), {
        cwd,
        signal: options?.signal,
      })
      return {
        ...result,
        stdout: normalizeShellText(result.stdout),
        stderr: normalizeShellText(result.stderr),
      }
    },
  }
}
