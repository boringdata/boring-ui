import { describe, it, expect } from 'vitest'
import { z } from 'zod'
import {
  createFrameworkTRPC,
  mergeChildRouters,
  registerChildTools,
} from '../trpc/framework.js'

describe('createFrameworkTRPC', () => {
  it('exports router, publicProcedure, workspaceProcedure', () => {
    const fw = createFrameworkTRPC()
    expect(fw.router).toBeDefined()
    expect(typeof fw.router).toBe('function')
    expect(fw.publicProcedure).toBeDefined()
    expect(fw.workspaceProcedure).toBeDefined()
  })
})

describe('mergeChildRouters', () => {
  it('merges child routers into a combined router', () => {
    const fw = createFrameworkTRPC()
    const childA = fw.router({
      hello: fw.publicProcedure.query(() => 'hello from A'),
    })
    const childB = fw.router({
      world: fw.publicProcedure.query(() => 'hello from B'),
    })

    const merged = mergeChildRouters(fw, [
      { namespace: 'a', router: childA },
      { namespace: 'b', router: childB },
    ])

    expect(merged).toBeDefined()
    expect(merged._def).toBeDefined()
    expect(merged._def.procedures).toHaveProperty('a.hello')
    expect(merged._def.procedures).toHaveProperty('b.world')
  })

  it('handles empty array', () => {
    const fw = createFrameworkTRPC()
    const merged = mergeChildRouters(fw, [])
    expect(merged).toBeDefined()
  })
})

describe('registerChildTools', () => {
  it('registers tools with Zod schemas', () => {
    const tools = registerChildTools([
      { name: 'my_tool', description: 'Test tool', parameters: z.object({ value: z.string() }) },
    ])
    expect(tools).toHaveLength(1)
    expect(tools[0].name).toBe('my_tool')
    expect(tools[0].parameters.safeParse({ value: 'ok' }).success).toBe(true)
  })
})
