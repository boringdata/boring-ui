import { Type } from '@sinclair/typebox'
import { exec as execCb } from 'node:child_process'
import { existsSync, mkdirSync } from 'node:fs'
import { resolve as pathResolve } from 'node:path'
import { promisify } from 'node:util'

const execAsync = promisify(execCb)

const DEFAULT_WORKSPACE_ROOT = process.env.BORING_UI_WORKSPACE_ROOT || process.cwd()

const textResult = (text, details = {}) => ({
  content: [{ type: 'text', text }],
  details,
})

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
    || '',
  )
  const internalApiToken = String(
    payload.internal_api_token
    || payload.internalApiToken
    || bearerTokenFromHeader(headers.authorization)
    || headers['x-boring-internal-token']
    || env.BORING_INTERNAL_TOKEN
    || env.BORING_INTERNAL_API_TOKEN
    || env.BORING_UI_INTERNAL_TOKEN
    || ''
  ).trim()
  const backendUrl = normalizeBaseUrl(
    payload.backend_url
    || payload.backendUrl
    || headers['x-boring-backend-url']
    || env.BORING_BACKEND_URL
  )
  const workspaceRoot = String(
    payload.workspace_root
    || payload.workspaceRoot
    || headers['x-boring-workspace-root']
    || ''
  ).trim()

  return { workspaceId, internalApiToken, backendUrl, workspaceRoot }
}

export function getEffectiveWorkspaceRoot(context = {}) {
  return context.workspaceRoot || DEFAULT_WORKSPACE_ROOT
}

export function buildSessionSystemPrompt(basePrompt, context = {}) {
  const prompt = String(basePrompt || '').trim()
  const root = getEffectiveWorkspaceRoot(context)
  return [
    prompt,
    `Workspace root: ${root}.`,
    'You have full shell access via the exec_bash tool.',
    'Use exec_bash for ALL operations: file creation, reading, editing, git, python, etc.',
    'Always use exec_bash — do not respond with file contents in text, use the tool.',
  ].filter(Boolean).join(' ')
}

// --- Backend-agent mode tool: exec_bash ---

function createExecBashTool(wsRoot) {
  return {
    name: 'exec_bash',
    label: 'Execute Bash',
    description: 'Execute a bash command in the workspace. Use this for ALL operations: file read/write, git, python, package install, etc.',
    parameters: Type.Object({
      command: Type.String({ description: 'Bash command to execute' }),
      cwd: Type.Optional(Type.String({ description: 'Working directory relative to workspace root' })),
    }),
    execute: async (_toolCallId, params) => {
      const command = String(params?.command || '').trim()
      if (!command) throw new Error('command is required')
      const cwd = params?.cwd
        ? String(params.cwd).trim().replace(/^\/+/, '')
        : '.'
      const fullCwd = pathResolve(wsRoot, cwd)
      if (!fullCwd.startsWith(wsRoot + '/') && fullCwd !== wsRoot) {
        return textResult('Error: cwd resolves outside workspace root')
      }
      if (!existsSync(fullCwd)) {
        try { mkdirSync(fullCwd, { recursive: true }) } catch { /* best effort */ }
      }
      const start = Date.now()
      try {
        const { stdout, stderr } = await execAsync(command, {
          cwd: fullCwd,
          timeout: 60_000,
          maxBuffer: 512 * 1024,
          env: { ...process.env, HOME: wsRoot },
        })
        return textResult(formatExecOutput({ stdout, stderr, exitCode: 0 }), {
          stdout, stderr, exitCode: 0, duration_ms: Date.now() - start,
        })
      } catch (err) {
        const result = {
          stdout: err.stdout || '',
          stderr: err.stderr || err.message || '',
          exitCode: typeof err.code === 'number' ? err.code : 1,
          duration_ms: Date.now() - start,
        }
        return textResult(formatExecOutput(result), result)
      }
    },
  }
}

// --- Shared tools (all modes): UI state via backend API ---

async function fetchBackendJson(backendUrl, apiPath, options = {}, authToken = '') {
  const url = `${backendUrl}${apiPath}`
  const headers = { ...options.headers }
  if (options.body) {
    headers['content-type'] = 'application/json'
  }
  if (authToken) {
    headers.authorization = `Bearer ${authToken}`
  }
  try {
    const res = await fetch(url, { headers, ...options })
    if (!res.ok) {
      const body = await res.text().catch(() => '')
      if (res.status === 404 && body.includes('No frontend state')) {
        return { _error: true, status: 404, body: 'No browser client is connected' }
      }
      return { _error: true, status: res.status, body }
    }
    return await res.json()
  } catch (err) {
    return { _error: true, status: 0, body: err.message || 'Backend unavailable' }
  }
}

function createSharedUiTools(backendUrl, authToken) {
  return [
    {
      name: 'list_panes',
      label: 'List Panes',
      description: 'List currently open UI panels and which one is active.',
      parameters: Type.Object({}),
      execute: async () => {
        const data = await fetchBackendJson(backendUrl, '/api/v1/ui/panes', {}, authToken)
        if (data._error) return textResult(`Error fetching panes: ${data.status} ${data.body}`)
        const panels = data.open_panels || []
        if (panels.length === 0) return textResult('No panels open')
        const activeId = data.active_panel_id || ''
        const lines = panels.map((p) => {
          const id = p.id || ''
          const component = p.component || ''
          const title = p.title || ''
          const marker = id === activeId ? ' (active)' : ''
          return `${component}: ${title || id}${marker}`
        })
        return textResult(lines.join('\n'))
      },
    },

    {
      name: 'get_ui_state',
      label: 'Get UI State',
      description: 'Get full UI snapshot: open panels, active file, project root.',
      parameters: Type.Object({}),
      execute: async () => {
        const data = await fetchBackendJson(backendUrl, '/api/v1/ui/state/latest', {}, authToken)
        if (data._error) return textResult(`Error fetching UI state: ${data.status} ${data.body}`)
        const state = data.state || {}
        const parts = []
        if (state.active_panel_id) parts.push(`Active panel: ${state.active_panel_id}`)
        if (state.project_root) parts.push(`Project root: ${state.project_root}`)
        const panels = state.open_panels || []
        if (panels.length > 0) {
          parts.push(`Open panels (${panels.length}):`)
          for (const p of panels) {
            const id = p.id || ''
            const component = p.component || ''
            const title = p.title || ''
            parts.push(`  ${component}: ${title || id}`)
          }
        }
        return textResult(parts.join('\n') || 'No UI state available')
      },
    },

    {
      name: 'open_file',
      label: 'Open File',
      description: 'Open a file in the editor panel.',
      parameters: Type.Object({
        path: Type.String({ description: 'File path relative to workspace root' }),
      }),
      execute: async (_toolCallId, params) => {
        const path = String(params?.path || '').trim().replace(/^\/+/, '')
        if (!path) return textResult('Error: path is required')
        const data = await fetchBackendJson(backendUrl, '/api/v1/ui/commands', {
          method: 'POST',
          body: JSON.stringify({
            command: {
              kind: 'open_panel',
              component: 'editor',
              title: path.split('/').pop() || path,
              params: { path },
              prefer_existing: true,
            },
          }),
        }, authToken)
        if (data._error) return textResult(`Error opening file: ${data.status} ${data.body}`)
        return textResult(`Opening ${path} in editor`)
      },
    },

    {
      name: 'list_tabs',
      label: 'List Tabs',
      description: 'List currently open editor tabs and which file is active.',
      parameters: Type.Object({}),
      execute: async () => {
        const data = await fetchBackendJson(backendUrl, '/api/v1/ui/panes', {}, authToken)
        if (data._error) return textResult(`Error fetching tabs: ${data.status} ${data.body}`)
        const panels = (data.open_panels || []).filter((p) => p.component === 'editor')
        if (panels.length === 0) return textResult('No editor tabs open')
        const activeId = data.active_panel_id || ''
        const lines = panels.map((p) => {
          const path = p.params?.path || p.title || p.id || ''
          return p.id === activeId ? `* ${path}` : `  ${path}`
        })
        return textResult(lines.join('\n'))
      },
    },
  ]
}

// --- Tool assembly ---

export function createWorkspaceTools(context = {}) {
  const wsRoot = getEffectiveWorkspaceRoot(context)
  const backendUrl = String(context.backendUrl || '').trim()
  const authToken = String(context.internalApiToken || '').trim()
  const tools = [createExecBashTool(wsRoot)]
  if (backendUrl) {
    tools.push(...createSharedUiTools(backendUrl, authToken))
  }
  return tools
}
