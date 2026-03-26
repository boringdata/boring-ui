/**
 * In-memory workspace store for local development mode.
 *
 * Provides workspace CRUD without a database. Used when
 * CONTROL_PLANE_PROVIDER=local. Data is ephemeral — lost on restart.
 */
import { randomUUID } from 'node:crypto'

export interface LocalWorkspace {
  id: string
  app_id: string
  name: string
  created_by: string
  created_at: string
  is_default: boolean
  machine_id: string | null
  volume_id: string | null
  fly_region: string | null
}

export type LocalMemberRole = 'owner' | 'editor' | 'viewer'

export interface LocalWorkspaceMember {
  workspace_id: string
  user_id: string
  role: LocalMemberRole
  created_at: string
}

export interface LocalWorkspaceInvite {
  id: string
  invite_id: string
  workspace_id: string
  email: string
  role: LocalMemberRole
  invited_by: string | null
  expires_at: string
  accepted_at: string | null
  created_at: string
}

export interface LocalUserSettings {
  display_name: string
  email: string
  settings: Record<string, unknown>
}

const workspaces = new Map<string, LocalWorkspace>()
const members = new Map<string, Map<string, LocalWorkspaceMember>>() // workspaceId -> userId -> member
const invites = new Map<string, Map<string, LocalWorkspaceInvite>>() // workspaceId -> inviteId -> invite
const userSettings = new Map<string, LocalUserSettings>() // `${userId}:${appId}` -> settings
const uiStates = new Map<string, Record<string, unknown>>() // `${userId}:${workspaceId}` -> state

// --- Workspaces ---

export function createWorkspace(
  userId: string,
  name: string,
  appId: string,
): LocalWorkspace {
  const id = randomUUID()
  const isFirst = ![...workspaces.values()].some(
    (w) => w.created_by === userId && w.app_id === appId,
  )
  const ws: LocalWorkspace = {
    id,
    app_id: appId,
    name,
    created_by: userId,
    created_at: new Date().toISOString(),
    is_default: isFirst,
    machine_id: null,
    volume_id: null,
    fly_region: null,
  }
  workspaces.set(id, ws)

  // Creator is auto-added as owner
  const createdAt = new Date().toISOString()
  const memberMap = new Map<string, LocalWorkspaceMember>()
  memberMap.set(userId, {
    workspace_id: id,
    user_id: userId,
    role: 'owner',
    created_at: createdAt,
  })
  members.set(id, memberMap)

  return ws
}

export function listWorkspaces(userId: string): LocalWorkspace[] {
  return [...workspaces.values()].filter((ws) => {
    const memberMap = members.get(ws.id)
    return memberMap?.has(userId)
  })
}

export function getWorkspace(id: string): LocalWorkspace | undefined {
  return workspaces.get(id)
}

export function updateWorkspace(
  id: string,
  updates: Partial<Pick<LocalWorkspace, 'name'>>,
): LocalWorkspace | undefined {
  const ws = workspaces.get(id)
  if (!ws) return undefined
  if (updates.name) ws.name = updates.name
  return ws
}

export function deleteWorkspace(id: string): boolean {
  members.delete(id)
  invites.delete(id)
  return workspaces.delete(id)
}

export function isMember(workspaceId: string, userId: string): boolean {
  return members.get(workspaceId)?.has(userId) ?? false
}

export function getMemberRole(
  workspaceId: string,
  userId: string,
): LocalMemberRole | null {
  return members.get(workspaceId)?.get(userId)?.role ?? null
}

export function listWorkspaceMembers(
  workspaceId: string,
): LocalWorkspaceMember[] {
  return [...(members.get(workspaceId)?.values() ?? [])].sort((a, b) => {
    const rank = (role: LocalMemberRole) => {
      if (role === 'owner') return 0
      if (role === 'editor') return 1
      return 2
    }
    return rank(a.role) - rank(b.role) || a.created_at.localeCompare(b.created_at)
  })
}

export function upsertWorkspaceMember(
  workspaceId: string,
  userId: string,
  role: LocalMemberRole,
): LocalWorkspaceMember {
  const memberMap = members.get(workspaceId) ?? new Map<string, LocalWorkspaceMember>()
  const existing = memberMap.get(userId)
  const member: LocalWorkspaceMember = {
    workspace_id: workspaceId,
    user_id: userId,
    role,
    created_at: existing?.created_at ?? new Date().toISOString(),
  }
  memberMap.set(userId, member)
  members.set(workspaceId, memberMap)
  return member
}

export function removeWorkspaceMember(
  workspaceId: string,
  userId: string,
): { removed: boolean; code?: 'LAST_OWNER' } {
  const memberMap = members.get(workspaceId)
  const existing = memberMap?.get(userId)
  if (!memberMap || !existing) return { removed: false }

  if (existing.role === 'owner') {
    const ownerCount = [...memberMap.values()].filter((member) => member.role === 'owner').length
    if (ownerCount <= 1) {
      return { removed: false, code: 'LAST_OWNER' }
    }
  }

  memberMap.delete(userId)
  return { removed: true }
}

export function listWorkspaceInvites(
  workspaceId: string,
): LocalWorkspaceInvite[] {
  return [...(invites.get(workspaceId)?.values() ?? [])].sort((a, b) =>
    b.created_at.localeCompare(a.created_at),
  )
}

export function createWorkspaceInvite(
  workspaceId: string,
  email: string,
  role: LocalMemberRole,
  invitedBy: string | null,
): LocalWorkspaceInvite {
  const inviteMap = invites.get(workspaceId) ?? new Map<string, LocalWorkspaceInvite>()
  const id = randomUUID()
  const createdAt = new Date().toISOString()
  const expiresAt = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString()
  const invite: LocalWorkspaceInvite = {
    id,
    invite_id: id,
    workspace_id: workspaceId,
    email: email.trim().toLowerCase(),
    role,
    invited_by: invitedBy,
    created_at: createdAt,
    expires_at: expiresAt,
    accepted_at: null,
  }
  inviteMap.set(id, invite)
  invites.set(workspaceId, inviteMap)
  return invite
}

export function getWorkspaceInvite(
  workspaceId: string,
  inviteId: string,
): LocalWorkspaceInvite | undefined {
  return invites.get(workspaceId)?.get(inviteId)
}

export function revokeWorkspaceInvite(
  workspaceId: string,
  inviteId: string,
): boolean {
  return invites.get(workspaceId)?.delete(inviteId) ?? false
}

export function acceptWorkspaceInvite(
  workspaceId: string,
  inviteId: string,
  userId: string,
): { invite?: LocalWorkspaceInvite; member?: LocalWorkspaceMember } {
  const invite = invites.get(workspaceId)?.get(inviteId)
  if (!invite) return {}
  invite.accepted_at = new Date().toISOString()
  const member = upsertWorkspaceMember(workspaceId, userId, invite.role)
  return { invite, member }
}

export function resetLocalWorkspaceStore(): void {
  workspaces.clear()
  members.clear()
  invites.clear()
  userSettings.clear()
  uiStates.clear()
}

// --- User Settings ---

function userSettingsKey(userId: string, appId: string): string {
  return `${userId}:${appId}`
}

export function getUserSettings(
  userId: string,
  appId: string,
): LocalUserSettings {
  const key = userSettingsKey(userId, appId)
  return userSettings.get(key) ?? { display_name: '', email: '', settings: {} }
}

export function putUserSettings(
  userId: string,
  appId: string,
  updates: Partial<LocalUserSettings>,
): LocalUserSettings {
  const key = userSettingsKey(userId, appId)
  const existing = userSettings.get(key) ?? {
    display_name: '',
    email: '',
    settings: {},
  }
  const merged = {
    ...existing,
    ...updates,
    settings: { ...existing.settings, ...updates.settings },
  }
  userSettings.set(key, merged)
  return merged
}

// --- Workspace Settings ---

const workspaceSettings = new Map<string, Record<string, string>>() // workspaceId -> settings

export function getWorkspaceSettings(workspaceId: string): Record<string, string> {
  return workspaceSettings.get(workspaceId) ?? {}
}

export function putWorkspaceSettings(
  workspaceId: string,
  settings: Record<string, string>,
): Record<string, string> {
  const existing = workspaceSettings.get(workspaceId) ?? {}
  const merged = { ...existing, ...settings }
  workspaceSettings.set(workspaceId, merged)
  return merged
}

// --- UI State ---

function uiStateKey(userId: string, workspaceId: string): string {
  return `${userId}:${workspaceId}`
}

export function getUiState(
  userId: string,
  workspaceId: string,
): Record<string, unknown> | null {
  return uiStates.get(uiStateKey(userId, workspaceId)) ?? null
}

export function putUiState(
  userId: string,
  workspaceId: string,
  state: Record<string, unknown>,
): void {
  uiStates.set(uiStateKey(userId, workspaceId), state)
}
