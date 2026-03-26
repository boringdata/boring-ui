/**
 * Service layer barrel export.
 *
 * NOTE: The stub interface files (files.ts, git.ts, etc.) are DEPRECATED.
 * Production routes import directly from the *Impl files:
 * - gitImpl.ts (via gitRoutes.ts)
 * - githubImpl.ts (via githubRoutes.ts)
 * - capabilitiesImpl.ts (via health.ts)
 * - pythonCompatCapabilities.ts (via health.ts)
 * - runtimeConfig.ts (via health.ts)
 * - uiStateImpl.ts (via uiStateRoutes.ts)
 * - extensionTrust.ts
 *
 * The type-only exports below are kept for backward compatibility.
 * New code should import from the Impl files directly.
 */

// --- Active implementations ---
export { createGitServiceImpl, type GitServiceImpl } from './gitImpl.js'
export { buildCapabilitiesResponse } from './capabilitiesImpl.js'
export { buildPythonCompatCapabilities, buildEnabledFeatures } from './pythonCompatCapabilities.js'
export { buildRuntimeConfigPayload } from './runtimeConfig.js'
export {
  createGitHubAppJwt,
  buildGitCredentials,
  buildOAuthUrl,
  isGitHubConfigured,
} from './githubImpl.js'

// --- Deprecated stub types (kept for backward compatibility) ---
export type { FileService } from './files.js'
export type { GitService } from './git.js'
export type { ExecService } from './exec.js'
export type { AuthService } from './auth.js'
export type { WorkspaceService } from './workspaces.js'
export type { UserService } from './users.js'
export type { ApprovalStore } from './approval.js'
export type { UIStateService } from './uiState.js'
export type { GitHubService } from './github.js'
