/**
 * Framework tRPC primitives for child app extension.
 *
 * Child apps use these exports to register their own tRPC routers and tools:
 *   import { router, workspaceProcedure } from 'boring-ui/trpc'
 *
 * The framework merges child routers into the root app router at startup.
 */
import { initTRPC } from '@trpc/server'
import type { z } from 'zod'

/** tRPC context — provides authenticated user and workspace to procedures. */
export interface TRPCContext {
  userId?: string
  email?: string
  workspaceId?: string
}

// --- Framework tRPC instance ---

export interface FrameworkTRPC {
  router: ReturnType<ReturnType<typeof initTRPC.context<TRPCContext>>['create']>['router']
  publicProcedure: ReturnType<ReturnType<typeof initTRPC.context<TRPCContext>>['create']>['procedure']
  workspaceProcedure: ReturnType<ReturnType<typeof initTRPC.context<TRPCContext>>['create']>['procedure']
}

/**
 * Create the framework tRPC primitives.
 * Exports router, publicProcedure, and workspaceProcedure.
 */
export function createFrameworkTRPC(): FrameworkTRPC {
  const t = initTRPC.context<TRPCContext>().create()

  // workspaceProcedure will add auth + workspace middleware in a later phase.
  // For now it's identical to publicProcedure (middleware added in Phase 3 auth work).
  const workspaceProcedure = t.procedure

  return {
    router: t.router,
    publicProcedure: t.procedure,
    workspaceProcedure,
  }
}

// --- Child router merging ---

export interface ChildRouterEntry {
  /** Namespace for the child router (e.g., 'analytics', 'macro') */
  namespace: string
  /** The child's tRPC router */
  router: ReturnType<FrameworkTRPC['router']>
}

/**
 * Merge child app routers into a combined router under namespaces.
 *
 * Example: child router `analytics` with procedure `pageViews`
 * becomes accessible as `trpc.analytics.pageViews`.
 */
export function mergeChildRouters(
  fw: FrameworkTRPC,
  children: ChildRouterEntry[],
): ReturnType<FrameworkTRPC['router']> {
  const routes: Record<string, ReturnType<FrameworkTRPC['router']>> = {}

  for (const child of children) {
    routes[child.namespace] = child.router
  }

  return fw.router(routes)
}

// --- Child tool registration ---

export interface ChildToolEntry {
  /** Tool name (e.g., 'macro_run') */
  name: string
  /** Human-readable description */
  description: string
  /** Zod schema for tool parameters */
  parameters: z.ZodType<any>
}

export interface RegisteredTool {
  name: string
  description: string
  parameters: z.ZodType<any>
}

/**
 * Register child app tools for agent use.
 * These are merged into the agent's tool list at runtime.
 */
export function registerChildTools(
  tools: ChildToolEntry[],
): RegisteredTool[] {
  return tools.map((tool) => ({
    name: tool.name,
    description: tool.description,
    parameters: tool.parameters,
  }))
}
