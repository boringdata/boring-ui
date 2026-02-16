import { useEffect, useMemo, useRef } from 'react'
import { useStore } from './upstream/store'
import { connectSession, disconnectSession } from './upstream/ws'
import CompanionApp from './upstream/App'
import { api } from './upstream/api'
import './overrides.css'

const buildSessionLabel = (session, sessionNames) => {
  if (!session) return 'Session'
  const id = session.session_id || session.sessionId
  const name = sessionNames?.get?.(id)
  const repo = session.repo_root ? session.repo_root.split('/').pop() : ''
  const cwd = session.cwd ? session.cwd.split('/').pop() : ''
  const model = session.model || ''
  const base = name || repo || cwd || model || id.slice(0, 8)
  const branch = session.git_branch || session.gitBranch
  const branchLabel = branch && branch !== 'main'
    ? ` • ${branch}`
    : ''
  return `${base}${branchLabel}`
}

export default function CompanionAdapter() {
  const sessionsMap = useStore((s) => s.sessions)
  const sdkSessions = useStore((s) => s.sdkSessions)
  const sessionNames = useStore((s) => s.sessionNames)
  const currentSessionId = useStore((s) => s.currentSessionId)
  const setCurrentSession = useStore((s) => s.setCurrentSession)
  const setSdkSessions = useStore((s) => s.setSdkSessions)
  const setCliConnected = useStore((s) => s.setCliConnected)
  const newSession = useStore((s) => s.newSession)
  const sidebarOpen = useStore((s) => s.sidebarOpen)
  const taskPanelOpen = useStore((s) => s.taskPanelOpen)
  const setSidebarOpen = useStore((s) => s.setSidebarOpen)
  const setTaskPanelOpen = useStore((s) => s.setTaskPanelOpen)
  const hasLoadedSessions = useRef(false)

  useEffect(() => {
    let active = true
    async function poll() {
      try {
        const list = await api.listSessions()
        if (active) {
          setSdkSessions(list)
          list.forEach((session) => {
            if (session.state === 'connected' || session.state === 'running') {
              setCliConnected(session.sessionId, true)
            }
          })
          hasLoadedSessions.current = true
        }
      } catch {
        // server not ready
      }
    }
    poll()
    const interval = setInterval(poll, 5000)
    return () => {
      active = false
      clearInterval(interval)
    }
  }, [setSdkSessions])

  const sessions = useMemo(() => {
    const all = new Map()
    for (const session of sessionsMap.values()) {
      all.set(session.session_id, session)
    }
    for (const sdk of sdkSessions) {
      if (!all.has(sdk.sessionId)) {
        all.set(sdk.sessionId, {
          session_id: sdk.sessionId,
          cwd: sdk.cwd,
          git_branch: sdk.gitBranch,
          model: sdk.model,
          created_at: sdk.createdAt,
        })
      }
    }
    return Array.from(all.values()).sort((a, b) => (b.created_at || 0) - (a.created_at || 0))
  }, [sessionsMap, sdkSessions])

  const handleSelect = (nextId) => {
    if (!nextId || nextId === currentSessionId) return
    if (currentSessionId) disconnectSession(currentSessionId)
    setCurrentSession(nextId)
    connectSession(nextId)
  }

  const handleNewSession = () => {
    if (currentSessionId) disconnectSession(currentSessionId)
    newSession()
  }

  useEffect(() => {
    // Keep the upstream session list hidden by default in embedded mode.
    setSidebarOpen(false)
    setTaskPanelOpen(false)
  }, [setSidebarOpen, setTaskPanelOpen])

  useEffect(() => {
    if (sidebarOpen) setSidebarOpen(false)
  }, [sidebarOpen, setSidebarOpen])

  useEffect(() => {
    if (taskPanelOpen) setTaskPanelOpen(false)
  }, [taskPanelOpen, setTaskPanelOpen])

  useEffect(() => {
    if (!currentSessionId) return
    if (!hasLoadedSessions.current) return
    const knownIds = new Set(sessions.map((s) => s.session_id))
    if (!knownIds.has(currentSessionId)) {
      setCurrentSession(null)
    }
  }, [currentSessionId, sessions, setCurrentSession])

  useEffect(() => {
    if (currentSessionId) return
    if (!hasLoadedSessions.current) return
    if (sessions.length === 0) return
    const nextId = sessions[0].session_id
    setCurrentSession(nextId)
    connectSession(nextId)
  }, [currentSessionId, sessions, setCurrentSession])

  return (
    <div className="companion-wrapper">
      <div className="companion-toolbar">
        <select
          className="companion-select"
          value={currentSessionId || ''}
          onChange={(e) => handleSelect(e.target.value)}
        >
          {sessions.length === 0 && <option value="">No sessions</option>}
          {sessions.map((session) => (
            <option key={session.session_id} value={session.session_id}>
              {buildSessionLabel(session, sessionNames)}
            </option>
          ))}
        </select>
        <button type="button" className="companion-new-session" onClick={handleNewSession}>
          New session
        </button>
      </div>
      <CompanionApp />
    </div>
  )
}
