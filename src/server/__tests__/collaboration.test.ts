import { afterEach, describe, expect, it } from 'vitest'
import type { FastifyInstance } from 'fastify'
import { createApp } from '../app.js'
import { createSessionCookie } from '../auth/session.js'
import { loadConfig } from '../config.js'
import {
  createWorkspace,
  resetLocalWorkspaceStore,
  upsertWorkspaceMember,
} from '../services/localWorkspaceStore.js'

const TEST_SECRET = 'test-secret-must-be-at-least-32-characters-long-for-hs256'
const OWNER_ID = '00000000-0000-0000-0000-000000000001'
const MEMBER_ID = '00000000-0000-0000-0000-000000000002'
const OUTSIDER_ID = '00000000-0000-0000-0000-000000000003'
const INVITEE_ID = '00000000-0000-0000-0000-000000000004'

let app: FastifyInstance | undefined

function getApp() {
  app = createApp({ config: { ...loadConfig(), sessionSecret: TEST_SECRET } })
  return app
}

function seedWorkspace(ownerId = OWNER_ID) {
  return createWorkspace(ownerId, 'Collaboration Test Workspace', loadConfig().controlPlaneAppId)
}

async function getToken(userId: string, email = `${userId}@example.com`) {
  return createSessionCookie(userId, email, TEST_SECRET, { ttlSeconds: 3600 })
}

afterEach(async () => {
  if (app) {
    await app.close()
    app = undefined
  }
  resetLocalWorkspaceStore()
})

describe('Collaboration routes', () => {
  it('requires auth across members and invites routes', async () => {
    const ws = seedWorkspace()
    const app = getApp()
    const routes = [
      { method: 'GET' as const, url: `/api/v1/workspaces/${ws.id}/members` },
      { method: 'POST' as const, url: `/api/v1/workspaces/${ws.id}/members`, payload: { user_id: MEMBER_ID } },
      { method: 'PATCH' as const, url: `/api/v1/workspaces/${ws.id}/members/${MEMBER_ID}`, payload: { role: 'viewer' } },
      { method: 'DELETE' as const, url: `/api/v1/workspaces/${ws.id}/members/${MEMBER_ID}` },
      { method: 'GET' as const, url: `/api/v1/workspaces/${ws.id}/invites` },
      { method: 'POST' as const, url: `/api/v1/workspaces/${ws.id}/invites`, payload: { email: 'bob@example.com' } },
    ]

    for (const route of routes) {
      const res = await app.inject(route)
      expect(res.statusCode).toBe(401)
    }
  })

  it('lists members for a workspace member', async () => {
    const ws = seedWorkspace()
    const app = getApp()
    const token = await getToken(OWNER_ID, 'owner@example.com')

    const res = await app.inject({
      method: 'GET',
      url: `/api/v1/workspaces/${ws.id}/members`,
      cookies: { boring_session: token },
    })

    expect(res.statusCode).toBe(200)
    expect(JSON.parse(res.payload)).toMatchObject({
      ok: true,
      count: 1,
      members: [
        {
          workspace_id: ws.id,
          user_id: OWNER_ID,
          role: 'owner',
        },
      ],
    })
  })

  it('returns 403 for non-members listing members', async () => {
    const ws = seedWorkspace()
    const app = getApp()
    const token = await getToken(OUTSIDER_ID, 'outsider@example.com')

    const res = await app.inject({
      method: 'GET',
      url: `/api/v1/workspaces/${ws.id}/members`,
      cookies: { boring_session: token },
    })

    expect(res.statusCode).toBe(403)
    expect(JSON.parse(res.payload)).toMatchObject({
      code: 'NOT_A_MEMBER',
    })
  })

  it('adds a member as owner', async () => {
    const ws = seedWorkspace()
    const app = getApp()
    const token = await getToken(OWNER_ID, 'owner@example.com')

    const res = await app.inject({
      method: 'POST',
      url: `/api/v1/workspaces/${ws.id}/members`,
      cookies: { boring_session: token },
      payload: { user_id: MEMBER_ID, role: 'editor' },
    })

    expect(res.statusCode).toBe(200)
    expect(JSON.parse(res.payload)).toMatchObject({
      ok: true,
      member: {
        workspace_id: ws.id,
        user_id: MEMBER_ID,
        role: 'editor',
      },
    })
  })

  it('updates a member role as owner', async () => {
    const ws = seedWorkspace()
    upsertWorkspaceMember(ws.id, MEMBER_ID, 'viewer')
    const app = getApp()
    const token = await getToken(OWNER_ID, 'owner@example.com')

    const res = await app.inject({
      method: 'PATCH',
      url: `/api/v1/workspaces/${ws.id}/members/${MEMBER_ID}`,
      cookies: { boring_session: token },
      payload: { role: 'editor' },
    })

    expect(res.statusCode).toBe(200)
    expect(JSON.parse(res.payload)).toMatchObject({
      ok: true,
      member: {
        workspace_id: ws.id,
        user_id: MEMBER_ID,
        role: 'editor',
      },
    })
  })

  it('prevents removing the last owner', async () => {
    const ws = seedWorkspace()
    const app = getApp()
    const token = await getToken(OWNER_ID, 'owner@example.com')

    const res = await app.inject({
      method: 'DELETE',
      url: `/api/v1/workspaces/${ws.id}/members/${OWNER_ID}`,
      cookies: { boring_session: token },
    })

    expect(res.statusCode).toBe(409)
    expect(JSON.parse(res.payload)).toMatchObject({
      code: 'LAST_OWNER',
    })
  })

  it('removes a non-owner member as owner', async () => {
    const ws = seedWorkspace()
    upsertWorkspaceMember(ws.id, MEMBER_ID, 'viewer')
    const app = getApp()
    const token = await getToken(OWNER_ID, 'owner@example.com')

    const res = await app.inject({
      method: 'DELETE',
      url: `/api/v1/workspaces/${ws.id}/members/${MEMBER_ID}`,
      cookies: { boring_session: token },
    })

    expect(res.statusCode).toBe(200)
    expect(JSON.parse(res.payload)).toMatchObject({
      ok: true,
      removed: true,
    })
  })

  it('creates, lists, and revokes invites for owner/editor roles', async () => {
    const ws = seedWorkspace()
    upsertWorkspaceMember(ws.id, MEMBER_ID, 'editor')
    const app = getApp()
    const ownerToken = await getToken(OWNER_ID, 'owner@example.com')
    const editorToken = await getToken(MEMBER_ID, 'editor@example.com')

    const createRes = await app.inject({
      method: 'POST',
      url: `/api/v1/workspaces/${ws.id}/invites`,
      cookies: { boring_session: ownerToken },
      payload: { email: 'invitee@example.com', role: 'viewer' },
    })
    expect(createRes.statusCode).toBe(200)
    const inviteId = JSON.parse(createRes.payload).invite.id

    const listRes = await app.inject({
      method: 'GET',
      url: `/api/v1/workspaces/${ws.id}/invites`,
      cookies: { boring_session: editorToken },
    })
    expect(listRes.statusCode).toBe(200)
    expect(JSON.parse(listRes.payload)).toMatchObject({
      ok: true,
      count: 1,
      invites: [
        {
          id: inviteId,
          workspace_id: ws.id,
          email: 'invitee@example.com',
          role: 'viewer',
        },
      ],
    })

    const revokeRes = await app.inject({
      method: 'DELETE',
      url: `/api/v1/workspaces/${ws.id}/invites/${inviteId}`,
      cookies: { boring_session: editorToken },
    })
    expect(revokeRes.statusCode).toBe(200)
    expect(JSON.parse(revokeRes.payload)).toMatchObject({
      ok: true,
      revoked: true,
    })
  })

  it('returns 403 for non-members listing invites', async () => {
    const ws = seedWorkspace()
    const app = getApp()
    const token = await getToken(OUTSIDER_ID, 'outsider@example.com')

    const res = await app.inject({
      method: 'GET',
      url: `/api/v1/workspaces/${ws.id}/invites`,
      cookies: { boring_session: token },
    })

    expect(res.statusCode).toBe(403)
    expect(JSON.parse(res.payload)).toMatchObject({
      code: 'NOT_A_MEMBER',
    })
  })

  it('accepts an invite only for the matching session email', async () => {
    const ws = seedWorkspace()
    const app = getApp()
    const ownerToken = await getToken(OWNER_ID, 'owner@example.com')

    const createRes = await app.inject({
      method: 'POST',
      url: `/api/v1/workspaces/${ws.id}/invites`,
      cookies: { boring_session: ownerToken },
      payload: { email: 'invitee@example.com', role: 'editor' },
    })
    const inviteId = JSON.parse(createRes.payload).invite.id

    const mismatchToken = await getToken(INVITEE_ID, 'other@example.com')
    const mismatchRes = await app.inject({
      method: 'POST',
      url: `/api/v1/workspaces/${ws.id}/invites/${inviteId}/accept`,
      cookies: { boring_session: mismatchToken },
    })
    expect(mismatchRes.statusCode).toBe(403)
    expect(JSON.parse(mismatchRes.payload)).toMatchObject({
      code: 'EMAIL_MISMATCH',
    })

    const matchingToken = await getToken(INVITEE_ID, 'invitee@example.com')
    const acceptRes = await app.inject({
      method: 'POST',
      url: `/api/v1/workspaces/${ws.id}/invites/${inviteId}/accept`,
      cookies: { boring_session: matchingToken },
    })
    expect(acceptRes.statusCode).toBe(200)
    expect(JSON.parse(acceptRes.payload)).toMatchObject({
      ok: true,
      membership: {
        workspace_id: ws.id,
        user_id: INVITEE_ID,
        role: 'editor',
      },
    })
  })
})
