import { buildApiUrl, buildWsUrl } from './apiBase'

const parseJsonResponse = async (response) => {
  const text = await response.text().catch(() => '')
  if (!text) return {}
  try {
    return JSON.parse(text)
  } catch {
    return {}
  }
}

// Local dev auto-login: first 401 sets a session cookie. Retry once per page load.
let _apiFetchRetried = false

export const apiFetch = async (path, options = {}) => {
  const { query, rootScoped = false, ...init } = options
  const url = buildApiUrl(path, query, { rootScoped })
  let response = await fetch(url, { credentials: 'include', ...init })
  if (response.status === 401 && !_apiFetchRetried) {
    _apiFetchRetried = true
    response = await fetch(url, { credentials: 'include', ...init })
  }
  return response
}

export const apiFetchJson = async (path, options = {}) => {
  const response = await apiFetch(path, options)
  const data = await parseJsonResponse(response)
  return { response, data }
}

export const apiFetchText = async (path, options = {}) => {
  const response = await apiFetch(path, options)
  const data = await response.text().catch(() => '')
  return { response, data }
}

export const getHttpErrorDetail = (response, data, fallback = 'Request failed') =>
  data?.detail || data?.message || `${fallback} (${response.status})`

export const openWebSocket = (path, options = {}) => {
  const { query } = options
  return new WebSocket(buildWsUrl(path, query))
}

export const fetchUrl = (url, options = {}) => {
  const init = { ...options }
  delete init.query
  return fetch(url, init)
}

export const fetchJsonUrl = async (url, options = {}) => {
  const response = await fetchUrl(url, options)
  const data = await parseJsonResponse(response)
  return { response, data }
}

export const openWebSocketUrl = (url) => new WebSocket(url)
