/**
 * Minimal auth token store for hosted mode (bd-1pwb.7.1).
 *
 * Module-level singleton — populated by the hosted login flow,
 * read by apiFetch for Authorization header injection.
 *
 * @module utils/authStore
 */

let _token = null
const TOKEN_KEY = 'boring_ui_auth_token'

const readBrowserToken = () => {
  if (typeof window === 'undefined') return null

  const globalToken = window.__BORING_UI_AUTH_TOKEN
  if (typeof globalToken === 'string' && globalToken.trim()) {
    return globalToken.trim()
  }

  const params = new URLSearchParams(window.location.search)
  const paramToken = params.get('auth_token') || params.get('access_token')
  if (paramToken) return paramToken

  try {
    const sessionToken = window.sessionStorage?.getItem(TOKEN_KEY)
    if (sessionToken) return sessionToken
    const localToken = window.localStorage?.getItem(TOKEN_KEY)
    if (localToken) return localToken
  } catch {
    // Ignore storage access errors
  }

  return null
}

export const setAuthToken = (t) => {
  _token = t || null
  if (typeof window === 'undefined') return
  try {
    if (_token) {
      window.sessionStorage?.setItem(TOKEN_KEY, _token)
      return
    }
    window.sessionStorage?.removeItem(TOKEN_KEY)
    window.localStorage?.removeItem(TOKEN_KEY)
  } catch {
    // Ignore storage access errors
  }
}

export const getAuthToken = () => {
  if (_token) return _token
  const resolved = readBrowserToken()
  if (resolved) _token = resolved
  return _token
}

export const clearAuthToken = () => { setAuthToken(null) }
