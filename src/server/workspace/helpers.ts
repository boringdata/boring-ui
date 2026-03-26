/**
 * Shared workspace helpers used across route handlers and AI SDK tools.
 */
import type { FastifyInstance, FastifyRequest } from 'fastify'
import { execSync } from 'node:child_process'
import { mkdirSync } from 'node:fs'
import { resolveWorkspacePath } from './resolver.js'

/**
 * Resolve the workspace root from the `x-workspace-id` header,
 * falling back to the configured default. Creates the directory if needed.
 */
export function getWorkspaceRoot(app: FastifyInstance, request: FastifyRequest): string {
  const workspaceIdHeader = request.headers['x-workspace-id']
  const workspaceId = Array.isArray(workspaceIdHeader)
    ? workspaceIdHeader[0]
    : workspaceIdHeader
  if (workspaceId && String(workspaceId).trim()) {
    const workspaceRoot = resolveWorkspacePath(app.config.workspaceRoot, String(workspaceId))
    mkdirSync(workspaceRoot, { recursive: true })
    return workspaceRoot
  }
  return app.config.workspaceRoot
}

/** Check once whether bubblewrap is available on this system. */
let _hasBwrapCached: boolean | undefined
export function hasBwrap(): boolean {
  if (_hasBwrapCached === undefined) {
    try {
      execSync('which bwrap', { stdio: 'ignore' })
      _hasBwrapCached = true
    } catch {
      _hasBwrapCached = false
    }
  }
  return _hasBwrapCached
}

export const MAX_OUTPUT_BYTES = 512 * 1024 // 512KB

export function truncateOutput(output: string): string {
  if (Buffer.byteLength(output) > MAX_OUTPUT_BYTES) {
    return output.slice(0, MAX_OUTPUT_BYTES) + '\n[truncated: output exceeded 512KB]'
  }
  return output
}

/** UUID format regex — shared across route files. */
export const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
