/**
 * TDD tests for bd-7b11p: Child app tRPC router merging + tool registration.
 *
 * Tests the framework extension pattern:
 * - workspaceProcedure provides auth + workspace context
 * - Child routers merge into root router
 * - Child tools register via config
 */
import { describe, it, expect } from 'vitest'
import { initTRPC } from '@trpc/server'
import { z } from 'zod'
import {
  createFrameworkTRPC,
  mergeChildRouters,
  registerChildTools,
  type ChildRouterEntry,
  type ChildToolEntry,
} from '../trpc/framework.js'

describe('createFrameworkTRPC', () => {
  it('exports router, publicProcedure, workspaceProcedure', () => {
    const fw = createFrameworkTRPC()
    expect(fw.router).toBeDefined()
    expect(typeof fw.router).toBe('function')
    expect(fw.publicProcedure).toBeDefined()
    expect(fw.workspaceProcedure).toBeDefined()
  })

  it('workspaceProcedure is a tRPC procedure builder', () => {
    const fw = createFrameworkTRPC()
    // Should be usable to create a procedure with input/output
    const testRouter = fw.router({
      hello: fw.workspaceProcedure
        .input(z.object({ name: z.string() }))
        .query(({ input }) => `Hello ${input.name}`),
    })
    expect(testRouter).toBeDefined()
  })
})

describe('mergeChildRouters', () => {
  it('merges child routers into a combined router', () => {
    const fw = createFrameworkTRPC()

    const analyticsRouter = fw.router({
      pageViews: fw.publicProcedure.query(() => 42),
    })

    const children: ChildRouterEntry[] = [
      { namespace: 'analytics', router: analyticsRouter },
    ]

    const merged = mergeChildRouters(fw, children)
    expect(merged).toBeDefined()
    // The merged router should have the child namespace
    expect(merged._def.procedures).toHaveProperty('analytics.pageViews')
  })

  it('merges multiple child routers', () => {
    const fw = createFrameworkTRPC()

    const r1 = fw.router({ a: fw.publicProcedure.query(() => 1) })
    const r2 = fw.router({ b: fw.publicProcedure.query(() => 2) })

    const merged = mergeChildRouters(fw, [
      { namespace: 'app1', router: r1 },
      { namespace: 'app2', router: r2 },
    ])

    expect(merged._def.procedures).toHaveProperty('app1.a')
    expect(merged._def.procedures).toHaveProperty('app2.b')
  })

  it('returns empty router when no children', () => {
    const fw = createFrameworkTRPC()
    const merged = mergeChildRouters(fw, [])
    expect(merged).toBeDefined()
  })
})

describe('registerChildTools', () => {
  it('registers tools from config entries', () => {
    const tools: ChildToolEntry[] = [
      {
        name: 'macro_run',
        description: 'Run a macro',
        parameters: z.object({ macro_id: z.string() }),
      },
      {
        name: 'chart_render',
        description: 'Render a chart',
        parameters: z.object({ chart_id: z.string() }),
      },
    ]

    const registered = registerChildTools(tools)
    expect(registered).toHaveLength(2)
    expect(registered[0].name).toBe('macro_run')
    expect(registered[1].name).toBe('chart_render')
  })

  it('validates tool parameters with Zod', () => {
    const tools: ChildToolEntry[] = [
      {
        name: 'test_tool',
        description: 'A test tool',
        parameters: z.object({ value: z.number().min(0) }),
      },
    ]

    const registered = registerChildTools(tools)
    const tool = registered[0]

    // Valid input
    const valid = tool.parameters.safeParse({ value: 42 })
    expect(valid.success).toBe(true)

    // Invalid input
    const invalid = tool.parameters.safeParse({ value: -1 })
    expect(invalid.success).toBe(false)
  })

  it('returns empty array for no tools', () => {
    expect(registerChildTools([])).toEqual([])
  })
})
