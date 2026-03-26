/**
 * Collaboration HTTP routes — workspace members + invites.
 * Local-mode implementation that mirrors the hosted contract closely enough
 * for route integration coverage and UI flows.
 */
import type { FastifyInstance, FastifyReply, FastifyRequest } from 'fastify'
import { createAuthHook } from '../auth/middleware.js'
import {
  type LocalMemberRole,
} from '../services/localWorkspaceStore.js'
import { getWorkspacePersistence } from '../services/workspacePersistence.js'
import { UUID_RE } from '../workspace/helpers.js'
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const VALID_ROLES: LocalMemberRole[] = ['owner', 'editor', 'viewer']

function badRequest(reply: FastifyReply, code: string, message: string) {
  return reply.code(400).send({ error: 'validation', code, message })
}

function notFound(reply: FastifyReply, code: string, message: string) {
  return reply.code(404).send({ error: 'not_found', code, message })
}

function forbidden(reply: FastifyReply, code: string, message: string) {
  return reply.code(403).send({ error: 'forbidden', code, message })
}

function conflict(reply: FastifyReply, code: string, message: string) {
  return reply.code(409).send({ error: 'conflict', code, message })
}

function gone(reply: FastifyReply, code: string, message: string) {
  return reply.code(410).send({ error: 'gone', code, message })
}

async function ensureWorkspaceExists(
  workspaceId: string,
  reply: FastifyReply,
  request: FastifyRequest,
): Promise<boolean> {
  const persistence = getWorkspacePersistence(request.server.config)
  if (!await persistence.getWorkspace(workspaceId)) {
    notFound(reply, 'WORKSPACE_NOT_FOUND', 'Workspace not found')
    return false
  }
  return true
}

async function requireMember(
  workspaceId: string,
  request: FastifyRequest,
  reply: FastifyReply,
): Promise<LocalMemberRole | null> {
  const userId = request.sessionUserId
  if (!userId) {
    reply.code(401).send({ error: 'unauthorized' })
    return null
  }
  if (!await ensureWorkspaceExists(workspaceId, reply, request)) {
    return null
  }
  const persistence = getWorkspacePersistence(request.server.config)
  const role = await persistence.getMemberRole(workspaceId, userId)
  if (!role) {
    forbidden(reply, 'NOT_A_MEMBER', 'You are not a member of this workspace')
    return null
  }
  return role
}

async function requireOwner(
  workspaceId: string,
  request: FastifyRequest,
  reply: FastifyReply,
): Promise<boolean> {
  const role = await requireMember(workspaceId, request, reply)
  if (!role) return false
  if (role !== 'owner') {
    forbidden(reply, 'OWNER_REQUIRED', 'Only workspace owners can manage members')
    return false
  }
  return true
}

async function requireInviteManager(
  workspaceId: string,
  request: FastifyRequest,
  reply: FastifyReply,
): Promise<boolean> {
  const role = await requireMember(workspaceId, request, reply)
  if (!role) return false
  if (role !== 'owner' && role !== 'editor') {
    forbidden(reply, 'ROLE_REQUIRED_EDITOR', 'Owner or editor role required')
    return false
  }
  return true
}

function normalizeRole(value: unknown, fallback: LocalMemberRole): LocalMemberRole | null {
  const role = String(value ?? fallback).trim().toLowerCase()
  if (!VALID_ROLES.includes(role as LocalMemberRole)) return null
  return role as LocalMemberRole
}

export async function registerCollaborationRoutes(app: FastifyInstance): Promise<void> {
  const persistence = getWorkspacePersistence(app.config)

  app.addHook('onRequest', createAuthHook(app))

  app.get<{ Params: { id: string } }>('/workspaces/:id/members', async (request, reply) => {
    const { id } = request.params
    if (!UUID_RE.test(id)) return badRequest(reply, 'INVALID_WORKSPACE_ID', 'workspace_id must be a UUID')
    if (!await requireMember(id, request, reply)) return reply
    const members = await persistence.listWorkspaceMembers(id)
    return { ok: true, members, count: members.length }
  })

  app.post<{ Params: { id: string } }>('/workspaces/:id/members', async (request, reply) => {
    const { id } = request.params
    if (!UUID_RE.test(id)) return badRequest(reply, 'INVALID_WORKSPACE_ID', 'workspace_id must be a UUID')
    if (!await requireOwner(id, request, reply)) return reply

    const body = request.body as { user_id?: string; role?: string } | null
    const userId = String(body?.user_id || '').trim()
    if (!UUID_RE.test(userId)) {
      return badRequest(reply, 'INVALID_MEMBER_USER_ID', 'user_id must be a UUID')
    }
    const role = normalizeRole(body?.role, 'editor')
    if (!role) {
      return badRequest(reply, 'INVALID_ROLE', `role must be: ${VALID_ROLES.join(', ')}`)
    }

    return { ok: true, member: await persistence.upsertWorkspaceMember(id, userId, role) }
  })

  const updateMemberHandler = async (
    request: FastifyRequest<{ Params: { id: string; userId: string } }>,
    reply: FastifyReply,
  ) => {
    const { id, userId } = request.params
    if (!UUID_RE.test(id)) return badRequest(reply, 'INVALID_WORKSPACE_ID', 'workspace_id must be a UUID')
    if (!UUID_RE.test(userId)) return badRequest(reply, 'INVALID_MEMBER_USER_ID', 'user_id must be a UUID')
    if (!await requireOwner(id, request, reply)) return reply

    const body = request.body as { role?: string } | null
    const role = normalizeRole(body?.role, 'viewer')
    if (!role) {
      return badRequest(reply, 'INVALID_ROLE', `role must be: ${VALID_ROLES.join(', ')}`)
    }

    return { ok: true, member: await persistence.upsertWorkspaceMember(id, userId, role) }
  }

  app.put('/workspaces/:id/members/:userId', updateMemberHandler)
  app.patch('/workspaces/:id/members/:userId', updateMemberHandler)

  app.delete<{ Params: { id: string; userId: string } }>('/workspaces/:id/members/:userId', async (request, reply) => {
    const { id, userId } = request.params
    if (!UUID_RE.test(id)) return badRequest(reply, 'INVALID_WORKSPACE_ID', 'workspace_id must be a UUID')
    if (!UUID_RE.test(userId)) return badRequest(reply, 'INVALID_MEMBER_USER_ID', 'user_id must be a UUID')
    if (!await requireOwner(id, request, reply)) return reply

    const result = await persistence.removeWorkspaceMember(id, userId)
    if (result.code === 'LAST_OWNER') {
      return conflict(reply, 'LAST_OWNER', 'Cannot remove the last workspace owner')
    }
    if (!result.removed) {
      return notFound(reply, 'MEMBER_NOT_FOUND', 'Member not found')
    }
    return { ok: true, removed: true }
  })

  app.get<{ Params: { id: string } }>('/workspaces/:id/invites', async (request, reply) => {
    const { id } = request.params
    if (!UUID_RE.test(id)) return badRequest(reply, 'INVALID_WORKSPACE_ID', 'workspace_id must be a UUID')
    if (!await requireInviteManager(id, request, reply)) return reply
    const invites = await persistence.listWorkspaceInvites(id)
    return { ok: true, invites, count: invites.length }
  })

  app.post<{ Params: { id: string } }>('/workspaces/:id/invites', async (request, reply) => {
    const { id } = request.params
    if (!UUID_RE.test(id)) return badRequest(reply, 'INVALID_WORKSPACE_ID', 'workspace_id must be a UUID')
    if (!await requireInviteManager(id, request, reply)) return reply

    const body = request.body as { email?: string; role?: string } | null
    const email = String(body?.email || '').trim().toLowerCase()
    if (!EMAIL_RE.test(email)) {
      return badRequest(reply, 'INVALID_EMAIL', 'A valid email address is required')
    }
    const role = normalizeRole(body?.role, 'editor')
    if (!role) {
      return badRequest(reply, 'INVALID_ROLE', `role must be: ${VALID_ROLES.join(', ')}`)
    }

    return {
      ok: true,
      invite: await persistence.createWorkspaceInvite(id, email, role, request.sessionUserId ?? null),
    }
  })

  app.post<{ Params: { id: string; inviteId: string } }>(
    '/workspaces/:id/invites/:inviteId/accept',
    async (request, reply) => {
      const { id, inviteId } = request.params
      if (!UUID_RE.test(id)) return badRequest(reply, 'INVALID_WORKSPACE_ID', 'workspace_id must be a UUID')
      if (!UUID_RE.test(inviteId)) return badRequest(reply, 'INVALID_INVITE_ID', 'invite_id must be a UUID')
      if (!await ensureWorkspaceExists(id, reply, request)) return reply

      const invite = await persistence.getWorkspaceInvite(id, inviteId)
      if (!invite) return notFound(reply, 'INVITE_NOT_FOUND', 'Invite not found')
      if (invite.accepted_at) {
        return conflict(reply, 'INVITE_ALREADY_ACCEPTED', 'Invite already accepted')
      }
      if (new Date(invite.expires_at).getTime() < Date.now()) {
        return gone(reply, 'INVITE_EXPIRED', 'Invite has expired')
      }
      if (String(invite.email).toLowerCase() !== String(request.sessionEmail || '').toLowerCase()) {
        return forbidden(reply, 'EMAIL_MISMATCH', 'Invite email does not match session user')
      }

      const userId = request.sessionUserId
      if (!userId) {
        return reply.code(401).send({ error: 'unauthorized' })
      }

      const accepted = await persistence.acceptWorkspaceInvite(id, inviteId, userId)
      return {
        ok: true,
        invite: accepted.invite,
        membership: accepted.member,
      }
    },
  )

  app.delete<{ Params: { id: string; inviteId: string } }>(
    '/workspaces/:id/invites/:inviteId',
    async (request, reply) => {
      const { id, inviteId } = request.params
      if (!UUID_RE.test(id)) return badRequest(reply, 'INVALID_WORKSPACE_ID', 'workspace_id must be a UUID')
      if (!UUID_RE.test(inviteId)) return badRequest(reply, 'INVALID_INVITE_ID', 'invite_id must be a UUID')
      if (!await requireInviteManager(id, request, reply)) return reply
      if (!await persistence.revokeWorkspaceInvite(id, inviteId)) {
        return notFound(reply, 'INVITE_NOT_FOUND', 'Invite not found')
      }
      return { ok: true, revoked: true }
    },
  )
}
