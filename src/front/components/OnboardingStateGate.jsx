import { AlertTriangle, Loader2, LogIn, RefreshCw, Rocket } from 'lucide-react'
import { ONBOARDING_STATES } from '../onboarding/stateMachine'

const getWorkspaceName = (workspace) =>
  workspace?.name || workspace?.workspace_name || workspace?.slug || workspace?.id || 'workspace'

const getRuntimeErrorCode = (machine) =>
  machine?.runtime?.last_error_code || machine?.errors?.runtime?.code || machine?.errorCode || ''

const getRuntimeErrorDetail = (machine) =>
  machine?.runtime?.last_error_detail || machine?.errors?.runtime?.message || ''

const PRIMARY_ACTIONS = {
  [ONBOARDING_STATES.UNAUTHENTICATED]: {
    label: 'Sign in',
    icon: LogIn,
    run: (machine) => machine.startLogin(),
  },
  [ONBOARDING_STATES.AUTHENTICATED_NO_WORKSPACE]: {
    label: 'Create workspace',
    icon: Rocket,
    run: (machine) => machine.startCreateWorkspace(),
  },
  [ONBOARDING_STATES.WORKSPACE_SELECTED_READY]: {
    label: 'Open workspace app',
    icon: Rocket,
    run: (machine) => machine.openWorkspaceApp(machine.selectedWorkspaceId),
  },
  [ONBOARDING_STATES.WORKSPACE_SELECTED_ERROR]: {
    label: 'Retry provisioning',
    icon: RefreshCw,
    run: (machine) => machine.retryProvisioning(),
  },
}

const STATE_COPY = {
  [ONBOARDING_STATES.UNAUTHENTICATED]: {
    title: 'Sign in required',
    description: 'Authenticate to continue to workspace onboarding.',
  },
  [ONBOARDING_STATES.AUTHENTICATED_NO_WORKSPACE]: {
    title: 'Create your first workspace',
    description: 'No workspace is available yet for this account.',
  },
  [ONBOARDING_STATES.WORKSPACE_SELECTED_PROVISIONING]: {
    title: 'Provisioning workspace runtime',
    description: 'Your workspace is being prepared. This can take a moment.',
  },
  [ONBOARDING_STATES.WORKSPACE_SELECTED_READY]: {
    title: 'Workspace ready',
    description: 'Runtime is ready. Continue to the workspace application.',
  },
  [ONBOARDING_STATES.WORKSPACE_SELECTED_ERROR]: {
    title: 'Provisioning failed',
    description: 'Runtime setup ended in an error. Review details and retry.',
  },
}

export default function OnboardingStateGate({ machine }) {
  const copy = STATE_COPY[machine.state] || STATE_COPY[ONBOARDING_STATES.UNAUTHENTICATED]
  const workspaceName = getWorkspaceName(machine.selectedWorkspace)
  const runtimeErrorCode = getRuntimeErrorCode(machine)
  const runtimeErrorDetail = getRuntimeErrorDetail(machine)
  const primaryAction = PRIMARY_ACTIONS[machine.state]
  const PrimaryIcon = primaryAction?.icon

  return (
    <div className="onboarding-gate" data-testid="onboarding-gate">
      <div className="onboarding-card">
        <div className="onboarding-card-header">
          <h1>{copy.title}</h1>
          <p>{copy.description}</p>
        </div>

        {machine.state === ONBOARDING_STATES.WORKSPACE_SELECTED_PROVISIONING && (
          <div className="onboarding-state-pill" role="status" aria-live="polite">
            <Loader2 size={16} className="onboarding-spin" />
            <span>
              {machine.isLoading ? 'Refreshing status…' : `Provisioning ${workspaceName}`}
            </span>
          </div>
        )}

        {machine.state === ONBOARDING_STATES.WORKSPACE_SELECTED_ERROR && (
          <div className="onboarding-error" role="alert">
            <AlertTriangle size={16} />
            <div>
              <div className="onboarding-error-code">
                Error code: {runtimeErrorCode || 'provisioning_failed'}
              </div>
              {runtimeErrorDetail && (
                <div className="onboarding-error-detail">{runtimeErrorDetail}</div>
              )}
            </div>
          </div>
        )}

        {machine.selectedWorkspaceId && (
          <div className="onboarding-meta">
            <span>Workspace: {workspaceName}</span>
            <span>State: {machine.state}</span>
          </div>
        )}

        <div className="onboarding-actions">
          {primaryAction && (
            <button
              type="button"
              className="onboarding-primary-btn"
              onClick={() => primaryAction.run(machine)}
            >
              {PrimaryIcon ? <PrimaryIcon size={16} /> : null}
              <span>{primaryAction.label}</span>
            </button>
          )}

          <button
            type="button"
            className="onboarding-secondary-btn"
            onClick={machine.refresh}
          >
            Refresh status
          </button>
        </div>
      </div>
    </div>
  )
}
