import { useState, useEffect, useCallback, useMemo } from 'react'
import { Github, ExternalLink, Unlink, Loader2, AlertCircle, Check } from 'lucide-react'
import { useLightningFsGitBootstrap } from '../hooks/useLightningFsGitBootstrap'
import { apiFetchJson } from '../utils/transport'
import { routes } from '../utils/routes'

const normalizeGitHubRepoUrl = (value) => {
  const raw = String(value || '').trim()
  if (!raw) return ''
  if (raw.startsWith('git@github.com:')) {
    return `https://github.com/${raw.slice('git@github.com:'.length).replace(/\.git$/i, '')}`.toLowerCase()
  }
  return raw.replace(/\.git$/i, '').replace(/\/+$/g, '').toLowerCase()
}

/**
 * Hook for GitHub connection state and actions.
 * Shared by all GitHub connection UI surfaces.
 */
export function useGitHubConnection(workspaceId, { enabled = true } = {}) {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [disconnecting, setDisconnecting] = useState(false)
  const [error, setError] = useState('')

  const fetchStatus = useCallback(async () => {
    if (!enabled) { setLoading(false); return }
    try {
      const route = routes.github.status(workspaceId)
      const qs = route.query ? '?' + new URLSearchParams(route.query).toString() : ''
      const { data } = await apiFetchJson(route.path + qs)

      // Auto-connect: if configured but not connected, check for existing installations
      if (data?.configured && !data?.connected && workspaceId) {
        try {
          const { data: instData } = await apiFetchJson(routes.github.installations().path)
          const installations = instData?.installations || []
          if (installations.length > 0) {
            const installationId = installations[0].id
            const { response } = await apiFetchJson(routes.github.connect().path, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ workspace_id: workspaceId, installation_id: installationId }),
            })
            if (response.ok) {
              setStatus({
                configured: true,
                connected: true,
                installation_connected: true,
                installation_id: installationId,
                repo_selected: false,
                repo_url: null,
              })
              return
            }
          }
        } catch {
          // Auto-connect failed silently — show normal disconnected state
        }
      }

      setStatus(data)
    } catch {
      setError('Failed to check GitHub status')
    } finally {
      setLoading(false)
    }
  }, [workspaceId, enabled])

  useEffect(() => { fetchStatus() }, [fetchStatus])

  // Listen for OAuth callback via postMessage from popup
  useEffect(() => {
    const handler = (event) => {
      if (event.origin !== window.location.origin) return
      if (event.data?.type === 'github-callback' && event.data?.success) {
        fetchStatus()
      }
    }
    window.addEventListener('message', handler)
    return () => window.removeEventListener('message', handler)
  }, [fetchStatus])

  const connect = useCallback(async () => {
    // First check if the app is already installed — auto-connect if so
    try {
      const { data: instData } = await apiFetchJson(routes.github.installations().path)
      const installations = instData?.installations || []
      if (installations.length > 0 && workspaceId) {
        // App is already installed — connect directly without leaving the page
        const installationId = installations[0].id
        await apiFetchJson(routes.github.connect().path, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ workspace_id: workspaceId, installation_id: installationId }),
        })
        fetchStatus()
        return
      }
    } catch {
      // Fall through to installation flow
    }

    // No installation found — open GitHub App install page
    const authPath = routes.github.authorize().path
    const url = workspaceId ? `${authPath}?workspace_id=${encodeURIComponent(workspaceId)}` : authPath
    window.open(url, '_blank')
  }, [workspaceId, fetchStatus])

  const disconnect = useCallback(async () => {
    setDisconnecting(true)
    try {
      await apiFetchJson(routes.github.disconnect().path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workspace_id: workspaceId }),
      })
      setStatus({
        configured: true,
        connected: false,
        installation_connected: false,
        installation_id: null,
        repo_selected: false,
        repo_url: null,
      })
    } catch {
      setError('Failed to disconnect')
    } finally {
      setDisconnecting(false)
    }
  }, [workspaceId])

  return { status, loading, error, disconnecting, connect, disconnect, refetch: fetchStatus }
}

/**
 * Full GitHub connection UI for the workspace settings page.
 * Shows status, connect/disconnect buttons, installation info.
 */
export default function GitHubConnect({ workspaceId }) {
  const { status, loading, error, disconnecting, connect, disconnect, refetch } = useGitHubConnection(workspaceId)
  const [repos, setRepos] = useState([])
  const [repoError, setRepoError] = useState('')
  const [selectingRepoUrl, setSelectingRepoUrl] = useState('')

  const installationConnected = !!(status?.installation_connected ?? status?.connected)
  const selectedRepoUrl = normalizeGitHubRepoUrl(status?.repo_url)
  const bootstrap = useLightningFsGitBootstrap({
    workspaceId,
    enabled: true,
    installationConnected,
    repoUrl: status?.repo_url || '',
    autoBootstrap: false,
  })

  useEffect(() => {
    if (!installationConnected || !status?.installation_id) {
      setRepos([])
      return
    }
    const route = routes.github.repos(status.installation_id)
    const qs = route.query ? `?${new URLSearchParams(route.query).toString()}` : ''
    apiFetchJson(route.path + qs)
      .then(({ data }) => {
        setRepoError('')
        setRepos(Array.isArray(data?.repos) ? data.repos : [])
      })
      .catch(() => {
        setRepos([])
        setRepoError('Failed to load the GitHub repo list')
      })
  }, [installationConnected, status?.installation_id])

  const selectedRepo = useMemo(
    () => repos.find((repo) => normalizeGitHubRepoUrl(repo?.clone_url) === selectedRepoUrl) || null,
    [repos, selectedRepoUrl],
  )

  const handleSelectRepo = useCallback(async (repo) => {
    const repoUrl = repo?.clone_url || ''
    if (!workspaceId || !repoUrl) return
    setRepoError('')
    setSelectingRepoUrl(repoUrl)
    try {
      await apiFetchJson(routes.github.selectRepo().path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workspace_id: workspaceId, repo_url: repoUrl }),
      })
      await refetch()
    } catch {
      setRepoError('Failed to save the selected repo')
    } finally {
      setSelectingRepoUrl('')
    }
  }, [refetch, workspaceId])

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
      ) : installationConnected ? (
        <div className="github-connect-connected">
          <div className="github-connect-status-grid">
            <div className="github-connect-status-card">
              <span className="github-connect-status-label">App installation</span>
              <div className="github-connect-status-row">
                <span className="settings-runtime-badge settings-runtime-badge-running">
                  Installed
                </span>
                {status?.installation_id && (
                  <span className="github-connect-installation">
                    Installation #{status.installation_id}
                  </span>
                )}
              </div>
            </div>
            <div className="github-connect-status-card">
              <span className="github-connect-status-label">Workspace repo</span>
              <div className="github-connect-status-row">
                <span className={`settings-runtime-badge ${status?.repo_selected ? 'settings-runtime-badge-running' : 'settings-runtime-badge-pending'}`}>
                  {status?.repo_selected ? 'Selected' : 'Not selected'}
                </span>
                {selectedRepo?.full_name && (
                  <a
                    className="github-connect-selected-link"
                    href={selectedRepo.clone_url?.replace(/\.git$/, '') || '#'}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <span>{selectedRepo.full_name}</span>
                    <ExternalLink size={12} />
                  </a>
                )}
              </div>
            </div>
          </div>
          <span className="github-connect-hint">
            {status?.repo_selected
              ? bootstrap.syncReady
                ? 'This workspace is linked to the selected GitHub repo.'
                : bootstrap.message || 'GitHub repo selected, but browser workspace sync is not ready yet.'
              : 'GitHub is installed. Pick one repo from the allowed list below for this workspace.'}
          </span>
          {status?.repo_selected && !bootstrap.syncReady && (
            <div className="github-connect-error">
              <AlertCircle size={14} />
              {bootstrap.error || bootstrap.message}
            </div>
          )}
          {repos.length > 0 ? (
            <div className="github-connect-repo-list" role="list">
              {repos.map((repo) => {
                const repoUrl = normalizeGitHubRepoUrl(repo?.clone_url)
                const isSelected = repoUrl === selectedRepoUrl
                const isSaving = selectingRepoUrl === repo?.clone_url
                return (
                  <div key={repo.full_name} className={`github-connect-repo-card${isSelected ? ' github-connect-repo-card--selected' : ''}`} role="listitem">
                    <div className="github-connect-repo-main">
                      <div className="github-connect-repo-title-row">
                        <span className="github-connect-repo-name">{repo.full_name}</span>
                        {isSelected && (
                          <span className="github-connect-repo-selected-pill">
                            <Check size={12} />
                            Selected
                          </span>
                        )}
                      </div>
                      <span className="github-connect-repo-visibility">
                        {repo.private ? 'Private repo' : 'Public repo'}
                      </span>
                    </div>
                    <div className="github-connect-repo-actions">
                      <a
                        className="github-connect-repo-link"
                        href={repo.clone_url?.replace(/\.git$/, '') || '#'}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        <Github size={14} />
                        <span>Open repo</span>
                        <ExternalLink size={12} />
                      </a>
                      <button
                        type="button"
                        className={`settings-btn ${isSelected ? 'settings-btn-secondary' : 'settings-btn-primary'}`}
                        onClick={() => handleSelectRepo(repo)}
                        disabled={isSaving || isSelected}
                      >
                        {isSaving ? 'Saving...' : isSelected ? 'Selected' : 'Use this repo'}
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <span className="github-connect-hint">
              No accessible repos were returned for this installation yet.
            </span>
          )}
          <button
            type="button"
            className="settings-btn settings-btn-secondary"
            onClick={disconnect}
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
            onClick={connect}
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
      {repoError && (
        <div className="github-connect-error">
          <AlertCircle size={14} />
          {repoError}
        </div>
      )}
    </div>
  )
}
