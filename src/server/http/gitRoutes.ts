/**
 * Git HTTP routes at /api/v1/git/* — 16 endpoints.
 * Uses simple-git via GitServiceImpl. Python-compatible response shapes.
 */
import type { FastifyInstance, FastifyReply, FastifyRequest } from 'fastify'
import { createGitServiceImpl, type GitServiceImpl } from '../services/gitImpl.js'
import { getWorkspaceRoot } from '../workspace/helpers.js'

export async function registerGitRoutes(app: FastifyInstance): Promise<void> {
  const gitServiceFor = (request: FastifyRequest): GitServiceImpl => {
    const workspaceRoot = getWorkspaceRoot(app, request)
    return createGitServiceImpl(workspaceRoot)
  }

  const sendGitError = (reply: FastifyReply, err: any, fallbackStatusCode = 500) => {
    const message = String(err?.message || 'git error')
    const lowered = message.toLowerCase()
    const statusCode = err?.statusCode
      ?? (lowered.includes('nothing to commit') ? 400 : fallbackStatusCode)

    return reply.code(statusCode).send({
      error: 'git_error',
      message,
      detail: `Git error: ${message}`,
    })
  }

  // --- Read operations ---

  // GET /git/status
  app.get('/git/status', async (request) => gitServiceFor(request).getStatus())

  // GET /git/diff?path=...
  app.get('/git/diff', async (request) => {
    const { path } = request.query as { path?: string }
    return gitServiceFor(request).getDiff(path)
  })

  // GET /git/show?path=...
  app.get('/git/show', async (request, reply) => {
    const { path } = request.query as { path?: string }
    if (!path) return reply.code(400).send({ error: 'validation', message: 'path is required' })
    return gitServiceFor(request).getShow(path)
  })

  // GET /git/branch
  app.get('/git/branch', async (request) => gitServiceFor(request).currentBranch())

  // GET /git/branches
  app.get('/git/branches', async (request) => gitServiceFor(request).listBranches())

  // GET /git/remotes
  app.get('/git/remotes', async (request) => gitServiceFor(request).listRemotes())

  // --- Write operations ---

  // POST /git/init
  app.post('/git/init', async (request) => gitServiceFor(request).initRepo())

  // POST /git/add
  app.post('/git/add', async (request, reply) => {
    const body = request.body as { paths?: string[] } | null
    try {
      return await gitServiceFor(request).addFiles(body?.paths)
    } catch (err: any) {
      return sendGitError(reply, err)
    }
  })

  // POST /git/commit
  app.post('/git/commit', async (request, reply) => {
    const body = request.body as {
      message: string
      author_name?: string
      author_email?: string
      author?: {
        name?: string
        email?: string
      }
    } | null

    if (!body?.message?.trim()) {
      return reply.code(400).send({ error: 'validation', message: 'commit message is required' })
    }

    try {
      const authorName = body.author_name || body.author?.name
      const authorEmail = body.author_email || body.author?.email
      return await gitServiceFor(request).commit(body.message, authorName, authorEmail)
    } catch (err: any) {
      return sendGitError(reply, err)
    }
  })

  // POST /git/push
  app.post('/git/push', async (request, reply) => {
    const body = request.body as { remote?: string; branch?: string } | null
    try {
      return await gitServiceFor(request).push(body?.remote, body?.branch)
    } catch (err: any) {
      const fallbackStatusCode = err.message?.includes('Authentication') ? 401 : 500
      return sendGitError(reply, err, fallbackStatusCode)
    }
  })

  // POST /git/pull
  app.post('/git/pull', async (request, reply) => {
    const body = request.body as { remote?: string; branch?: string } | null
    try {
      return await gitServiceFor(request).pull(body?.remote, body?.branch)
    } catch (err: any) {
      const fallbackStatusCode = err.message?.includes('Authentication') ? 401 : 500
      return sendGitError(reply, err, fallbackStatusCode)
    }
  })

  // POST /git/clone
  app.post('/git/clone', async (request, reply) => {
    const body = request.body as { url: string; branch?: string } | null
    if (!body?.url) {
      return reply.code(400).send({ error: 'validation', message: 'url is required' })
    }
    try {
      return await gitServiceFor(request).cloneRepo(body.url, body.branch)
    } catch (err: any) {
      return sendGitError(reply, err)
    }
  })

  // POST /git/branch/create
  app.post('/git/branch/create', async (request, reply) => {
    const body = request.body as { name: string; checkout?: boolean } | null
    if (!body?.name?.trim()) {
      return reply.code(400).send({ error: 'validation', message: 'branch name is required' })
    }
    try {
      return await gitServiceFor(request).createBranch(body.name, body.checkout ?? true)
    } catch (err: any) {
      return sendGitError(reply, err)
    }
  })

  // POST /git/checkout
  app.post('/git/checkout', async (request, reply) => {
    const body = request.body as { name: string } | null
    if (!body?.name?.trim()) {
      return reply.code(400).send({ error: 'validation', message: 'branch name is required' })
    }
    try {
      return await gitServiceFor(request).checkoutBranch(body.name)
    } catch (err: any) {
      return sendGitError(reply, err)
    }
  })

  // POST /git/merge
  app.post('/git/merge', async (request, reply) => {
    const body = request.body as { source: string; message?: string } | null
    if (!body?.source?.trim()) {
      return reply.code(400).send({ error: 'validation', message: 'source branch is required' })
    }
    try {
      return await gitServiceFor(request).mergeBranch(body.source, body.message)
    } catch (err: any) {
      const statusCode = err.message?.includes('CONFLICTS') ? 409 : 500
      return sendGitError(reply, err, statusCode)
    }
  })

  const addRemoteHandler = async (request: any, reply: FastifyReply) => {
    const body = request.body as { name: string; url: string } | null
    if (!body?.name?.trim() || !body?.url?.trim()) {
      return reply.code(400).send({ error: 'validation', message: 'name and url are required' })
    }
    try {
      return await gitServiceFor(request).addRemote(body.name, body.url)
    } catch (err: any) {
      return sendGitError(reply, err)
    }
  }

  // POST /git/remote and /git/remote/add
  app.post('/git/remote', addRemoteHandler)
  app.post('/git/remote/add', addRemoteHandler)
}
