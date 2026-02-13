import { useCallback, useEffect, useState } from 'react'
import { buildApiUrl } from '../utils/apiBase'
import { ONBOARDING_STATES, deriveOnboardingState } from '../onboarding/stateMachine'

const PASS_THROUGH_MACHINE = {
  state: ONBOARDING_STATES.WORKSPACE_SELECTED_READY,
  eventTrace: [],
  user: null,
  workspaces: [],
  selectedWorkspace: null,
  selectedWorkspaceId: null,
  runtime: null,
  runtimeState: 'ready',
  isLoading: false,
  errors: {},
  errorCode: '',
  unsupported: false,
}

const readJson = async (response) => {
  const text = await response.text()
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return null
  }
}

const requestJson = async (path, init) => {
  const response = await fetch(buildApiUrl(path), init)
  const data = await readJson(response)

  if (!response.ok) {
    const detail = data?.detail
    const message =
      (typeof detail === 'string' && detail) ||
      (typeof data?.message === 'string' && data.message) ||
      `HTTP ${response.status}`
    const code =
      (typeof data?.code === 'string' && data.code) ||
      (typeof detail === 'object' && typeof detail?.code === 'string' && detail.code) ||
      String(response.status)

    const error = new Error(message)
    error.status = response.status
    error.code = code
    error.detail = detail
    throw error
  }

  return data
}

const extractWorkspaceIdFromPath = () => {
  if (typeof window === 'undefined') return null
  const match = window.location.pathname.match(/^\/w\/([^/]+)/)
  if (!match) return null
  try {
    return decodeURIComponent(match[1])
  } catch {
    return match[1]
  }
}

const extractUser = (payload) => {
  if (!payload) return null
  if (payload.user && typeof payload.user === 'object') return payload.user
  if (payload.user_id || payload.email) return payload
  return null
}

const extractWorkspaces = (payload) => {
  if (!payload) return []
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload.workspaces)) return payload.workspaces
  if (Array.isArray(payload.items)) return payload.items
  return []
}

const extractRuntime = (payload) => {
  if (!payload) return null
  if (payload.runtime && typeof payload.runtime === 'object') return payload.runtime
  return payload
}

const buildError = (error) => ({
  status: error?.status || 0,
  code: error?.code || '',
  message: error?.message || 'Unknown error',
  detail: error?.detail,
})

export const useOnboardingState = ({ enabled = false } = {}) => {
  const [machine, setMachine] = useState(() => ({
    ...PASS_THROUGH_MACHINE,
    isLoading: !!enabled,
  }))

  const loadState = useCallback(async () => {
    if (!enabled) {
      setMachine(PASS_THROUGH_MACHINE)
      return PASS_THROUGH_MACHINE
    }

    setMachine((prev) => ({ ...prev, isLoading: true, unsupported: false }))

    const selectedWorkspaceIdFromUrl = extractWorkspaceIdFromPath()
    const errors = {}

    let user = null

    try {
      user = extractUser(await requestJson('/api/v1/me'))
    } catch (error) {
      if (error?.status === 404) {
        const next = {
          ...PASS_THROUGH_MACHINE,
          unsupported: true,
          errors: { me: buildError(error) },
        }
        setMachine(next)
        return next
      }
      errors.me = buildError(error)
      const next = {
        ...deriveOnboardingState({
          user: null,
          workspaces: [],
          runtime: null,
          selectedWorkspaceId: null,
          loading: false,
          errors,
        }),
        unsupported: false,
      }
      setMachine(next)
      return next
    }

    let workspacesPayload = null
    let workspaceList = []

    try {
      workspacesPayload = await requestJson('/api/v1/workspaces')
      workspaceList = extractWorkspaces(workspacesPayload)
    } catch (error) {
      errors.workspaces = buildError(error)
      if (error?.status === 404) {
        const next = {
          ...PASS_THROUGH_MACHINE,
          unsupported: true,
          user,
          errors,
        }
        setMachine(next)
        return next
      }
      workspaceList = []
    }

    const selectedWorkspaceId =
      selectedWorkspaceIdFromUrl ||
      workspacesPayload?.active_workspace_id ||
      workspacesPayload?.activeWorkspaceId ||
      null

    const selectedWorkspace =
      workspaceList.find((workspace) => {
        const id = workspace?.id || workspace?.workspace_id || workspace?.workspaceId
        return selectedWorkspaceId && id === selectedWorkspaceId
      }) || workspaceList[0] || null

    const resolvedWorkspaceId =
      selectedWorkspace?.id || selectedWorkspace?.workspace_id || selectedWorkspace?.workspaceId || null

    let runtime = null

    if (resolvedWorkspaceId) {
      try {
        const runtimePayload = await requestJson(
          `/api/v1/workspaces/${encodeURIComponent(resolvedWorkspaceId)}/runtime`
        )
        runtime = extractRuntime(runtimePayload)
      } catch (error) {
        errors.runtime = buildError(error)
        runtime = {
          state: 'error',
          last_error_code: errors.runtime.code || 'runtime_status_unavailable',
          last_error_detail: errors.runtime.message,
        }
      }
    }

    const derived = deriveOnboardingState({
      user,
      workspaces: workspaceList,
      runtime,
      selectedWorkspaceId: resolvedWorkspaceId || selectedWorkspaceId,
      loading: false,
      errors,
    })

    const next = {
      ...derived,
      unsupported: false,
    }

    setMachine(next)
    return next
  }, [enabled])

  useEffect(() => {
    loadState()
  }, [loadState])

  const startLogin = useCallback(() => {
    if (typeof window === 'undefined') return
    const nextPath = encodeURIComponent(window.location.pathname + window.location.search)
    window.location.assign(`/auth/login?next=${nextPath}`)
  }, [])

  const startCreateWorkspace = useCallback(() => {
    if (typeof window === 'undefined') return
    window.location.assign('/app/workspaces?create=1')
  }, [])

  const openWorkspaceApp = useCallback((workspaceId) => {
    if (typeof window === 'undefined' || !workspaceId) return
    window.location.assign(`/w/${encodeURIComponent(workspaceId)}/app`)
  }, [])

  const retryProvisioning = useCallback(async () => {
    const workspaceId = machine.selectedWorkspaceId
    if (!workspaceId) return { ok: false, reason: 'missing_workspace_id' }

    try {
      await requestJson(`/api/v1/workspaces/${encodeURIComponent(workspaceId)}/retry`, {
        method: 'POST',
      })
      await loadState()
      return { ok: true }
    } catch (error) {
      await loadState()
      return { ok: false, reason: error?.code || 'retry_failed' }
    }
  }, [loadState, machine.selectedWorkspaceId])

  const isBlocking =
    enabled && !machine.unsupported && machine.state !== ONBOARDING_STATES.WORKSPACE_SELECTED_READY

  return {
    ...machine,
    enabled,
    isBlocking,
    refresh: loadState,
    startLogin,
    startCreateWorkspace,
    openWorkspaceApp,
    retryProvisioning,
  }
}

export default useOnboardingState
