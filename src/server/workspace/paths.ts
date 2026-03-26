/**
 * Workspace path utilities — safe path resolution and validation.
 * Canonical home for all path-within-workspace checks.
 * Used by fileRoutes, aiSdkTools, and any code that needs to verify
 * a user-supplied path stays inside the workspace root.
 */
import { lstat, mkdir, realpath, stat } from 'node:fs/promises'
import { dirname, isAbsolute, relative, resolve } from 'node:path'

/**
 * Resolve a user-supplied path against the workspace root and verify
 * it doesn't escape via `..` or absolute-path tricks.
 * Throws with statusCode 400 on traversal.
 */
export function validatePath(workspaceRoot: string, requestedPath: string): string {
  const resolvedRoot = resolve(workspaceRoot)
  const resolved = resolve(workspaceRoot, requestedPath)
  if (resolved !== resolvedRoot && !resolved.startsWith(resolvedRoot + '/')) {
    throw Object.assign(new Error('Path traversal detected'), { statusCode: 400 })
  }
  return resolved
}

/**
 * Follow symlinks and verify the real path is still within the workspace.
 * Both paths must already exist on disk.
 */
export async function assertRealPathWithinWorkspace(
  workspaceRoot: string,
  candidatePath: string,
): Promise<void> {
  const realRoot = await realpath(resolve(workspaceRoot))
  const realCandidate = await realpath(candidatePath)
  const rel = relative(realRoot, realCandidate)
  if (rel.startsWith('..') || isAbsolute(rel)) {
    throw Object.assign(new Error('Path traversal detected'), { statusCode: 400 })
  }
}

/**
 * Validate + symlink-check for a path that must already exist.
 */
export async function ensureExistingWorkspacePath(
  workspaceRoot: string,
  requestedPath: string,
): Promise<string> {
  const absolutePath = validatePath(workspaceRoot, requestedPath)
  await assertRealPathWithinWorkspace(workspaceRoot, absolutePath)
  return absolutePath
}

/**
 * Validate + symlink-check for a path that may not yet exist.
 * Creates intermediate directories, then rechecks symlinks at each level.
 */
export async function ensureWritableWorkspacePath(
  workspaceRoot: string,
  requestedPath: string,
): Promise<string> {
  const absolutePath = validatePath(workspaceRoot, requestedPath)
  const absoluteDir = dirname(absolutePath)
  const resolvedRoot = resolve(workspaceRoot)

  // Walk up to find the first existing ancestor
  let existingAncestor = absoluteDir
  while (existingAncestor !== resolvedRoot) {
    try {
      await stat(existingAncestor)
      break
    } catch (error: any) {
      if (error?.code !== 'ENOENT') throw error
      existingAncestor = dirname(existingAncestor)
    }
  }

  await assertRealPathWithinWorkspace(workspaceRoot, existingAncestor)
  await mkdir(absoluteDir, { recursive: true })
  await assertRealPathWithinWorkspace(workspaceRoot, absoluteDir)

  // Reject symlinks at the target path itself
  try {
    const pathStat = await lstat(absolutePath)
    if (pathStat.isSymbolicLink()) {
      throw Object.assign(new Error('Path traversal detected'), { statusCode: 400 })
    }
  } catch (error: any) {
    if (error?.code !== 'ENOENT') throw error
  }

  return absolutePath
}
