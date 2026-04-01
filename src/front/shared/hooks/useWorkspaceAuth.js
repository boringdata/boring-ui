/**
 * useWorkspaceAuth — manages user identity resolution and workspace list.
 *
 * Extracted from App.jsx. Encapsulates:
 * - User identity fetch (GET /me → userId, email, authStatus)
 * - Workspace list fetch (GET /workspaces)
 * - Error states for both
 * - User-scoped storage prefix derivation
 * - Retry and refresh logic
 *
 * @param {Object} options
 * @param {string} options.baseStoragePrefix - Base prefix before user scoping
 * @param {boolean} options.autoRefresh - Whether to load identity/workspaces on mount
 * @returns Auth state, workspace list, and action callbacks
 */
import { useState, useCallback, useEffect, useRef } from 'react'
import { apiFetchJson, getHttpErrorDetail } from '../utils/transport'
import { routeHref, routes } from '../utils/routes'
import {
  extractUserId,
  extractUserEmail,
  normalizeWorkspaceList,
} from '../utils/controlPlane'

const MAX_PRESERVED_IDENTITY_AGE_MS = 30_000

export default function useWorkspaceAuth({
  baseStoragePrefix = '',
  autoRefresh = true,
} = {}) {
  const [userId, setUserId] = useState('')
  const [email, setEmail] = useState('')
  const [authStatus, setAuthStatus] = useState('unknown') // unknown | authenticated | unauthenticated | error
  const [identityError, setIdentityError] = useState('')
  const [workspaceError, setWorkspaceError] = useState('')
  const [workspaces, setWorkspaces] = useState([])
  const [workspaceListStatus, setWorkspaceListStatus] = useState('idle') // idle | loading | success | error

  const lastIdentitySuccessAtRef = useRef(0)

  // User-scoped storage prefix
  const storagePrefix = userId
    ? `${baseStoragePrefix}-u-${userId.slice(0, 12)}`
    : baseStoragePrefix

  // --- Fetch workspace list ---
  const fetchWorkspaces = useCallback(async () => {
    const route = routes.controlPlane.workspaces.list()
    setWorkspaceListStatus('loading')
    try {
      const { response, data } = await apiFetchJson(route.path, {
        query: route.query,
        rootScoped: true,
      })
      if (!response.ok) {
        setWorkspaces([])
        if (response.status === 401) {
          setWorkspaceError('Not signed in.')
        } else if (response.status === 403) {
          setWorkspaceError('Permission denied while loading workspaces.')
        } else {
          setWorkspaceError(getHttpErrorDetail(response, data, 'Failed to load workspaces'))
        }
        setWorkspaceListStatus('error')
        return []
      }
      setWorkspaceError('')
      const list = normalizeWorkspaceList(data)
      setWorkspaces(list)
      setWorkspaceListStatus('success')
      return list
    } catch (error) {
      console.warn('[useWorkspaceAuth] Workspaces load failed:', error)
      setWorkspaces([])
      setWorkspaceError('Failed to reach control plane for workspaces.')
      setWorkspaceListStatus('error')
      return []
    }
  }, [])

  // --- Fetch identity + workspaces ---
  const refreshData = useCallback(async () => {
    const meRoute = routes.controlPlane.me.get()
    setIdentityError('')

    let meResponse = null
    let meData = {}

    try {
      const result = await apiFetchJson(meRoute.path, {
        query: meRoute.query,
        rootScoped: true,
      })
      meResponse = result.response
      meData = result.data
    } catch (error) {
      console.warn('[useWorkspaceAuth] Identity load failed:', error)
      const now = Date.now()
      const identityAgeMs = now - lastIdentitySuccessAtRef.current
      const preserveStableIdentity = (
        authStatus === 'authenticated'
        && userId.length > 0
        && identityAgeMs >= 0
        && identityAgeMs <= MAX_PRESERVED_IDENTITY_AGE_MS
      )
      if (!preserveStableIdentity) {
        setUserId('')
        setEmail('')
        setAuthStatus('error')
      }
      setIdentityError('Failed to reach control plane for identity.')
      return fetchWorkspaces()
    }

    const wsList = await fetchWorkspaces()

    if (meResponse.ok) {
      lastIdentitySuccessAtRef.current = Date.now()
      setAuthStatus('authenticated')
      const uid = extractUserId(meData)
      const em = extractUserEmail(meData)
      setUserId(uid || '')
      setEmail(em || '')
      return wsList
    }

    if (meResponse.status === 401) {
      setUserId('')
      setEmail('')
      setAuthStatus('unauthenticated')
      setIdentityError('Not signed in.')
    } else if (meResponse.status === 403) {
      setUserId('')
      setEmail('')
      setAuthStatus('error')
      setIdentityError('Permission denied while loading identity.')
    } else {
      setUserId('')
      setEmail('')
      setAuthStatus('error')
      setIdentityError(getHttpErrorDetail(meResponse, meData, 'Failed to load identity'))
    }

    return wsList
  }, [fetchWorkspaces, userId, authStatus])

  // --- Auto-fetch on mount ---
  useEffect(() => {
    if (!autoRefresh) return
    refreshData().catch(() => {})
  }, [autoRefresh, refreshData])

  // --- Retry (clears errors first) ---
  const retryData = useCallback(() => {
    setIdentityError('')
    setWorkspaceError('')
    return refreshData()
  }, [refreshData])

  // --- Logout ---
  const logout = useCallback(() => {
    const route = routes.controlPlane.auth.logout()
    window.location.assign(routeHref(route))
  }, [])

  return {
    userId,
    email,
    authStatus,
    identityError,
    workspaceError,
    workspaces,
    workspaceListStatus,
    storagePrefix,
    refreshData,
    fetchWorkspaces,
    retryData,
    logout,
  }
}
