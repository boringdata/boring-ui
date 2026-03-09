import { useState, useEffect, useCallback } from 'react'
import { Github, ExternalLink, Check, Unlink, Loader2, AlertCircle } from 'lucide-react'
import { apiFetchJson } from '../utils/transport'
import { routes } from '../utils/routes'

/**
 * Reusable GitHub connection component.
 *
 * Variants:
 *   - "full"     : Settings page — shows status, connect/disconnect, repo info
 *   - "compact"  : Git changes panel — small "Connect GitHub" button
 *   - "wizard"   : Onboarding wizard — full-width card with skip
 */
export default function GitHubConnect({
  workspaceId,
  variant = 'full',
  onConnected,
  onSkip,
  githubEnabled = true,
}) {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [disconnecting, setDisconnecting] = useState(false)
  const [error, setError] = useState('')

  const fetchStatus = useCallback(async () => {
    if (!githubEnabled) {
      setLoading(false)
      return
    }
    try {
      const route = routes.github.status(workspaceId)
      const qs = route.query ? '?' + new URLSearchParams(route.query).toString() : ''
      const { data } = await apiFetchJson(route.path + qs)
      setStatus(data)
    } catch {
      setError('Failed to check GitHub status')
    } finally {
      setLoading(false)
    }
  }, [workspaceId, githubEnabled])

  useEffect(() => {
    fetchStatus()
  }, [fetchStatus])

  // Listen for OAuth callback via popup/redirect
  useEffect(() => {
    const handler = (event) => {
      if (event.data?.type === 'github-callback' && event.data?.success) {
        fetchStatus()
        onConnected?.()
      }
    }
    window.addEventListener('message', handler)
    return () => window.removeEventListener('message', handler)
  }, [fetchStatus, onConnected])

  const handleConnect = () => {
    // Open GitHub OAuth in new tab — the authorize endpoint redirects to GitHub
    const route = routes.github.authorize()
    window.open(route.path, '_blank', 'noopener')
  }

  const handleDisconnect = async () => {
    setDisconnecting(true)
    try {
      const route = routes.github.disconnect()
      await apiFetchJson(route.path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workspace_id: workspaceId }),
      })
      setStatus({ configured: true, connected: false })
    } catch {
      setError('Failed to disconnect')
    } finally {
      setDisconnecting(false)
    }
  }

  if (!githubEnabled) {
    return null
  }

  // ── Compact variant (for git changes panel) ──────────────────────
  if (variant === 'compact') {
    if (loading) return null
    if (status?.connected) return null

    return (
      <button
        type="button"
        className="github-connect-compact"
        onClick={handleConnect}
        title="Connect GitHub for push/pull"
      >
        <Github size={14} />
        <span>Connect GitHub</span>
      </button>
    )
  }

  // ── Wizard variant (for onboarding) ──────────────────────────────
  if (variant === 'wizard') {
    return (
      <div className="github-connect-wizard">
        <div className="github-connect-wizard-icon">
          <Github size={32} />
        </div>
        <h3 className="github-connect-wizard-title">Connect to GitHub</h3>
        <p className="github-connect-wizard-description">
          Automatically sync your workspace files to a private GitHub repository.
          Changes are backed up and versioned.
        </p>
        {loading ? (
          <div className="github-connect-wizard-loading">
            <Loader2 className="git-inline-spinner" size={16} />
            <span>Checking GitHub status...</span>
          </div>
        ) : status?.connected ? (
          <div className="github-connect-wizard-connected">
            <Check size={16} />
            <span>Connected to GitHub</span>
          </div>
        ) : (
          <button
            type="button"
            className="settings-btn settings-btn-primary github-connect-wizard-btn"
            onClick={handleConnect}
          >
            <Github size={16} />
            Connect GitHub
            <ExternalLink size={14} />
          </button>
        )}
        {error && (
          <div className="github-connect-wizard-error">
            <AlertCircle size={14} />
            {error}
          </div>
        )}
        <button
          type="button"
          className="github-connect-wizard-skip"
          onClick={onSkip}
        >
          Skip for now
        </button>
      </div>
    )
  }

  // ── Full variant (for settings page) ─────────────────────────────
  return (
    <div className="github-connect-full">
      {loading ? (
        <div className="github-connect-loading">
          <Loader2 className="git-inline-spinner" size={14} />
          <span>Checking connection...</span>
        </div>
      ) : !status?.configured ? (
        <div className="github-connect-unconfigured">
          <span className="settings-configured-badge">Not configured</span>
          <span className="github-connect-hint">
            GitHub App not configured on this server.
          </span>
        </div>
      ) : status?.connected ? (
        <div className="github-connect-connected">
          <div className="github-connect-status-row">
            <span className="settings-runtime-badge settings-runtime-badge-running">
              Connected
            </span>
            {status.installation_id && (
              <span className="github-connect-installation">
                Installation #{status.installation_id}
              </span>
            )}
          </div>
          <button
            type="button"
            className="settings-btn settings-btn-secondary"
            onClick={handleDisconnect}
            disabled={disconnecting}
          >
            <Unlink size={14} />
            {disconnecting ? 'Disconnecting...' : 'Disconnect'}
          </button>
        </div>
      ) : (
        <div className="github-connect-disconnected">
          <span className="settings-runtime-badge settings-runtime-badge-pending">
            Not connected
          </span>
          <button
            type="button"
            className="settings-btn settings-btn-primary"
            onClick={handleConnect}
          >
            <Github size={16} />
            Connect GitHub
            <ExternalLink size={14} />
          </button>
        </div>
      )}
      {error && (
        <div className="github-connect-error">
          <AlertCircle size={14} />
          {error}
        </div>
      )}
    </div>
  )
}
