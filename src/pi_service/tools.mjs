import { Type } from '@sinclair/typebox'
import { exec as execCb } from 'node:child_process'
import { promises as fs } from 'node:fs'
import path from 'node:path'
import { promisify } from 'node:util'

const execAsync = promisify(execCb)

const WORKSPACE_ROOT = process.env.BORING_UI_WORKSPACE_ROOT || process.cwd()
console.log(`[pi-tools] WORKSPACE_ROOT=${WORKSPACE_ROOT}`)

const textResult = (text, details = {}) => ({
  content: [{ type: 'text', text }],
  details,
})

const normalizePath = (value, fallback = '.') => {
  const trimmed = String(value || '').trim().replace(/^\/+/, '')
  return trimmed || fallback
}

const normalizeFilePath = (value) => normalizePath(value, '')

const resolveSafe = (relPath) => {
  const resolved = path.resolve(WORKSPACE_ROOT, relPath)
  if (!resolved.startsWith(path.resolve(WORKSPACE_ROOT))) {
    throw new Error('Path escapes workspace root')
  }
  return resolved
}

const formatDirEntries = (entries) => {
  if (!Array.isArray(entries) || entries.length === 0) return '(empty)'
  return entries
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((e) => (e.isDir ? `${e.name}/` : e.name))
    .join('\n')
}

const formatExecOutput = (result) => {
  const chunks = []
  if (result.stdout) chunks.push(result.stdout)
  if (result.stderr) chunks.push(`[stderr]\n${result.stderr}`)
  if (result.exitCode !== null && result.exitCode !== 0) chunks.push(`[exit_code] ${result.exitCode}`)
  return chunks.join('\n') || '(no output)'
}

// --- Session context (kept for API compatibility with server.mjs) ---

const normalizeWorkspaceId = (value) => String(value || '').trim()

const bearerTokenFromHeader = (authorization) => {
  const raw = String(authorization || '').trim()
  if (!raw) return ''
  const match = raw.match(/^Bearer\s+(.+)$/i)
  return match ? String(match[1] || '').trim() : ''
}

const normalizeBaseUrl = (value) => {
  const trimmed = String(value || '').trim().replace(/\/+$/, '')
  return trimmed || 'http://127.0.0.1:8000'
}

export function resolveSessionContext(payload = {}, headers = {}, env = process.env) {
  const workspaceId = normalizeWorkspaceId(
    payload.workspace_id
    || payload.workspaceId
    || headers['x-workspace-id']
    || headers['X-Workspace-Id']
    || '',
  )
  const internalApiToken = String(
    payload.internal_api_token
    || payload.internalApiToken
    || bearerTokenFromHeader(headers.authorization || headers.Authorization)
    || headers['x-boring-internal-token']
    || headers['X-Boring-Internal-Token']
    || env.BORING_INTERNAL_TOKEN
    || env.BORING_INTERNAL_API_TOKEN
    || env.BORING_UI_INTERNAL_TOKEN
    || ''
  ).trim()
  const backendUrl = normalizeBaseUrl(
    payload.backend_url
    || payload.backendUrl
    || headers['x-boring-backend-url']
    || headers['X-Boring-Backend-Url']
    || env.BORING_BACKEND_URL
  )

  return { workspaceId, internalApiToken, backendUrl }
}

export function buildSessionSystemPrompt(basePrompt, context = {}) {
  const prompt = String(basePrompt || '').trim()
  const sections = [prompt]
  sections.push(
    `Workspace root: ${WORKSPACE_ROOT}.`,
    'Use the available tools for file reads/writes, directory listing, git, and command execution.',
    'You have direct filesystem and shell access on this workspace VM.',
  )
  return sections.filter(Boolean).join(' ')
}

// --- Direct tools (no HTTP, runs on the workspace VM) ---

export function createWorkspaceTools(_context) {
  const tools = [
    {
      name: 'read_file',
      label: 'Read File',
      description: 'Read the contents of a file at a workspace-relative path.',
      parameters: Type.Object({
        path: Type.String({ description: 'Relative file path (e.g. README.md or src/main.py)' }),
      }),
      execute: async (_toolCallId, params) => {
        const filePath = normalizeFilePath(params?.path)
        if (!filePath) throw new Error('path is required')
        const fullPath = resolveSafe(filePath)
        const content = await fs.readFile(fullPath, 'utf-8')
        return textResult(content, { path: filePath })
      },
    },
    {
      name: 'write_file',
      label: 'Write File',
      description: 'Write content to a file at a workspace-relative path. Creates parent directories if needed.',
      parameters: Type.Object({
        path: Type.String({ description: 'Relative file path' }),
        content: Type.String({ description: 'Content to write' }),
      }),
      execute: async (_toolCallId, params) => {
        console.log(`[pi-tools] write_file called: path=${params?.path}`)
        const filePath = normalizeFilePath(params?.path)
        if (!filePath) throw new Error('path is required')
        const fullPath = resolveSafe(filePath)
        console.log(`[pi-tools] write_file resolved: ${fullPath}`)
        await fs.mkdir(path.dirname(fullPath), { recursive: true })
        const content = String(params?.content ?? '')
        await fs.writeFile(fullPath, content, 'utf-8')
        console.log(`[pi-tools] write_file done: ${fullPath} (${content.length} bytes)`)
        return textResult(`Wrote ${content.length} bytes to ${filePath}`, { path: filePath, size: content.length })
      },
    },
    {
      name: 'list_dir',
      label: 'List Directory',
      description: 'List files and directories at a workspace-relative path.',
      parameters: Type.Object({
        path: Type.Optional(Type.String({ description: 'Relative directory path (default: project root)' })),
      }),
      execute: async (_toolCallId, params) => {
        const dirPath = normalizePath(params?.path)
        const fullPath = resolveSafe(dirPath)
        const entries = await fs.readdir(fullPath, { withFileTypes: true })
        const formatted = entries.map((e) => ({ name: e.name, isDir: e.isDirectory() }))
        return textResult(formatDirEntries(formatted), { path: dirPath, entries: formatted })
      },
    },
    {
      name: 'exec',
      label: 'Execute Command',
      description: 'Run a shell command in the workspace. Has full access to the workspace filesystem.',
      parameters: Type.Object({
        command: Type.String({ description: 'Shell command to execute' }),
        cwd: Type.Optional(Type.String({ description: 'Working directory (relative to workspace root)' })),
        timeout_seconds: Type.Optional(Type.Number({ description: 'Timeout in seconds', default: 60 })),
      }),
      execute: async (_toolCallId, params) => {
        const command = String(params?.command || '').trim()
        if (!command) throw new Error('command is required')
        const cwd = resolveSafe(normalizePath(params?.cwd))
        const timeout = (Number.isFinite(params?.timeout_seconds) ? Number(params.timeout_seconds) : 60) * 1000
        const start = Date.now()
        try {
          const { stdout, stderr } = await execAsync(command, {
            cwd,
            timeout,
            maxBuffer: 512 * 1024,
            env: { ...process.env, HOME: WORKSPACE_ROOT },
          })
          const duration = Date.now() - start
          const result = { stdout, stderr, exitCode: 0, duration_ms: duration }
          return textResult(formatExecOutput(result), result)
        } catch (err) {
          const duration = Date.now() - start
          const result = {
            stdout: err.stdout || '',
            stderr: err.stderr || err.message || '',
            exitCode: err.code === 'ERR_CHILD_PROCESS_STDIO_MAXBUFFER' ? 124 : (err.code || 1),
            duration_ms: duration,
          }
          return textResult(formatExecOutput(result), result)
        }
      },
    },
    {
      name: 'git_status',
      label: 'Git Status',
      description: 'Show git working tree status.',
      parameters: Type.Object({}),
      execute: async () => {
        try {
          const { stdout } = await execAsync('git status --porcelain', { cwd: WORKSPACE_ROOT })
          const lines = stdout.trim().split('\n').filter(Boolean)
          if (lines.length === 0) return textResult('Clean working tree')
          return textResult(stdout.trim())
        } catch (err) {
          return textResult(err.stderr || 'Not a git repository')
        }
      },
    },
    {
      name: 'git_diff',
      label: 'Git Diff',
      description: 'Show git diff for a file.',
      parameters: Type.Object({
        path: Type.String({ description: 'Relative file path' }),
      }),
      execute: async (_toolCallId, params) => {
        const filePath = normalizeFilePath(params?.path)
        if (!filePath) throw new Error('path is required')
        try {
          const { stdout } = await execAsync(`git diff -- ${filePath}`, { cwd: WORKSPACE_ROOT })
          return textResult(stdout || '(no diff)', { path: filePath })
        } catch (err) {
          return textResult(err.stderr || '(no diff)', { path: filePath })
        }
      },
    },
    {
      name: 'git_commit',
      label: 'Git Commit',
      description: 'Create a git commit from staged changes.',
      parameters: Type.Object({
        message: Type.String({ description: 'Commit message' }),
      }),
      execute: async (_toolCallId, params) => {
        const message = String(params?.message || '').trim()
        if (!message) throw new Error('message is required')
        try {
          const { stdout } = await execAsync(`git commit -m "${message.replace(/"/g, '\\"')}"`, { cwd: WORKSPACE_ROOT })
          return textResult(stdout.trim())
        } catch (err) {
          return textResult(err.stderr || err.message)
        }
      },
    },
  ]

  return tools
}
