/**
 * Workspace settings page with metadata, runtime status, and membership surfaces.
 *
 * Bead: bd-223o.14.3 (H3)
 *
 * Rendered at /w/{workspace_id}/settings via the onboarding gate.
 * Consumes:
 *   GET  /api/v1/workspaces/{id}          — workspace metadata
 *   PATCH /api/v1/workspaces/{id}         — rename
 *   GET  /api/v1/workspaces/{id}/members  — membership list
 *   POST /api/v1/workspaces/{id}/members  — invite
 *   DELETE /api/v1/workspaces/{id}/members/{member_id} — remove
 *   GET  /api/v1/workspaces/{id}/runtime  — runtime status
 */

import { useCallback, useEffect, useState } from 'react'
import {
  ArrowLeft,
  Check,
  Loader2,
  Pencil,
  Plus,
  Trash2,
  UserPlus,
  X,
} from 'lucide-react'
import { buildApiUrl } from '../utils/apiBase'
import { resolveFromError } from '../utils/apiErrors'
import ApiErrorBanner from './ApiErrorBanner'

// ── Helpers ──────────────────────────────────────────────────────────

const fetchJson = async (path, init) => {
  const response = await fetch(buildApiUrl(path), init)
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    const error = new Error(data?.detail || `HTTP ${response.status}`)
    error.status = response.status
    error.data = data
    throw error
  }
  return response.json()
}

const STATUS_LABELS = {
  active: 'Active',
  pending: 'Pending',
  removed: 'Removed',
}

const RUNTIME_LABELS = {
  ready: 'Ready',
  provisioning: 'Provisioning',
  queued: 'Queued',
  creating_sandbox: 'Creating sandbox',
  bootstrapping: 'Bootstrapping',
  health_check: 'Health check',
  retrying: 'Retrying',
  error: 'Error',
  failed: 'Failed',
}

// ── Workspace Info Section ───────────────────────────────────────────

function WorkspaceInfo({ workspace, onRename }) {
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const startEdit = () => {
    setName(workspace?.name || '')
    setEditing(true)
    setError('')
  }

  const cancelEdit = () => {
    setEditing(false)
    setError('')
  }

  const saveEdit = async () => {
    const trimmed = name.trim()
    if (!trimmed) {
      setError('Name cannot be empty')
      return
    }
    if (trimmed === workspace?.name) {
      setEditing(false)
      return
    }
    setSaving(true)
    setError('')
    try {
      await onRename(trimmed)
      setEditing(false)
    } catch (err) {
      setError(err?.data?.detail || err.message || 'Failed to rename')
    } finally {
      setSaving(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') saveEdit()
    if (e.key === 'Escape') cancelEdit()
  }

  if (!workspace) return null

  return (
    <section className="ws-settings-section" data-testid="workspace-info">
      <h2>Workspace</h2>
      <div className="ws-settings-field">
        <label>Name</label>
        {editing ? (
          <div className="ws-settings-inline-edit">
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={handleKeyDown}
              autoFocus
              data-testid="workspace-name-input"
            />
            <button
              type="button"
              onClick={saveEdit}
              disabled={saving}
              className="ws-settings-icon-btn ws-settings-icon-btn-confirm"
              data-testid="workspace-name-save"
            >
              {saving ? <Loader2 size={14} className="ws-spin" /> : <Check size={14} />}
            </button>
            <button
              type="button"
              onClick={cancelEdit}
              className="ws-settings-icon-btn"
              data-testid="workspace-name-cancel"
            >
              <X size={14} />
            </button>
            {error && <span className="ws-settings-error">{error}</span>}
          </div>
        ) : (
          <div className="ws-settings-value">
            <span data-testid="workspace-name-display">{workspace.name}</span>
            <button
              type="button"
              className="ws-settings-icon-btn"
              onClick={startEdit}
              data-testid="workspace-name-edit"
            >
              <Pencil size={14} />
            </button>
          </div>
        )}
      </div>
      <div className="ws-settings-field">
        <label>ID</label>
        <span className="ws-settings-value ws-settings-mono" data-testid="workspace-id">
          {workspace.workspace_id || workspace.id}
        </span>
      </div>
      <div className="ws-settings-field">
        <label>Created</label>
        <span className="ws-settings-value" data-testid="workspace-created">
          {workspace.created_at ? new Date(workspace.created_at).toLocaleString() : '—'}
        </span>
      </div>
    </section>
  )
}

// ── Runtime Status Section ───────────────────────────────────────────

function RuntimeStatus({ runtime, loading }) {
  const state = runtime?.runtime_state || runtime?.state || 'unknown'
  const label = RUNTIME_LABELS[state] || state

  return (
    <section className="ws-settings-section" data-testid="runtime-status">
      <h2>Runtime</h2>
      {loading ? (
        <div className="ws-settings-loading">
          <Loader2 size={16} className="ws-spin" />
          <span>Loading runtime status...</span>
        </div>
      ) : (
        <div className="ws-settings-field">
          <label>State</label>
          <span
            className={`ws-settings-runtime-badge ws-settings-runtime-${state}`}
            data-testid="runtime-state"
          >
            {label}
          </span>
        </div>
      )}
    </section>
  )
}

// ── Members Section ──────────────────────────────────────────────────

function MembersSection({ workspaceId }) {
  const [members, setMembers] = useState([])
  const [loading, setLoading] = useState(true)
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviting, setInviting] = useState(false)
  const [inviteError, setInviteError] = useState(null)
  const [removeError, setRemoveError] = useState(null)
  const [showInvite, setShowInvite] = useState(false)

  const loadMembers = useCallback(async () => {
    if (!workspaceId) return
    setLoading(true)
    try {
      const data = await fetchJson(
        `/api/v1/workspaces/${encodeURIComponent(workspaceId)}/members`,
      )
      setMembers(data.members || [])
    } catch {
      setMembers([])
    } finally {
      setLoading(false)
    }
  }, [workspaceId])

  useEffect(() => {
    loadMembers()
  }, [loadMembers])

  const handleInvite = async () => {
    const email = inviteEmail.trim()
    if (!email) return
    setInviting(true)
    setInviteError(null)
    try {
      await fetchJson(
        `/api/v1/workspaces/${encodeURIComponent(workspaceId)}/members`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email }),
        },
      )
      setInviteEmail('')
      setShowInvite(false)
      await loadMembers()
    } catch (err) {
      setInviteError(resolveFromError(err))
    } finally {
      setInviting(false)
    }
  }

  const handleRemove = async (memberId) => {
    setRemoveError(null)
    try {
      await fetchJson(
        `/api/v1/workspaces/${encodeURIComponent(workspaceId)}/members/${memberId}`,
        { method: 'DELETE' },
      )
      await loadMembers()
    } catch (err) {
      setRemoveError(resolveFromError(err))
    }
  }

  const handleInviteKeyDown = (e) => {
    if (e.key === 'Enter') handleInvite()
    if (e.key === 'Escape') {
      setShowInvite(false)
      setInviteError(null)
    }
  }

  return (
    <section className="ws-settings-section" data-testid="members-section">
      <div className="ws-settings-section-header">
        <h2>Members</h2>
        <button
          type="button"
          className="ws-settings-text-btn"
          onClick={() => setShowInvite(!showInvite)}
          data-testid="invite-toggle"
        >
          <UserPlus size={14} />
          <span>Invite</span>
        </button>
      </div>

      {showInvite && (
        <div className="ws-settings-invite" data-testid="invite-form">
          <input
            type="email"
            placeholder="Email address"
            value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
            onKeyDown={handleInviteKeyDown}
            autoFocus
            data-testid="invite-email-input"
          />
          <button
            type="button"
            className="ws-settings-text-btn ws-settings-text-btn-primary"
            onClick={handleInvite}
            disabled={inviting || !inviteEmail.trim()}
            data-testid="invite-submit"
          >
            {inviting ? <Loader2 size={14} className="ws-spin" /> : <Plus size={14} />}
            <span>Send invite</span>
          </button>
          {inviteError && (
            <ApiErrorBanner
              error={inviteError}
              onDismiss={() => setInviteError(null)}
              onRetry={inviteError.retryable ? handleInvite : undefined}
              data-testid="invite-error"
            />
          )}
        </div>
      )}

      {removeError && (
        <ApiErrorBanner
          error={removeError}
          onDismiss={() => setRemoveError(null)}
          onRetry={removeError.retryable ? loadMembers : undefined}
        />
      )}

      {loading ? (
        <div className="ws-settings-loading">
          <Loader2 size={16} className="ws-spin" />
          <span>Loading members...</span>
        </div>
      ) : members.length === 0 ? (
        <p className="ws-settings-empty">No members yet.</p>
      ) : (
        <ul className="ws-settings-members-list" data-testid="members-list">
          {members.map((m) => (
            <li key={m.member_id} className="ws-settings-member" data-testid={`member-${m.member_id}`}>
              <div className="ws-settings-member-info">
                <span className="ws-settings-member-email">{m.email}</span>
                <span className={`ws-settings-status ws-settings-status-${m.status}`}>
                  {STATUS_LABELS[m.status] || m.status}
                </span>
              </div>
              {m.status !== 'removed' && (
                <button
                  type="button"
                  className="ws-settings-icon-btn ws-settings-icon-btn-danger"
                  onClick={() => handleRemove(m.member_id)}
                  title="Remove member"
                  data-testid={`remove-member-${m.member_id}`}
                >
                  <Trash2 size={14} />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

// ── Main Settings Page ───────────────────────────────────────────────

export default function WorkspaceSettings({ workspaceId, onBack }) {
  const [workspace, setWorkspace] = useState(null)
  const [runtime, setRuntime] = useState(null)
  const [loading, setLoading] = useState(true)
  const [runtimeLoading, setRuntimeLoading] = useState(true)

  const loadWorkspace = useCallback(async () => {
    if (!workspaceId) return
    setLoading(true)
    try {
      const data = await fetchJson(
        `/api/v1/workspaces/${encodeURIComponent(workspaceId)}`,
      )
      setWorkspace(data)
    } catch {
      setWorkspace(null)
    } finally {
      setLoading(false)
    }
  }, [workspaceId])

  const loadRuntime = useCallback(async () => {
    if (!workspaceId) return
    setRuntimeLoading(true)
    try {
      const data = await fetchJson(
        `/api/v1/workspaces/${encodeURIComponent(workspaceId)}/runtime`,
      )
      setRuntime(data?.runtime || data)
    } catch {
      setRuntime({ state: 'unknown' })
    } finally {
      setRuntimeLoading(false)
    }
  }, [workspaceId])

  useEffect(() => {
    loadWorkspace()
    loadRuntime()
  }, [loadWorkspace, loadRuntime])

  const handleRename = useCallback(
    async (newName) => {
      await fetchJson(
        `/api/v1/workspaces/${encodeURIComponent(workspaceId)}`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: newName }),
        },
      )
      await loadWorkspace()
    },
    [workspaceId, loadWorkspace],
  )

  const handleBack = useCallback(() => {
    if (onBack) {
      onBack()
    } else if (workspaceId) {
      window.location.assign(`/w/${encodeURIComponent(workspaceId)}/app`)
    }
  }, [workspaceId, onBack])

  if (loading) {
    return (
      <div className="ws-settings-page" data-testid="workspace-settings">
        <div className="ws-settings-loading">
          <Loader2 size={20} className="ws-spin" />
          <span>Loading workspace settings...</span>
        </div>
      </div>
    )
  }

  if (!workspace) {
    return (
      <div className="ws-settings-page" data-testid="workspace-settings">
        <div className="ws-settings-error-page">
          <p>Workspace not found.</p>
          <button type="button" className="ws-settings-text-btn" onClick={handleBack}>
            <ArrowLeft size={14} />
            <span>Back to workspace</span>
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="ws-settings-page" data-testid="workspace-settings">
      <header className="ws-settings-header">
        <button
          type="button"
          className="ws-settings-back-btn"
          onClick={handleBack}
          data-testid="settings-back"
        >
          <ArrowLeft size={16} />
          <span>Back to workspace</span>
        </button>
        <h1>Settings</h1>
      </header>

      <div className="ws-settings-content">
        <WorkspaceInfo workspace={workspace} onRename={handleRename} />
        <RuntimeStatus runtime={runtime} loading={runtimeLoading} />
        <MembersSection workspaceId={workspaceId} />
      </div>
    </div>
  )
}
