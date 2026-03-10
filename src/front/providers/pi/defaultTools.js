import { Type } from '@sinclair/typebox'
import { queryKeys } from '../data'
import { PI_LIST_TABS_BRIDGE, PI_OPEN_FILE_BRIDGE } from './uiBridge'

const CANONICAL_GIT_CODES = new Set(['M', 'U', 'A', 'D', 'C'])

const textResult = (text) => ({
  content: [{ type: 'text', text }],
  details: {},
})

const normalizePath = (path, fallback = '.') => {
  const trimmed = String(path || '').trim().replace(/^\/+/, '')
  return trimmed || fallback
}

const normalizeFilePath = (path) => normalizePath(path, '')

const invalidateFileAndGitQueries = async (queryClient) => {
  if (!queryClient) return
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: queryKeys.files.all }),
    queryClient.invalidateQueries({ queryKey: queryKeys.git.all }),
  ])
}

const formatDirEntries = (entries) => {
  if (!Array.isArray(entries) || entries.length === 0) return '(empty)'
  return entries
    .slice()
    .sort((a, b) => String(a?.name || '').localeCompare(String(b?.name || '')))
    .map((entry) => {
      const name = String(entry?.name || entry?.path || '')
      return entry?.is_dir ? `${name}/` : name
    })
    .join('\n')
}

const listDirRecursive = async (provider, dirPath) => {
  const current = normalizePath(dirPath)
  const entries = await provider.files.list(current)
  const out = []

  for (const entry of entries) {
    const entryPath = normalizeFilePath(
      entry?.path || (current === '.' ? entry?.name : `${current}/${entry?.name || ''}`),
    )
    if (!entryPath) continue

    if (entry?.is_dir) {
      out.push(`${entryPath}/`)
      const sub = await listDirRecursive(provider, entryPath)
      out.push(...sub)
    } else {
      out.push(entryPath)
    }
  }

  return out
}

const normalizeGitEntries = (payload) => {
  const files = payload?.files
  if (Array.isArray(files)) {
    return files
      .map((entry) => ({
        path: String(entry?.path || ''),
        status: String(entry?.status || '').toUpperCase(),
      }))
      .filter((entry) => entry.path && CANONICAL_GIT_CODES.has(entry.status))
  }

  if (files && typeof files === 'object') {
    return Object.entries(files)
      .map(([path, status]) => ({
        path: String(path || ''),
        status: String(status || '').toUpperCase(),
      }))
      .filter((entry) => entry.path && CANONICAL_GIT_CODES.has(entry.status))
  }

  return []
}

const resolvePythonRunner = (provider) => {
  if (typeof provider?.runPython === 'function') return provider.runPython.bind(provider)
  if (typeof provider?.python?.run === 'function') return provider.python.run.bind(provider.python)
  return null
}

const resolveCommandRunner = (provider) => {
  if (typeof provider?.runCommand === 'function') return provider.runCommand.bind(provider)
  if (typeof provider?.shell?.run === 'function') return provider.shell.run.bind(provider.shell)
  if (typeof provider?.bash?.run === 'function') return provider.bash.run.bind(provider.bash)
  return null
}

const formatPythonResult = (result) => {
  if (result === null || result === undefined) return ''
  if (typeof result === 'string') return result

  const stdout = typeof result?.stdout === 'string' ? result.stdout : ''
  const stderr = typeof result?.stderr === 'string' ? result.stderr : ''
  if (stdout || stderr) {
    if (stdout && stderr) return `${stdout}\n[stderr]\n${stderr}`
    return stdout || stderr
  }

  try {
    return JSON.stringify(result, null, 2)
  } catch {
    return String(result)
  }
}

const formatCommandResult = (result) => {
  if (result === null || result === undefined) return ''
  if (typeof result === 'string') return result

  const stdout = typeof result?.stdout === 'string'
    ? result.stdout
    : (typeof result?.output === 'string' ? result.output : '')
  const stderr = typeof result?.stderr === 'string' ? result.stderr : ''
  const exitCode = Number.isFinite(result?.exitCode)
    ? Number(result.exitCode)
    : (Number.isFinite(result?.status) ? Number(result.status) : null)

  const chunks = []
  if (stdout) chunks.push(stdout)
  if (stderr) chunks.push(`[stderr]\n${stderr}`)
  if (exitCode !== null && exitCode !== 0) chunks.push(`[exit_code] ${exitCode}`)
  if (chunks.length > 0) return chunks.join('\n')

  try {
    return JSON.stringify(result, null, 2)
  } catch {
    return String(result)
  }
}

const createExecBashTool = (runCommand, queryClient) => ({
  name: 'exec_bash',
  label: 'Exec Bash',
  description: 'Execute a shell command in the active backend runtime.',
  parameters: Type.Object({
    command: Type.String({ description: 'Shell command to execute' }),
    cwd: Type.Optional(Type.String({ description: 'Optional working directory (relative path)' })),
  }),
  execute: async (_toolCallId, params) => {
    const command = String(params?.command || '').trim()
    const cwd = params?.cwd !== undefined ? normalizePath(params.cwd) : undefined
    if (!command) return textResult('Error: command is required')
    try {
      const result = await runCommand(command, { cwd })
      await invalidateFileAndGitQueries(queryClient)
      return textResult(formatCommandResult(result) || '(no output)')
    } catch (error) {
      return textResult(`Error running command: ${error?.message || String(error)}`)
    }
  },
})

const getOpenFileBridge = () => {
  if (typeof window === 'undefined') return null
  const maybeFn = window[PI_OPEN_FILE_BRIDGE]
  return typeof maybeFn === 'function' ? maybeFn : null
}

const getListTabsBridge = () => {
  if (typeof window === 'undefined') return null
  const maybeFn = window[PI_LIST_TABS_BRIDGE]
  return typeof maybeFn === 'function' ? maybeFn : null
}

const formatTabsResult = (tabs, activeFile) => {
  if (!Array.isArray(tabs) || tabs.length === 0) return 'No open tabs'
  const lines = tabs.map((path) => (path === activeFile ? `* ${path}` : `  ${path}`))
  return lines.join('\n')
}

const createOpenFileTool = () => ({
  name: 'open_file',
  label: 'Open File',
  description: 'Open a file in the editor panel using a path relative to project root.',
  parameters: Type.Object({
    path: Type.String({ description: 'Relative file path (e.g. hello.txt or src/main.py)' }),
  }),
  execute: async (_toolCallId, params) => {
    const openFile = getOpenFileBridge()
    if (!openFile) return textResult('Error opening file: UI bridge unavailable')
    const path = normalizeFilePath(params.path)
    if (!path) return textResult('Error: path is required')
    try {
      const opened = openFile(path)
      if (opened === false) return textResult(`Error opening file: ${path}`)
      return textResult(`Opening ${path} in editor`)
    } catch (error) {
      return textResult(`Error opening file: ${error?.message || String(error)}`)
    }
  },
})

const createListTabsTool = () => ({
  name: 'list_tabs',
  label: 'List Tabs',
  description: 'List currently open editor tabs in the UI.',
  parameters: Type.Object({}),
  execute: async () => {
    const listTabs = getListTabsBridge()
    if (!listTabs) return textResult('Error listing tabs: UI bridge unavailable')
    try {
      const payload = listTabs() || {}
      const tabs = Array.isArray(payload.tabs) ? payload.tabs : []
      const activeFile = typeof payload.activeFile === 'string' ? payload.activeFile : ''
      const rows = tabs.map((path) => ({ path, active: path === activeFile }))
      return {
        content: [{ type: 'text', text: formatTabsResult(tabs, activeFile) }],
        details: {
          tabs: rows,
          active_file: activeFile,
        },
      }
    } catch (error) {
      return textResult(`Error listing tabs: ${error?.message || String(error)}`)
    }
  },
})

export function createPiNativeUiTools() {
  return [createOpenFileTool(), createListTabsTool()]
}

function createPiCoreTools(provider, queryClient, { includeUi = false } = {}) {
  const runCommand = resolveCommandRunner(provider)
  const hasFiles = Boolean(provider?.files)
  const bashOnly = Boolean(provider?.pi?.bashOnly)

  if (!hasFiles && !runCommand) return includeUi ? createPiNativeUiTools() : []

  if (bashOnly) {
    const tools = []
    if (runCommand) tools.push(createExecBashTool(runCommand, queryClient))
    return tools
  }

  if (!hasFiles) {
    const tools = []
    if (runCommand) tools.push(createExecBashTool(runCommand, queryClient))
    if (includeUi) tools.push(...createPiNativeUiTools())
    return tools
  }

  const tools = [
    {
      name: 'read_file',
      label: 'Read File',
      description: 'Read the contents of a file at the given path (relative to project root).',
      parameters: Type.Object({
        path: Type.String({ description: 'Relative file path (e.g. hello.txt or src/main.py)' }),
      }),
      execute: async (_toolCallId, params) => {
        const path = normalizeFilePath(params.path)
        if (!path) return textResult('Error: path is required')
        try {
          const content = await provider.files.read(path)
          return textResult(content)
        } catch (error) {
          return textResult(`Error reading ${path}: ${error?.message || String(error)}`)
        }
      },
    },

    {
      name: 'write_file',
      label: 'Write File',
      description: 'Write content to a file (relative path). Creates the file if it does not exist.',
      parameters: Type.Object({
        path: Type.String({ description: 'Relative file path' }),
        content: Type.String({ description: 'Content to write' }),
      }),
      execute: async (_toolCallId, params) => {
        const path = normalizeFilePath(params.path)
        if (!path) return textResult('Error: path is required')
        try {
          await provider.files.write(path, params.content ?? '')
          await invalidateFileAndGitQueries(queryClient)
          return textResult(`Wrote ${String(params.content || '').length} bytes to ${path}`)
        } catch (error) {
          return textResult(`Error writing ${path}: ${error?.message || String(error)}`)
        }
      },
    },

    {
      name: 'list_dir',
      label: 'List Directory',
      description: 'List files and directories at a relative path.',
      parameters: Type.Object({
        path: Type.Optional(Type.String({ description: 'Relative directory path (default: project root)', default: '.' })),
        recursive: Type.Optional(Type.Boolean({ description: 'List recursively', default: false })),
      }),
      execute: async (_toolCallId, params) => {
        const path = normalizePath(params.path)
        try {
          if (params.recursive) {
            const recursiveEntries = await listDirRecursive(provider, path)
            return textResult(recursiveEntries.join('\n') || '(empty)')
          }

          const entries = await provider.files.list(path)
          return textResult(formatDirEntries(entries))
        } catch (error) {
          return textResult(`Error listing ${path}: ${error?.message || String(error)}`)
        }
      },
    },

    {
      name: 'delete',
      label: 'Delete',
      description: 'Delete a file or directory recursively at a relative path.',
      parameters: Type.Object({
        path: Type.String({ description: 'Relative path to delete' }),
      }),
      execute: async (_toolCallId, params) => {
        const path = normalizeFilePath(params.path)
        if (!path) return textResult('Error: path is required')
        try {
          await provider.files.delete(path)
          await invalidateFileAndGitQueries(queryClient)
          return textResult(`Deleted ${path}`)
        } catch (error) {
          return textResult(`Error deleting ${path}: ${error?.message || String(error)}`)
        }
      },
    },

    {
      name: 'rename_file',
      label: 'Rename File',
      description: 'Rename a file within its current directory.',
      parameters: Type.Object({
        old_path: Type.String({ description: 'Existing relative file path' }),
        new_name: Type.String({ description: 'New file name (not a full path)' }),
      }),
      execute: async (_toolCallId, params) => {
        const oldPath = normalizeFilePath(params.old_path)
        const newName = String(params.new_name || '').trim()
        if (!oldPath || !newName) return textResult('Error: old_path and new_name are required')
        try {
          await provider.files.rename(oldPath, newName)
          await invalidateFileAndGitQueries(queryClient)
          return textResult(`Renamed ${oldPath} to ${newName}`)
        } catch (error) {
          return textResult(`Error renaming ${oldPath}: ${error?.message || String(error)}`)
        }
      },
    },

    {
      name: 'move_file',
      label: 'Move File',
      description: 'Move a file to a destination directory (relative path).',
      parameters: Type.Object({
        src_path: Type.String({ description: 'Source relative file path' }),
        dest_dir: Type.String({ description: 'Destination relative directory path' }),
      }),
      execute: async (_toolCallId, params) => {
        const srcPath = normalizeFilePath(params.src_path)
        const destDir = normalizePath(params.dest_dir)
        if (!srcPath) return textResult('Error: src_path is required')
        try {
          await provider.files.move(srcPath, destDir)
          await invalidateFileAndGitQueries(queryClient)
          return textResult(`Moved ${srcPath} to ${destDir}`)
        } catch (error) {
          return textResult(`Error moving ${srcPath}: ${error?.message || String(error)}`)
        }
      },
    },

    {
      name: 'search_files',
      label: 'Search Files',
      description: 'Search files by name/content metadata using a query string.',
      parameters: Type.Object({
        query: Type.String({ description: 'Search query' }),
      }),
      execute: async (_toolCallId, params) => {
        const query = String(params.query || '').trim()
        if (!query) return textResult('(empty query)')
        if (typeof provider.files.search !== 'function') {
          return textResult('Error searching files: provider.files.search is unavailable')
        }
        try {
          const results = await provider.files.search(query)
          if (!Array.isArray(results) || results.length === 0) return textResult('No matches')
          const lines = results.map((result) => String(result?.path || result?.name || '')).filter(Boolean)
          return textResult(lines.join('\n') || 'No matches')
        } catch (error) {
          return textResult(`Error searching files: ${error?.message || String(error)}`)
        }
      },
    },
  ]

  if (includeUi) {
    tools.push(...createPiNativeUiTools())
  }

  if (provider.git) {
    tools.push(
      {
        name: 'git_status',
        label: 'Git Status',
        description: 'Show working tree status with canonical git status codes (M/U/A/D/C).',
        parameters: Type.Object({}),
        execute: async () => {
          try {
            const payload = await provider.git.status()
            if (payload?.available === false) return textResult('Git not available')
            if (payload?.is_repo === false) return textResult('Not a git repository')

            const entries = normalizeGitEntries(payload)
            if (entries.length === 0) return textResult('Clean working tree')
            const lines = entries
              .sort((a, b) => a.path.localeCompare(b.path))
              .map((entry) => `${entry.status} ${entry.path}`)
            return textResult(lines.join('\n'))
          } catch (error) {
            return textResult(`Error: ${error?.message || String(error)}`)
          }
        },
      },

      {
        name: 'git_diff',
        label: 'Git Diff',
        description: 'Show git diff for a file path.',
        parameters: Type.Object({
          path: Type.String({ description: 'Relative file path' }),
        }),
        execute: async (_toolCallId, params) => {
          const path = normalizeFilePath(params.path)
          if (!path) return textResult('Error: path is required')
          try {
            const diff = await provider.git.diff(path)
            return textResult(diff || '(no diff)')
          } catch (error) {
            return textResult(`Error diffing ${path}: ${error?.message || String(error)}`)
          }
        },
      },

      {
        name: 'git_show',
        label: 'Git Show',
        description: 'Show file content from HEAD for a relative path.',
        parameters: Type.Object({
          path: Type.String({ description: 'Relative file path' }),
        }),
        execute: async (_toolCallId, params) => {
          const path = normalizeFilePath(params.path)
          if (!path) return textResult('Error: path is required')
          try {
            const content = await provider.git.show(path)
            return textResult(content || '(empty)')
          } catch (error) {
            return textResult(`Error showing ${path}: ${error?.message || String(error)}`)
          }
        },
      },

      // ── Write operations ──────────────────────────────────────────────

      {
        name: 'git_add',
        label: 'Git Add',
        description: 'Stage files for commit. Pass specific paths or omit to stage all changes.',
        parameters: Type.Object({
          paths: Type.Optional(Type.Array(Type.String(), { description: 'File paths to stage (omit to stage all)' })),
        }),
        execute: async (_toolCallId, params) => {
          try {
            const paths = Array.isArray(params?.paths) && params.paths.length > 0 ? params.paths : undefined
            await provider.git.add(paths)
            await invalidateFileAndGitQueries(queryClient)
            return textResult(paths ? `Staged ${paths.length} file(s)` : 'Staged all changes')
          } catch (error) {
            return textResult(`Error staging files: ${error?.message || String(error)}`)
          }
        },
      },

      {
        name: 'git_commit',
        label: 'Git Commit',
        description: 'Create a commit with the currently staged changes.',
        parameters: Type.Object({
          message: Type.String({ description: 'Commit message' }),
        }),
        execute: async (_toolCallId, params) => {
          const message = String(params?.message || '').trim()
          if (!message) return textResult('Error: message is required')
          try {
            const result = await provider.git.commit(message)
            await invalidateFileAndGitQueries(queryClient)
            return textResult(`Committed: ${result?.oid || '(ok)'}`)
          } catch (error) {
            return textResult(`Error committing: ${error?.message || String(error)}`)
          }
        },
      },

      {
        name: 'git_push',
        label: 'Git Push',
        description: 'Push commits to a remote repository.',
        parameters: Type.Object({
          remote: Type.Optional(Type.String({ description: 'Remote name (default: origin)' })),
          branch: Type.Optional(Type.String({ description: 'Branch to push' })),
        }),
        execute: async (_toolCallId, params) => {
          try {
            await provider.git.push({ remote: params?.remote, branch: params?.branch })
            return textResult('Pushed successfully')
          } catch (error) {
            return textResult(`Error pushing: ${error?.message || String(error)}`)
          }
        },
      },

      {
        name: 'git_pull',
        label: 'Git Pull',
        description: 'Pull changes from a remote repository.',
        parameters: Type.Object({
          remote: Type.Optional(Type.String({ description: 'Remote name (default: origin)' })),
          branch: Type.Optional(Type.String({ description: 'Branch to pull' })),
        }),
        execute: async (_toolCallId, params) => {
          try {
            await provider.git.pull({ remote: params?.remote, branch: params?.branch })
            await invalidateFileAndGitQueries(queryClient)
            return textResult('Pulled successfully')
          } catch (error) {
            return textResult(`Error pulling: ${error?.message || String(error)}`)
          }
        },
      },

      {
        name: 'git_init',
        label: 'Git Init',
        description: 'Initialize a new git repository in the workspace.',
        parameters: Type.Object({}),
        execute: async () => {
          try {
            await provider.git.init()
            await invalidateFileAndGitQueries(queryClient)
            return textResult('Initialized git repository')
          } catch (error) {
            return textResult(`Error initializing: ${error?.message || String(error)}`)
          }
        },
      },

      // ── Branch operations ─────────────────────────────────────────────

      {
        name: 'git_branches',
        label: 'Git Branches',
        description: 'List all local branches and show the current branch.',
        parameters: Type.Object({}),
        execute: async () => {
          try {
            if (typeof provider.git.branches !== 'function') {
              return textResult('Branch operations not available')
            }
            const { branches, current } = await provider.git.branches()
            if (!branches || branches.length === 0) return textResult('No branches')
            const lines = branches.map((b) => (b === current ? `* ${b}` : `  ${b}`))
            return textResult(lines.join('\n'))
          } catch (error) {
            return textResult(`Error listing branches: ${error?.message || String(error)}`)
          }
        },
      },

      {
        name: 'git_create_branch',
        label: 'Create Branch',
        description: 'Create a new git branch. Optionally switch to it.',
        parameters: Type.Object({
          name: Type.String({ description: 'New branch name' }),
          checkout: Type.Optional(Type.Boolean({ description: 'Switch to the new branch (default: true)', default: true })),
        }),
        execute: async (_toolCallId, params) => {
          const name = String(params?.name || '').trim()
          if (!name) return textResult('Error: name is required')
          try {
            if (typeof provider.git.createBranch !== 'function') {
              return textResult('Branch operations not available')
            }
            const checkout = params?.checkout !== false
            await provider.git.createBranch(name, checkout)
            await invalidateFileAndGitQueries(queryClient)
            return textResult(checkout ? `Created and switched to branch '${name}'` : `Created branch '${name}'`)
          } catch (error) {
            return textResult(`Error creating branch: ${error?.message || String(error)}`)
          }
        },
      },

      {
        name: 'git_checkout',
        label: 'Git Checkout',
        description: 'Switch to an existing branch.',
        parameters: Type.Object({
          name: Type.String({ description: 'Branch name to checkout' }),
        }),
        execute: async (_toolCallId, params) => {
          const name = String(params?.name || '').trim()
          if (!name) return textResult('Error: name is required')
          try {
            if (typeof provider.git.checkout !== 'function') {
              return textResult('Branch operations not available')
            }
            await provider.git.checkout(name)
            await invalidateFileAndGitQueries(queryClient)
            return textResult(`Switched to branch '${name}'`)
          } catch (error) {
            return textResult(`Error checking out: ${error?.message || String(error)}`)
          }
        },
      },

      {
        name: 'git_merge',
        label: 'Git Merge',
        description: 'Merge a branch into the current branch.',
        parameters: Type.Object({
          source: Type.String({ description: 'Branch to merge from' }),
          message: Type.Optional(Type.String({ description: 'Merge commit message' })),
        }),
        execute: async (_toolCallId, params) => {
          const source = String(params?.source || '').trim()
          if (!source) return textResult('Error: source branch is required')
          try {
            if (typeof provider.git.merge !== 'function') {
              return textResult('Branch operations not available')
            }
            await provider.git.merge(source, params?.message)
            await invalidateFileAndGitQueries(queryClient)
            return textResult(`Merged '${source}' into current branch`)
          } catch (error) {
            return textResult(`Error merging: ${error?.message || String(error)}`)
          }
        },
      },
    )
  }

  const runPython = resolvePythonRunner(provider)
  if (runPython) {
    tools.push({
      name: 'python_exec',
      label: 'Run Python',
      description: 'Execute Python code or run a Python file path using the active backend runtime.',
      parameters: Type.Object({
        code: Type.Optional(Type.String({ description: 'Python source code to execute' })),
        path: Type.Optional(Type.String({ description: 'Relative Python file path to execute (e.g. scripts/main.py)' })),
        cwd: Type.Optional(Type.String({ description: 'Optional working directory (relative path)' })),
      }),
      execute: async (_toolCallId, params) => {
        const code = String(params?.code || '')
        const path = normalizeFilePath(params?.path)
        const cwd = params?.cwd !== undefined ? normalizePath(params.cwd) : undefined
        if (!code.trim() && !path) return textResult('Error: provide code or path')
        try {
          const result = await runPython(code, { path, cwd })
          await invalidateFileAndGitQueries(queryClient)
          return textResult(formatPythonResult(result) || '(no output)')
        } catch (error) {
          return textResult(`Error running python: ${error?.message || String(error)}`)
        }
      },
    })
  }

  if (runCommand) {
    tools.push(createExecBashTool(runCommand, queryClient))
  }

  return tools
}

export function createPiDefaultTools(provider, queryClient) {
  return createPiCoreTools(provider, queryClient, { includeUi: true })
}

export function createPiFilesystemTools(provider, queryClient) {
  return createPiCoreTools(provider, queryClient)
}

export function createPiNativeTools(provider, queryClient) {
  return createPiDefaultTools(provider, queryClient)
}

export function mergePiTools(defaultTools, configuredTools) {
  const merged = new Map()
  for (const tool of defaultTools || []) {
    const name = String(tool?.name || '').trim()
    if (!name) continue
    merged.set(name, tool)
  }
  for (const tool of configuredTools || []) {
    const name = String(tool?.name || '').trim()
    if (!name) continue
    merged.set(name, tool)
  }
  return [...merged.values()]
}
