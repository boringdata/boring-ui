import { useCallback, useEffect, useMemo, useState } from 'react'
import { Rocket, ArrowRight, Github, ExternalLink, Loader2, Check, ServerCog, RefreshCw, AlertTriangle } from 'lucide-react'
import { useGitHubConnection } from '../components/GitHubConnect'
import { apiFetch, apiFetchJson } from '../utils/transport'
import { routeHref, routes } from '../utils/routes'
import { getRuntimeStatus, isRuntimeReady, shouldRetryRuntime } from '../utils/controlPlane'
import PageShell from './PageShell'

/**
 * Post-creation onboarding wizard.
 * Currently a single-step wizard for GitHub connection (skippable).
 * Can be extended with more steps later.
 */
export default function WorkspaceSetupPage({
  workspaceId,
  workspaceName,
  capabilities,
  capabilitiesPending = false,
  onComplete,
}) {
  const [setupPayload, setSetupPayload] = useState(null)
  const [setupLoading, setSetupLoading] = useState(true)
  const [setupError, setSetupError] = useState('')
  const [retryingRuntime, setRetryingRuntime] = useState(false)
  const capabilitiesLoaded = !capabilitiesPending && capabilities != null
  const githubEnabled = capabilities?.features?.github === true
  const { status, loading, connect } = useGitHubConnection(workspaceId, { enabled: githubEnabled })

  const runtimePayload = useMemo(
    () => setupPayload?.runtime || setupPayload?.data?.runtime || setupPayload || null,
    [setupPayload],
  )
  const runtimeState = getRuntimeStatus(runtimePayload)
  const runtimeReady = isRuntimeReady(runtimePayload)
  const runtimeRetryable = shouldRetryRuntime(runtimePayload)
  const provisioningStep = String(runtimePayload?.provisioning_step || '').trim()

  const handleDone = useCallback(() => {
    onComplete?.()
  }, [onComplete])

  const loadSetup = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setSetupLoading(true)
    try {
      const route = routes.controlPlane.workspaces.setup(workspaceId)
      const { response, data } = await apiFetchJson(route.path, {
        query: route.query,
        headers: { Accept: 'application/json' },
      })
      if (response.status === 401) {
        const loginRoute = routes.controlPlane.auth.login(
          `${window.location.pathname}${window.location.search}`,
        )
        window.location.assign(routeHref(loginRoute))
        return
      }
      if (!response.ok) {
        throw new Error(data?.message || 'Failed to load workspace setup')
      }
      setSetupPayload(data)
      setSetupError('')
    } catch (error) {
      setSetupError(error?.message || 'Failed to prepare workspace')
    } finally {
      setSetupLoading(false)
    }
  }, [workspaceId])

  useEffect(() => {
    loadSetup()
  }, [loadSetup])

  useEffect(() => {
    if (!workspaceId || setupLoading || setupError || runtimeReady) return
    const timer = window.setTimeout(() => {
      loadSetup({ silent: true })
    }, 2000)
    return () => window.clearTimeout(timer)
  }, [loadSetup, runtimeReady, setupError, setupLoading, workspaceId])

  const handleRetryRuntime = useCallback(async () => {
    setRetryingRuntime(true)
    try {
      const route = routes.controlPlane.workspaces.runtime.retry(workspaceId)
      await apiFetch(route.path, {
        query: route.query,
        method: 'POST',
      })
      await loadSetup({ silent: true })
    } finally {
      setRetryingRuntime(false)
    }
  }, [loadSetup, workspaceId])

  // If GitHub is not enabled, skip the wizard entirely — but only after capabilities load
  useEffect(() => {
    if (runtimeReady && capabilitiesLoaded && !githubEnabled) handleDone()
  }, [capabilitiesLoaded, githubEnabled, handleDone, runtimeReady])

  const runtimeStateLabel = runtimeState
    ? runtimeState.charAt(0).toUpperCase() + runtimeState.slice(1)
    : 'Provisioning'

  if (setupLoading && !setupPayload) {
    return (
      <PageShell title={`Preparing ${workspaceName || 'Workspace'}`}>
        <div className="setup-wizard">
          <div className="setup-wizard-header">
            <ServerCog size={24} />
            <h2 className="setup-wizard-title">Creating your backend workspace</h2>
            <p className="setup-wizard-subtitle">
              We’re starting a dedicated machine for this workspace. This usually takes a few seconds.
            </p>
          </div>
          <div className="setup-wizard-step setup-wizard-step-status">
            <div className="setup-wizard-loading">
              <Loader2 className="git-inline-spinner" size={16} />
              <span>Provisioning workspace runtime…</span>
            </div>
          </div>
        </div>
      </PageShell>
    )
  }

  if (setupError) {
    return (
      <PageShell title={`Preparing ${workspaceName || 'Workspace'}`}>
        <div className="setup-wizard">
          <div className="setup-wizard-header">
            <AlertTriangle size={24} />
            <h2 className="setup-wizard-title">Workspace setup hit a problem</h2>
            <p className="setup-wizard-subtitle">{setupError}</p>
          </div>
          <div className="setup-wizard-footer">
            <button
              type="button"
              className="settings-btn settings-btn-primary setup-wizard-continue"
              onClick={() => loadSetup()}
            >
              <RefreshCw size={16} />
              Retry
            </button>
          </div>
        </div>
      </PageShell>
    )
  }

  if (!runtimeReady) {
    return (
      <PageShell title={`Preparing ${workspaceName || 'Workspace'}`}>
        <div className="setup-wizard">
          <div className="setup-wizard-header">
            <ServerCog size={24} />
            <h2 className="setup-wizard-title">Preparing your workspace</h2>
            <p className="setup-wizard-subtitle">
              We’ll take you into the workspace as soon as the backend is ready.
            </p>
          </div>

          <div className="setup-wizard-step setup-wizard-step-status">
            <div className="setup-wizard-status-row">
              <span className={`settings-runtime-badge ${
                runtimeState === 'error'
                  ? 'settings-runtime-badge-error'
                  : runtimeState === 'ready'
                    ? 'settings-runtime-badge-running'
                    : 'settings-runtime-badge-provisioning'
              }`}
              >
                {runtimeStateLabel}
              </span>
              <span className="setup-wizard-status-copy">
                {provisioningStep || 'Starting workspace machine and loading services…'}
              </span>
            </div>
            <div className="setup-wizard-loading">
              <Loader2 className="git-inline-spinner" size={16} />
              <span>Checking runtime status…</span>
            </div>
          </div>

          <div className="setup-wizard-footer">
            {runtimeRetryable ? (
              <button
                type="button"
                className="settings-btn settings-btn-primary setup-wizard-continue"
                onClick={handleRetryRuntime}
                disabled={retryingRuntime}
              >
                <RefreshCw size={16} />
                {retryingRuntime ? 'Retrying…' : 'Retry setup'}
              </button>
            ) : (
              <div className="setup-wizard-footnote">This page updates automatically while the workspace starts.</div>
            )}
          </div>
        </div>
      </PageShell>
    )
  }

  if (!capabilitiesLoaded) {
    return (
      <PageShell title={`Preparing ${workspaceName || 'Workspace'}`}>
        <div className="setup-wizard">
          <div className="setup-wizard-header">
            <Rocket size={24} />
            <h2 className="setup-wizard-title">Workspace is ready</h2>
            <p className="setup-wizard-subtitle">
              Loading workspace tools and connection options…
            </p>
          </div>
          <div className="setup-wizard-step setup-wizard-step-status">
            <div className="setup-wizard-loading">
              <Loader2 className="git-inline-spinner" size={16} />
              <span>Loading workspace capabilities…</span>
            </div>
          </div>
        </div>
      </PageShell>
    )
  }

  if (!githubEnabled) return null

  const connected = Boolean(status?.account_linked ?? status?.connected)

  return (
    <PageShell title={`Set up ${workspaceName || 'Workspace'}`}>
      <div className="setup-wizard">
        <div className="setup-wizard-header">
          <Rocket size={24} />
          <h2 className="setup-wizard-title">Get started</h2>
          <p className="setup-wizard-subtitle">
            Link your GitHub account, verify app access, then choose a repo for this workspace.
          </p>
        </div>

        <div className="setup-wizard-step">
          {loading ? (
            <div className="setup-wizard-loading">
              <Loader2 className="git-inline-spinner" size={16} />
              <span>Checking GitHub status...</span>
            </div>
          ) : connected ? (
            <div className="setup-wizard-connected">
              <Check size={16} />
              <span>GitHub account verified</span>
            </div>
          ) : (
            <button
              type="button"
              className="settings-btn settings-btn-primary"
              onClick={connect}
            >
              <Github size={16} />
              Link GitHub Account
              <ExternalLink size={14} />
            </button>
          )}
        </div>

        <div className="setup-wizard-footer">
          <button
            type="button"
            className="settings-btn settings-btn-primary setup-wizard-continue"
            onClick={handleDone}
          >
            {connected ? 'Continue to workspace' : 'Skip for now'}
            <ArrowRight size={16} />
          </button>
        </div>
      </div>
    </PageShell>
  )
}
