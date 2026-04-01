/**
 * useSessionState — chat-session state for the chat-centered shell.
 *
 * The shell needs session-scoped chat state even in browser mode where the
 * transport does not yet provide a first-class session manager. This store owns:
 *
 * - active session pointer
 * - session metadata ordering and status
 * - per-session UI messages
 * - per-session composer draft
 * - lightweight local persistence for shell reloads
 */

import { useSyncExternalStore, useCallback } from 'react'

const STORAGE_KEY = 'boring-ui:chat-sessions:v1'
const DEFAULT_SESSION_TITLE = 'New chat'

function createSessionRecord(metadata = {}) {
  const now = Number(metadata.lastModified) || Date.now()
  return {
    id: String(metadata.id || ''),
    title: String(metadata.title || DEFAULT_SESSION_TITLE),
    lastModified: now,
    status: String(metadata.status || 'idle'),
    draft: String(metadata.draft || ''),
    messages: Array.isArray(metadata.messages) ? metadata.messages : [],
  }
}

function serializeState(snapshot) {
  return JSON.stringify({
    activeSessionId: snapshot.activeSessionId,
    sessions: Array.from(snapshot.sessionsById.values()),
  })
}

function loadPersistedState() {
  try {
    const raw = window.localStorage?.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    const sessions = Array.isArray(parsed?.sessions) ? parsed.sessions : []
    const sessionsById = new Map()

    sessions.forEach((session) => {
      const record = createSessionRecord(session)
      if (record.id) {
        sessionsById.set(record.id, record)
      }
    })

    const activeSessionId = String(parsed?.activeSessionId || '').trim() || null
    return {
      activeSessionId: activeSessionId && sessionsById.has(activeSessionId) ? activeSessionId : null,
      sessionsById,
    }
  } catch {
    return null
  }
}

function persistState(nextState) {
  try {
    window.localStorage?.setItem(STORAGE_KEY, serializeState(nextState))
  } catch {
    // Best-effort only.
  }
}

// ---------------------------------------------------------------------------
// Internal store (module-level singleton, survives re-renders)
// ---------------------------------------------------------------------------

function createInitialState() {
  return (
    loadPersistedState() || {
      activeSessionId: null,
      sessionsById: new Map(),
    }
  )
}

let state = createInitialState()

const listeners = new Set()

function emitChange() {
  for (const listener of listeners) {
    listener()
  }
}

function subscribe(listener) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/**
 * Returns sessions sorted by lastModified descending (most recent first).
 */
function getSortedSessions() {
  return Array.from(state.sessionsById.values()).sort(
    (a, b) => b.lastModified - a.lastModified
  )
}

function getSnapshot() {
  return state
}

function commitState(nextState) {
  state = nextState
  persistState(nextState)
  emitChange()
}

function getInactiveStatus(session) {
  if (!session) return 'idle'
  if (Array.isArray(session.messages) && session.messages.length > 0) return 'paused'
  if (String(session.draft || '').trim()) return 'paused'
  return 'idle'
}

function deriveSessionTitle(messages, currentTitle = DEFAULT_SESSION_TITLE) {
  const title = String(currentTitle || DEFAULT_SESSION_TITLE).trim()
  if (title && title !== DEFAULT_SESSION_TITLE) return title

  const firstUserMessage = (messages || []).find((message) => message?.role === 'user')
  if (!firstUserMessage) return DEFAULT_SESSION_TITLE

  const parts = Array.isArray(firstUserMessage.parts) ? firstUserMessage.parts : []
  const partText = parts
    .filter((part) => part?.type === 'text' && typeof part.text === 'string')
    .map((part) => part.text)
    .join(' ')
    .trim()
  const contentText = typeof firstUserMessage.content === 'string'
    ? firstUserMessage.content.trim()
    : ''
  const sourceText = partText || contentText
  if (!sourceText) return DEFAULT_SESSION_TITLE

  return sourceText.length > 48 ? `${sourceText.slice(0, 45).trimEnd()}...` : sourceText
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

function switchSession(id) {
  if (!id || !state.sessionsById.has(id) || state.activeSessionId === id) return

  const nextMap = new Map(state.sessionsById)
  const previousActive = state.activeSessionId ? nextMap.get(state.activeSessionId) : null
  if (previousActive) {
    nextMap.set(previousActive.id, {
      ...previousActive,
      status: getInactiveStatus(previousActive),
    })
  }

  const nextActive = nextMap.get(id)
  nextMap.set(id, {
    ...nextActive,
    status: 'active',
    lastModified: Date.now(),
  })

  commitState({
    ...state,
    activeSessionId: id,
    sessionsById: nextMap,
  })
}

function createNewSession(overrides = {}) {
  const id = String(overrides.id || `session-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`)
  const now = Date.now()
  const session = createSessionRecord({
    ...overrides,
    id,
    title: overrides.title || DEFAULT_SESSION_TITLE,
    lastModified: now,
    status: 'active',
  })

  const nextMap = new Map(state.sessionsById)
  const previousActive = state.activeSessionId ? nextMap.get(state.activeSessionId) : null
  if (previousActive) {
    nextMap.set(previousActive.id, {
      ...previousActive,
      status: getInactiveStatus(previousActive),
    })
  }
  nextMap.set(id, session)

  commitState({
    ...state,
    activeSessionId: id,
    sessionsById: nextMap,
  })

  return id
}

function addSession(metadata) {
  if (!metadata?.id) return

  const nextMap = new Map(state.sessionsById)
  const existing = nextMap.get(metadata.id)
  const nextSession = createSessionRecord({
    ...existing,
    ...metadata,
  })
  nextMap.set(nextSession.id, nextSession)

  commitState({
    ...state,
    sessionsById: nextMap,
    activeSessionId: state.activeSessionId || nextSession.id,
  })
}

function ensureSession() {
  if (state.activeSessionId && state.sessionsById.has(state.activeSessionId)) {
    return state.activeSessionId
  }
  if (state.sessionsById.size > 0) {
    const [firstSession] = getSortedSessions()
    if (firstSession?.id) {
      switchSession(firstSession.id)
      return firstSession.id
    }
  }
  return createNewSession()
}

function updateSessionDraft(id, draft) {
  if (!id || !state.sessionsById.has(id)) return

  const nextMap = new Map(state.sessionsById)
  const session = nextMap.get(id)
  nextMap.set(id, {
    ...session,
    draft: String(draft || ''),
    lastModified: Date.now(),
  })

  commitState({
    ...state,
    sessionsById: nextMap,
  })
}

function updateSessionMessages(id, messages) {
  if (!id || !state.sessionsById.has(id) || !Array.isArray(messages)) return

  const nextMap = new Map(state.sessionsById)
  const session = nextMap.get(id)
  const nextTitle = deriveSessionTitle(messages, session.title)

  nextMap.set(id, {
    ...session,
    title: nextTitle,
    messages,
    status: state.activeSessionId === id ? 'active' : getInactiveStatus({ ...session, messages }),
    lastModified: Date.now(),
  })

  commitState({
    ...state,
    sessionsById: nextMap,
  })
}

/**
 * Reset the store to initial state.
 * Exported for test isolation — not intended for production use.
 */
export function resetSessionStore() {
  try {
    window.localStorage?.removeItem(STORAGE_KEY)
  } catch {
    // Ignore cleanup failures in tests.
  }
  state = {
    activeSessionId: null,
    sessionsById: new Map(),
  }
  emitChange()
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useSessionState() {
  const snapshot = useSyncExternalStore(subscribe, getSnapshot)

  const sessions = getSortedSessions()
  const activeSession = snapshot.activeSessionId
    ? snapshot.sessionsById.get(snapshot.activeSessionId) || null
    : null

  return {
    activeSessionId: snapshot.activeSessionId,
    activeSession,
    sessions,
    switchSession: useCallback((id) => switchSession(id), []),
    createNewSession: useCallback((metadata) => createNewSession(metadata), []),
    addSession: useCallback((metadata) => addSession(metadata), []),
    ensureSession: useCallback(() => ensureSession(), []),
    updateSessionDraft: useCallback((id, draft) => updateSessionDraft(id, draft), []),
    updateSessionMessages: useCallback((id, messages) => updateSessionMessages(id, messages), []),
  }
}
