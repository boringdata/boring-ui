/**
 * Workspace resolver — maps config to concrete backend implementations.
 *
 * resolveWorkspaceBackend(config, workspaceId) creates the right backend
 * based on workspace.backend config. Panels and tools never see raw config.
 *
 * Server-side: only bwrap is valid (lightningfs/justbash run in browser).
 */
import { mkdirSync } from 'node:fs'
import { join, resolve } from 'node:path'
import type { ServerConfig, WorkspaceBackend } from '../config.js'

export interface ResolvedWorkspace {
  /** Absolute path to the workspace directory */
  workspacePath: string
  /** The backend type */
  backend: WorkspaceBackend
  /** Capabilities this backend provides */
  capabilities: string[]
}

const BACKEND_CAPABILITIES: Record<WorkspaceBackend, string[]> = {
  bwrap: ['workspace.files', 'workspace.exec', 'workspace.git', 'workspace.python'],
  lightningfs: ['workspace.files', 'workspace.git'],
  justbash: ['workspace.files', 'workspace.exec'],
}

/**
 * Resolve workspace backend for server-side use.
 * Creates the workspace directory if it doesn't exist.
 *
 * @throws Error if backend is browser-only (lightningfs, justbash)
 */
export function resolveWorkspaceBackend(
  config: ServerConfig,
  workspaceId: string,
): ResolvedWorkspace {
  const backend = config.workspaceBackend

  if (backend === 'lightningfs' || backend === 'justbash') {
    throw new Error(
      `workspace.backend="${backend}" runs in the browser, not on the server. ` +
      `Server resolver only supports "bwrap".`,
    )
  }

  const workspacePath = resolveWorkspacePath(config.workspaceRoot, workspaceId)

  // Ensure workspace directory exists (idempotent)
  mkdirSync(workspacePath, { recursive: true })

  return {
    workspacePath,
    backend,
    capabilities: BACKEND_CAPABILITIES[backend] ?? [],
  }
}

/**
 * Resolve workspace root path safely.
 * Prevents path traversal by validating the resolved path.
 */
export function resolveWorkspacePath(
  workspaceRoot: string,
  workspaceId: string,
): string {
  const resolvedRoot = resolve(workspaceRoot)
  const resolvedPath = resolve(workspaceRoot, workspaceId)

  // Use resolvedRoot + '/' to prevent prefix collision:
  // e.g., /workspace-evil would falsely match /workspace without trailing /
  if (resolvedPath !== resolvedRoot && !resolvedPath.startsWith(resolvedRoot + '/')) {
    throw new Error(`Path traversal detected: ${workspaceId}`)
  }

  return resolvedPath
}

/**
 * Resolve a file path within a workspace safely.
 * Prevents path traversal outside the workspace directory.
 */
export function resolvePathBeneath(
  workspacePath: string,
  requestedPath: string,
): string {
  const resolvedBase = resolve(workspacePath)
  const resolvedPath = resolve(workspacePath, requestedPath)

  if (resolvedPath !== resolvedBase && !resolvedPath.startsWith(resolvedBase + '/')) {
    throw new Error(`Path traversal detected: ${requestedPath}`)
  }

  return resolvedPath
}

/**
 * Check if single-mode is forced via header.
 * Used by dedicated workspace machines.
 */
export function isSingleModeForced(
  headers: Record<string, string | string[] | undefined>,
): boolean {
  const value = headers['x-boring-local-workspace']
  if (Array.isArray(value)) return value.length > 0
  return !!value
}
