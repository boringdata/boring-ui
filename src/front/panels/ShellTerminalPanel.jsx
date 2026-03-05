import { useCallback, useEffect, useRef, useState } from 'react'
import { ChevronDown, ChevronUp, X } from 'lucide-react'
import Terminal from '../components/Terminal'
import Tooltip from '../components/Tooltip'

const SESSION_STORAGE_KEY = 'kurt-web-shell-sessions'
const ACTIVE_SESSION_KEY = 'kurt-web-shell-active'
const DEFAULT_PANEL_STORAGE_SCOPE = 'shell'

const scopedStorageKey = (baseKey, panelId) => {
  const scope = String(panelId || DEFAULT_PANEL_STORAGE_SCOPE)
  return `${baseKey}-${scope}`
}

const isUuid = (value) =>
  typeof value === 'string'
  && /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)

const fallbackUuidV4 = () => {
  const template = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'
  return template.replace(/[xy]/g, (char) => {
    const random = Math.floor(Math.random() * 16)
    const value = char === 'x' ? random : ((random & 0x3) | 0x8)
    return value.toString(16)
  })
}

const createSessionId = () => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
    const bytes = new Uint8Array(16)
    crypto.getRandomValues(bytes)
    bytes[6] = (bytes[6] & 0x0f) | 0x40
    bytes[8] = (bytes[8] & 0x3f) | 0x80
    const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
  }
  return fallbackUuidV4()
}

const loadSessions = (panelId) => {
  try {
    const raw = localStorage.getItem(scopedStorageKey(SESSION_STORAGE_KEY, panelId))
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed) || parsed.length === 0) return null
    return parsed
  } catch {
    return null
  }
}

const loadActiveSession = (panelId) => {
  try {
    const raw = localStorage.getItem(scopedStorageKey(ACTIVE_SESSION_KEY, panelId))
    if (!raw) return null
    const id = Number(raw)
    return Number.isNaN(id) ? null : id
  } catch {
    return null
  }
}

const normalizeSession = (session, fallbackId) => {
  // eslint-disable-next-line no-unused-vars
  const { bannerMessage, ...rest } = session
  const id = Number(rest.id) || fallbackId
  return {
    ...rest,
    id,
    title: rest.title || `Terminal ${id}`,
    provider: 'shell',
    sessionId: isUuid(rest.sessionId) ? rest.sessionId : createSessionId(),
  }
}

const serializeSessions = (sessions) =>
  // eslint-disable-next-line no-unused-vars
  sessions.map(({ bannerMessage, resume, ...session }) => session)

export default function ShellTerminalPanel({ params }) {
  const panelId = params?.panelId
  const collapsed = params?.collapsed === true
  const onToggleCollapse = typeof params?.onToggleCollapse === 'function'
    ? params.onToggleCollapse
    : null
  const terminalCounter = useRef(1)
  const sessionStorageKey = scopedStorageKey(SESSION_STORAGE_KEY, panelId)
  const activeSessionKey = scopedStorageKey(ACTIVE_SESSION_KEY, panelId)
  const [sessions, setSessions] = useState(() => {
    const saved = loadSessions(panelId)
    if (saved) {
      return saved.map((session, index) => ({
        ...normalizeSession(session, index + 1),
        resume: true,
      }))
    }
    return [
      {
        id: 1,
        title: 'Terminal 1',
        provider: 'shell',
        sessionId: createSessionId(),
        resume: false,
      },
    ]
  })
  const [activeId, setActiveId] = useState(() => {
    const saved = loadActiveSession(panelId)
    if (saved) return saved
    if (saved === 0) return 0
    return null
  })

  const formatPrompt = useCallback((prompt) => {
    const cleaned = prompt.replace(/\s+/g, ' ').trim()
    if (!cleaned) return 'Terminal'
    return cleaned.length > 28 ? `${cleaned.slice(0, 28)}…` : cleaned
  }, [])

  const handleFirstPrompt = useCallback(
    (sessionId, prompt) => {
      setSessions((prev) =>
        prev.map((session) => {
          if (session.id !== sessionId) return session
          if (!session.title.startsWith('Terminal')) return session
          return { ...session, title: formatPrompt(prompt) }
        }),
      )
    },
    [formatPrompt],
  )

  const addSession = () => {
    const nextId = terminalCounter.current + 1
    terminalCounter.current = nextId
    const next = {
      id: nextId,
      title: `Terminal ${nextId}`,
      provider: 'shell',
      sessionId: createSessionId(),
      resume: false,
    }
    setSessions((prev) => [...prev, next])
    setActiveId(nextId)
  }

  const closeSession = (id) => {
    setSessions((prev) => {
      if (id == null) return prev
      const next = prev.filter((session) => session.id !== id)
      if (next.length === 0) {
        setActiveId(null)
        return next
      }
      if (id === activeId) {
        setActiveId(next[next.length - 1].id)
      }
      return next
    })
  }

  const handleBannerShown = useCallback((id) => {
    setSessions((prev) =>
      prev.map((session) =>
        session.id === id ? { ...session, bannerMessage: undefined } : session,
      ),
    )
  }, [])

  const handleResumeMissing = useCallback((id) => {
    setSessions((prev) =>
      prev.map((session) =>
        session.id === id
          ? {
              ...session,
              sessionId: createSessionId(),
              resume: false,
            }
          : session,
      ),
    )
  }, [])

  useEffect(() => {
    const maxId = sessions.reduce((max, session) => Math.max(max, session.id), 1)
    terminalCounter.current = maxId
    if (!sessions.length) {
      setActiveId(null)
      return
    }
    if (!sessions.some((session) => session.id === activeId)) {
      setActiveId(sessions[0]?.id || 1)
    }
  }, [sessions, activeId])

  useEffect(() => {
    try {
      if (sessions.length === 0) {
        localStorage.removeItem(sessionStorageKey)
      } else {
        localStorage.setItem(sessionStorageKey, JSON.stringify(serializeSessions(sessions)))
      }
      if (activeId == null) {
        localStorage.removeItem(activeSessionKey)
      } else {
        localStorage.setItem(activeSessionKey, String(activeId))
      }
    } catch {
      // Ignore storage errors
    }
  }, [sessions, activeId, sessionStorageKey, activeSessionKey])

  return (
    <div className="panel-content shell-panel-content">
      <div className="shell-header">
        {onToggleCollapse && (
          <Tooltip label={collapsed ? 'Expand panel' : 'Collapse panel'}>
            <button
              type="button"
              className="sidebar-toggle-btn"
              onClick={onToggleCollapse}
              aria-label={collapsed ? 'Expand panel' : 'Collapse panel'}
            >
              {collapsed ? <ChevronDown size={12} /> : <ChevronUp size={12} />}
            </button>
          </Tooltip>
        )}
        <div className="shell-session-bar">
          <select
            id="shell-session-select"
            className="terminal-select"
            value={activeId ?? ''}
            onChange={(event) => setActiveId(Number(event.target.value))}
          >
            {sessions.map((session) => (
              <option key={session.id} value={session.id}>
                {session.title}
              </option>
            ))}
          </select>
          <Tooltip label="New terminal">
            <button
              type="button"
              className="terminal-new terminal-new-icon"
              onClick={addSession}
              aria-label="New terminal"
            >
              <span aria-hidden="true">+</span>
            </button>
          </Tooltip>
          <Tooltip label="Close terminal session">
            <button
              type="button"
              className="terminal-icon-btn terminal-close-btn"
              onClick={() => closeSession(activeId)}
              aria-label="Close terminal session"
            >
              <X size={16} />
            </button>
          </Tooltip>
        </div>
      </div>
      {collapsed ? null : sessions.length === 0 ? (
        <div className="terminal-empty">
          <p>No active terminals.</p>
          <button type="button" className="terminal-new" onClick={addSession}>
            Start new terminal
          </button>
        </div>
      ) : (
        <div className="terminal-body">
          {sessions.map((session) => (
            <div
              key={session.id}
              className={`terminal-instance ${session.id === activeId ? 'active' : ''}`}
            >
              <Terminal
                key={`${session.id}-${session.sessionId}-${session.resume}`}
                isActive={session.id === activeId}
                provider="shell"
                sessionId={session.sessionId}
                sessionName={session.title}
                resume={Boolean(session.resume)}
                onFirstPrompt={(prompt) => handleFirstPrompt(session.id, prompt)}
                onResumeMissing={() => handleResumeMissing(session.id)}
                bannerMessage={session.bannerMessage}
                onBannerShown={() => handleBannerShown(session.id)}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
