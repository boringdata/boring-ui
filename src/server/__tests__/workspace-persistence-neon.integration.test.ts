import { randomUUID } from 'node:crypto'
import { existsSync } from 'node:fs'
import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { describe, beforeAll, afterAll, afterEach, expect, it } from 'vitest'
import { createDbClient } from '../db/index.js'
import {
  RuntimeInvalidTransitionError,
  getWorkspacePersistence,
} from '../services/workspacePersistence.js'
import { testConfig } from './helpers.js'

const DATABASE_URL = process.env.DATABASE_URL
const SETTINGS_KEY = process.env.BORING_SETTINGS_KEY
const describeIfNeon = DATABASE_URL && SETTINGS_KEY ? describe : describe.skip

describeIfNeon('workspace persistence against real Neon', () => {
  let workspaceRoot = ''
  let sqlClient: NonNullable<ReturnType<typeof createDbClient>>['sql']
  let persistence: ReturnType<typeof getWorkspacePersistence>
  let createdWorkspaceIds: string[] = []
  let createdUserIds: string[] = []

  beforeAll(async () => {
    workspaceRoot = await mkdtemp(join(tmpdir(), 'bui-neon-persistence-'))
    const config = testConfig({
      controlPlaneProvider: 'neon',
      databaseUrl: DATABASE_URL,
      settingsKey: SETTINGS_KEY,
      workspaceRoot,
    }) as any
    const client = createDbClient(config)
    if (!client) {
      throw new Error('DATABASE_URL is required for Neon integration tests')
    }
    sqlClient = client.sql
    persistence = getWorkspacePersistence(config)
  })

  afterEach(async () => {
    for (const workspaceId of createdWorkspaceIds.reverse()) {
      await sqlClient`
        DELETE FROM workspace_settings
        WHERE workspace_id = ${workspaceId}::uuid
      `
      await sqlClient`
        DELETE FROM workspace_invites
        WHERE workspace_id = ${workspaceId}::uuid
      `
      await sqlClient`
        DELETE FROM workspace_members
        WHERE workspace_id = ${workspaceId}::uuid
      `
      await sqlClient`
        DELETE FROM workspace_runtimes
        WHERE workspace_id = ${workspaceId}::uuid
      `
      await sqlClient`
        DELETE FROM workspaces
        WHERE id = ${workspaceId}::uuid
      `
    }

    for (const userId of createdUserIds.reverse()) {
      await sqlClient`
        DELETE FROM user_settings
        WHERE user_id = ${userId}::uuid
          AND app_id = 'boring-ui'
      `
    }

    createdWorkspaceIds = []
    createdUserIds = []
  })

  afterAll(async () => {
    await rm(workspaceRoot, { recursive: true, force: true })
    await sqlClient.end({ timeout: 5 })
  })

  it('creates, lists, updates, soft-deletes, and initializes workspace runtime + owner state', async () => {
    const userId = randomUUID()
    createdUserIds.push(userId)

    const first = await persistence.createWorkspace(userId, `bd-3xftp neon alpha ${Date.now()}`)
    createdWorkspaceIds.push(first.id)
    const second = await persistence.createWorkspace(userId, `bd-3xftp neon beta ${Date.now()}`)
    createdWorkspaceIds.push(second.id)

    expect(first.created_by).toBe(userId)
    expect(first.is_default).toBe(true)
    expect(second.is_default).toBe(false)
    expect(existsSync(join(workspaceRoot, first.id))).toBe(true)

    const listed = await persistence.listWorkspaces(userId)
    expect(listed.map((workspace) => workspace.id)).toEqual([first.id, second.id])

    const runtime = await persistence.getWorkspaceRuntime(first.id)
    expect(runtime.workspace_id).toBe(first.id)
    expect(runtime.state).toBe('pending')
    expect(runtime.retryable).toBe(false)

    const ownerRole = await persistence.getMemberRole(first.id, userId)
    expect(ownerRole).toBe('owner')

    const renamed = await persistence.updateWorkspace(second.id, {
      name: 'bd-3xftp renamed workspace',
    })
    expect(renamed?.name).toBe('bd-3xftp renamed workspace')

    expect(await persistence.deleteWorkspace(second.id)).toBe(true)
    expect(await persistence.getWorkspace(second.id)).toBeUndefined()

    const softDeletedRows = await sqlClient<{ deleted_at: string | null }[]>`
      SELECT deleted_at
      FROM workspaces
      WHERE id = ${second.id}::uuid
    `
    expect(softDeletedRows).toHaveLength(1)
    expect(softDeletedRows[0].deleted_at).toBeTruthy()
  }, 30000)

  it('merges user settings and stores workspace settings as decryptable encrypted rows', async () => {
    const userId = randomUUID()
    createdUserIds.push(userId)
    const workspace = await persistence.createWorkspace(userId, `bd-3xftp settings ${Date.now()}`)
    createdWorkspaceIds.push(workspace.id)

    const firstSettings = await persistence.putUserSettings(userId, 'MixedCase@Test.EXAMPLE', {
      display_name: 'Neon Test User',
      settings: { theme: 'dark' },
    })
    expect(firstSettings.email).toBe('mixedcase@test.example')
    expect(firstSettings.display_name).toBe('Neon Test User')
    expect(firstSettings.settings).toEqual({ theme: 'dark' })

    const mergedSettings = await persistence.putUserSettings(userId, 'MixedCase@Test.EXAMPLE', {
      settings: { sidebar_collapsed: true },
    })
    expect(mergedSettings.settings).toEqual({
      theme: 'dark',
      sidebar_collapsed: true,
    })

    const storedSettings = await persistence.getUserSettings(userId, 'MixedCase@Test.EXAMPLE')
    expect(storedSettings).toEqual({
      display_name: 'Neon Test User',
      email: 'mixedcase@test.example',
      settings: {
        theme: 'dark',
        sidebar_collapsed: true,
      },
    })

    const secretValue = `secret-${Date.now()}`
    await persistence.putWorkspaceSettings(workspace.id, {
      api_key: secretValue,
      region: 'iad',
    })

    const workspaceSettings = await persistence.getWorkspaceSettings(workspace.id)
    expect(workspaceSettings).toMatchObject({
      api_key: { configured: true },
      region: { configured: true },
    })

    const decryptedRows = await sqlClient<{ key: string; decrypted: string }[]>`
      SELECT key, pgp_sym_decrypt(value, ${SETTINGS_KEY!}) AS decrypted
      FROM workspace_settings
      WHERE workspace_id = ${workspace.id}::uuid
      ORDER BY key ASC
    `
    expect(decryptedRows).toEqual([
      { key: 'api_key', decrypted: secretValue },
      { key: 'region', decrypted: 'iad' },
    ])
  }, 30000)

  it('manages invites and membership transitions while protecting the last owner', async () => {
    const ownerId = randomUUID()
    const invitedUserId = randomUUID()
    createdUserIds.push(ownerId, invitedUserId)

    const workspace = await persistence.createWorkspace(ownerId, `bd-3xftp invites ${Date.now()}`)
    createdWorkspaceIds.push(workspace.id)

    expect(await persistence.removeWorkspaceMember(workspace.id, ownerId)).toEqual({
      removed: false,
      code: 'LAST_OWNER',
    })

    const invite = await persistence.createWorkspaceInvite(
      workspace.id,
      'Invitee@Example.COM',
      'editor',
      ownerId,
    )
    expect(invite.email).toBe('invitee@example.com')
    expect(invite.role).toBe('editor')

    const inviteList = await persistence.listWorkspaceInvites(workspace.id)
    expect(inviteList.map((row) => row.id)).toContain(invite.id)

    const accepted = await persistence.acceptWorkspaceInvite(workspace.id, invite.id, invitedUserId)
    expect(accepted.invite?.accepted_at).toBeTruthy()
    expect(accepted.member).toMatchObject({
      workspace_id: workspace.id,
      user_id: invitedUserId,
      role: 'editor',
    })

    expect(await persistence.getMemberRole(workspace.id, invitedUserId)).toBe('editor')

    const updatedMember = await persistence.upsertWorkspaceMember(workspace.id, invitedUserId, 'viewer')
    expect(updatedMember.role).toBe('viewer')

    const members = await persistence.listWorkspaceMembers(workspace.id)
    expect(members.map((member) => [member.user_id, member.role])).toEqual([
      [ownerId, 'owner'],
      [invitedUserId, 'viewer'],
    ])

    expect(await persistence.removeWorkspaceMember(workspace.id, invitedUserId)).toEqual({ removed: true })

    const secondInvite = await persistence.createWorkspaceInvite(
      workspace.id,
      'revoke-me@example.com',
      'viewer',
      ownerId,
    )
    expect(await persistence.revokeWorkspaceInvite(workspace.id, secondInvite.id)).toBe(true)
    expect(await persistence.getWorkspaceInvite(workspace.id, secondInvite.id)).toBeUndefined()
  }, 30000)

  it('creates concurrent workspaces for one user without producing duplicate defaults', async () => {
    const userId = randomUUID()
    createdUserIds.push(userId)

    const created = await Promise.all([
      persistence.createWorkspace(userId, `bd-3xftp concurrent a ${Date.now()}`),
      persistence.createWorkspace(userId, `bd-3xftp concurrent b ${Date.now()}`),
    ])
    createdWorkspaceIds.push(...created.map((workspace) => workspace.id))

    const listed = await persistence.listWorkspaces(userId)
    const defaults = listed.filter((workspace) => workspace.is_default)

    expect(created).toHaveLength(2)
    expect(defaults).toHaveLength(1)
    expect(new Set(created.map((workspace) => workspace.id)).size).toBe(2)
  }, 30000)

  it('persists GitHub linkage through encrypted workspace settings and user settings JSON', async () => {
    const userId = randomUUID()
    createdUserIds.push(userId)
    const workspace = await persistence.createWorkspace(userId, `bd-3xftp github ${Date.now()}`)
    createdWorkspaceIds.push(workspace.id)

    expect(await persistence.getWorkspaceGitHubConnection(workspace.id)).toBeNull()

    const workspaceLink = await persistence.setWorkspaceGitHubConnection(workspace.id, {
      installation_id: 424242,
      repo_url: 'https://github.com/boringdata/boring-ui',
    })
    expect(workspaceLink).toEqual({
      installation_id: 424242,
      repo_url: 'https://github.com/boringdata/boring-ui',
    })
    expect(await persistence.getWorkspaceGitHubConnection(workspace.id)).toEqual(workspaceLink)

    await persistence.clearWorkspaceGitHubConnection(workspace.id)
    expect(await persistence.getWorkspaceGitHubConnection(workspace.id)).toBeNull()

    const userLink = await persistence.setUserGitHubLink(
      userId,
      'github-link@example.com',
      777777,
    )
    expect(userLink).toEqual({
      account_linked: true,
      default_installation_id: 777777,
    })
    expect(await persistence.getUserGitHubLink(userId, 'github-link@example.com')).toEqual(userLink)

    const clearedUserLink = await persistence.setUserGitHubLink(
      userId,
      'github-link@example.com',
      null,
    )
    expect(clearedUserLink).toEqual({
      account_linked: false,
      default_installation_id: null,
    })
  }, 30000)

  it('recreates a missing runtime row on demand', async () => {
    const userId = randomUUID()
    createdUserIds.push(userId)
    const workspace = await persistence.createWorkspace(userId, `bd-3xftp runtime-seed ${Date.now()}`)
    createdWorkspaceIds.push(workspace.id)

    await sqlClient`
      DELETE FROM workspace_runtimes
      WHERE workspace_id = ${workspace.id}::uuid
    `

    const runtime = await persistence.getWorkspaceRuntime(workspace.id)
    expect(runtime).toMatchObject({
      workspace_id: workspace.id,
      state: 'pending',
      retryable: false,
    })
  }, 30000)

  it('retries runtime from error and rejects invalid retry transitions', async () => {
    const userId = randomUUID()
    createdUserIds.push(userId)
    const workspace = await persistence.createWorkspace(userId, `bd-3xftp runtime ${Date.now()}`)
    createdWorkspaceIds.push(workspace.id)

    await sqlClient`
      UPDATE workspace_runtimes
      SET state = 'error',
          last_error = 'boom',
          provisioning_step = 'booting',
          step_started_at = now()
      WHERE workspace_id = ${workspace.id}::uuid
    `

    const retried = await persistence.retryWorkspaceRuntime(workspace.id)
    expect(retried).toMatchObject({
      workspace_id: workspace.id,
      state: 'pending',
      last_error: null,
      retryable: false,
    })

    await expect(persistence.retryWorkspaceRuntime(workspace.id)).rejects.toBeInstanceOf(
      RuntimeInvalidTransitionError,
    )
  }, 30000)
})
