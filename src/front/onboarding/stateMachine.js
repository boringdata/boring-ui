/**
 * Onboarding state machine for Feature 3 control-plane UX.
 *
 * Contract states (from docs/ideas/feature-3-external-control-plane-with-auth.md):
 * - unauthenticated
 * - authenticated_no_workspace
 * - workspace_selected_provisioning
 * - workspace_selected_ready
 * - workspace_selected_error
 */

export const ONBOARDING_STATES = Object.freeze({
  UNAUTHENTICATED: 'unauthenticated',
  AUTHENTICATED_NO_WORKSPACE: 'authenticated_no_workspace',
  WORKSPACE_SELECTED_PROVISIONING: 'workspace_selected_provisioning',
  WORKSPACE_SELECTED_READY: 'workspace_selected_ready',
  WORKSPACE_SELECTED_ERROR: 'workspace_selected_error',
})

export const ONBOARDING_EVENTS = Object.freeze({
  AUTH_REQUIRED: 'AUTH_REQUIRED',
  AUTHENTICATED: 'AUTHENTICATED',
  NO_WORKSPACE: 'NO_WORKSPACE',
  WORKSPACE_SELECTED: 'WORKSPACE_SELECTED',
  RUNTIME_PROVISIONING: 'RUNTIME_PROVISIONING',
  RUNTIME_READY: 'RUNTIME_READY',
  RUNTIME_ERROR: 'RUNTIME_ERROR',
})

const TRANSITIONS = Object.freeze({
  [ONBOARDING_STATES.UNAUTHENTICATED]: {
    [ONBOARDING_EVENTS.AUTH_REQUIRED]: ONBOARDING_STATES.UNAUTHENTICATED,
    [ONBOARDING_EVENTS.AUTHENTICATED]: ONBOARDING_STATES.AUTHENTICATED_NO_WORKSPACE,
  },
  [ONBOARDING_STATES.AUTHENTICATED_NO_WORKSPACE]: {
    [ONBOARDING_EVENTS.AUTH_REQUIRED]: ONBOARDING_STATES.UNAUTHENTICATED,
    [ONBOARDING_EVENTS.AUTHENTICATED]: ONBOARDING_STATES.AUTHENTICATED_NO_WORKSPACE,
    [ONBOARDING_EVENTS.NO_WORKSPACE]: ONBOARDING_STATES.AUTHENTICATED_NO_WORKSPACE,
    [ONBOARDING_EVENTS.WORKSPACE_SELECTED]: ONBOARDING_STATES.WORKSPACE_SELECTED_PROVISIONING,
  },
  [ONBOARDING_STATES.WORKSPACE_SELECTED_PROVISIONING]: {
    [ONBOARDING_EVENTS.AUTH_REQUIRED]: ONBOARDING_STATES.UNAUTHENTICATED,
    [ONBOARDING_EVENTS.NO_WORKSPACE]: ONBOARDING_STATES.AUTHENTICATED_NO_WORKSPACE,
    [ONBOARDING_EVENTS.WORKSPACE_SELECTED]: ONBOARDING_STATES.WORKSPACE_SELECTED_PROVISIONING,
    [ONBOARDING_EVENTS.RUNTIME_PROVISIONING]: ONBOARDING_STATES.WORKSPACE_SELECTED_PROVISIONING,
    [ONBOARDING_EVENTS.RUNTIME_READY]: ONBOARDING_STATES.WORKSPACE_SELECTED_READY,
    [ONBOARDING_EVENTS.RUNTIME_ERROR]: ONBOARDING_STATES.WORKSPACE_SELECTED_ERROR,
  },
  [ONBOARDING_STATES.WORKSPACE_SELECTED_READY]: {
    [ONBOARDING_EVENTS.AUTH_REQUIRED]: ONBOARDING_STATES.UNAUTHENTICATED,
    [ONBOARDING_EVENTS.NO_WORKSPACE]: ONBOARDING_STATES.AUTHENTICATED_NO_WORKSPACE,
    [ONBOARDING_EVENTS.WORKSPACE_SELECTED]: ONBOARDING_STATES.WORKSPACE_SELECTED_PROVISIONING,
    [ONBOARDING_EVENTS.RUNTIME_PROVISIONING]: ONBOARDING_STATES.WORKSPACE_SELECTED_PROVISIONING,
    [ONBOARDING_EVENTS.RUNTIME_READY]: ONBOARDING_STATES.WORKSPACE_SELECTED_READY,
    [ONBOARDING_EVENTS.RUNTIME_ERROR]: ONBOARDING_STATES.WORKSPACE_SELECTED_ERROR,
  },
  [ONBOARDING_STATES.WORKSPACE_SELECTED_ERROR]: {
    [ONBOARDING_EVENTS.AUTH_REQUIRED]: ONBOARDING_STATES.UNAUTHENTICATED,
    [ONBOARDING_EVENTS.NO_WORKSPACE]: ONBOARDING_STATES.AUTHENTICATED_NO_WORKSPACE,
    [ONBOARDING_EVENTS.WORKSPACE_SELECTED]: ONBOARDING_STATES.WORKSPACE_SELECTED_PROVISIONING,
    [ONBOARDING_EVENTS.RUNTIME_PROVISIONING]: ONBOARDING_STATES.WORKSPACE_SELECTED_PROVISIONING,
    [ONBOARDING_EVENTS.RUNTIME_READY]: ONBOARDING_STATES.WORKSPACE_SELECTED_READY,
    [ONBOARDING_EVENTS.RUNTIME_ERROR]: ONBOARDING_STATES.WORKSPACE_SELECTED_ERROR,
  },
})

const PROVISIONING_RUNTIME_STATES = new Set([
  'queued',
  'provisioning',
  'creating_sandbox',
  'uploading_artifact',
  'bootstrapping',
  'health_check',
  'retrying',
])

const READY_RUNTIME_STATES = new Set(['ready'])
const ERROR_RUNTIME_STATES = new Set(['error', 'failed'])

const toStringOrEmpty = (value) =>
  typeof value === 'string' ? value.trim() : ''

const normalizeRuntimeState = (runtimeState) => {
  const state = toStringOrEmpty(runtimeState).toLowerCase()
  if (!state) return ''
  if (PROVISIONING_RUNTIME_STATES.has(state)) return 'provisioning'
  if (READY_RUNTIME_STATES.has(state)) return 'ready'
  if (ERROR_RUNTIME_STATES.has(state)) return 'error'
  return state
}

const extractWorkspaceId = (workspace) =>
  workspace?.id || workspace?.workspace_id || workspace?.workspaceId || null

const extractRuntimeState = (workspace, runtime) => {
  const runtimeState =
    runtime?.runtime_state ||
    runtime?.state ||
    workspace?.runtime_state ||
    workspace?.runtime?.state ||
    workspace?.runtime?.runtime_state ||
    ''
  return normalizeRuntimeState(runtimeState)
}

const normalizeErrorCode = (value) => {
  if (!value) return ''
  if (typeof value === 'string') return value
  if (typeof value === 'number') return String(value)
  return ''
}

const selectWorkspace = (workspaces, preferredWorkspaceId) => {
  if (!Array.isArray(workspaces) || workspaces.length === 0) return null

  if (preferredWorkspaceId) {
    const selected = workspaces.find((workspace) => extractWorkspaceId(workspace) === preferredWorkspaceId)
    if (selected) return selected
  }

  return workspaces[0]
}

export const advanceOnboardingState = (currentState, eventType) => {
  const table = TRANSITIONS[currentState]
  if (!table) return currentState
  return table[eventType] || currentState
}

/**
 * Derive a deterministic onboarding state from auth/workspace/runtime snapshots.
 */
export const deriveOnboardingState = ({
  user,
  workspaces,
  runtime,
  selectedWorkspaceId,
  loading = false,
  errors = {},
}) => {
  const meErrorCode = normalizeErrorCode(errors?.me?.code || errors?.me?.status)
  const workspacesErrorCode = normalizeErrorCode(errors?.workspaces?.code || errors?.workspaces?.status)
  const runtimeErrorCode = normalizeErrorCode(errors?.runtime?.code || errors?.runtime?.status)

  const eventTrace = []
  let currentState = ONBOARDING_STATES.UNAUTHENTICATED

  const authMissing = !user || meErrorCode === '401' || meErrorCode === 'unauthorized'

  if (authMissing) {
    eventTrace.push(ONBOARDING_EVENTS.AUTH_REQUIRED)
    currentState = advanceOnboardingState(currentState, ONBOARDING_EVENTS.AUTH_REQUIRED)
    return {
      state: currentState,
      eventTrace,
      user: null,
      workspaces: [],
      selectedWorkspace: null,
      selectedWorkspaceId: null,
      runtime: null,
      runtimeState: '',
      isLoading: !!loading,
      errors,
      errorCode: meErrorCode,
    }
  }

  eventTrace.push(ONBOARDING_EVENTS.AUTHENTICATED)
  currentState = advanceOnboardingState(currentState, ONBOARDING_EVENTS.AUTHENTICATED)

  const workspaceList = Array.isArray(workspaces) ? workspaces : []
  const selectedWorkspace = selectWorkspace(workspaceList, selectedWorkspaceId)
  const resolvedWorkspaceId = extractWorkspaceId(selectedWorkspace)

  if (!selectedWorkspace || workspaceList.length === 0) {
    eventTrace.push(ONBOARDING_EVENTS.NO_WORKSPACE)
    currentState = advanceOnboardingState(currentState, ONBOARDING_EVENTS.NO_WORKSPACE)
    return {
      state: currentState,
      eventTrace,
      user,
      workspaces: workspaceList,
      selectedWorkspace: null,
      selectedWorkspaceId: null,
      runtime: null,
      runtimeState: '',
      isLoading: !!loading,
      errors,
      errorCode: workspacesErrorCode,
    }
  }

  eventTrace.push(ONBOARDING_EVENTS.WORKSPACE_SELECTED)
  currentState = advanceOnboardingState(currentState, ONBOARDING_EVENTS.WORKSPACE_SELECTED)

  const runtimeState = extractRuntimeState(selectedWorkspace, runtime)

  if (runtimeState === 'ready') {
    eventTrace.push(ONBOARDING_EVENTS.RUNTIME_READY)
    currentState = advanceOnboardingState(currentState, ONBOARDING_EVENTS.RUNTIME_READY)
  } else if (runtimeState === 'error') {
    eventTrace.push(ONBOARDING_EVENTS.RUNTIME_ERROR)
    currentState = advanceOnboardingState(currentState, ONBOARDING_EVENTS.RUNTIME_ERROR)
  } else {
    eventTrace.push(ONBOARDING_EVENTS.RUNTIME_PROVISIONING)
    currentState = advanceOnboardingState(currentState, ONBOARDING_EVENTS.RUNTIME_PROVISIONING)
  }

  return {
    state: currentState,
    eventTrace,
    user,
    workspaces: workspaceList,
    selectedWorkspace,
    selectedWorkspaceId: resolvedWorkspaceId,
    runtime,
    runtimeState,
    isLoading: !!loading,
    errors,
    errorCode: runtimeErrorCode || workspacesErrorCode || meErrorCode,
  }
}
