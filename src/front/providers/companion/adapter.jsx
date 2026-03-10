import { useEffect, useMemo, useRef } from 'react'
import { useStore } from './upstream/store'
import { connectSession, disconnectSession } from './upstream/ws'
import CompanionApp from './upstream/App'
import { api } from './upstream/api'
import './overrides.css'

export default function CompanionAdapter() {
  const sessionsMap = useStore((s) => s.sessions)
  const sdkSessions = useStore((s) => s.sdkSessions)
  const currentSessionId = useStore((s) => s.currentSessionId)
  const setCurrentSession = useStore((s) => s.setCurrentSession)
  const setSdkSessions = useStore((s) => s.setSdkSessions)
  const setCliConnected = useStore((s) => s.setCliConnected)
  const sidebarOpen = useStore((s) => s.sidebarOpen)
  const taskPanelOpen = useStore((s) => s.taskPanelOpen)
  const setSidebarOpen = useStore((s) => s.setSidebarOpen)
  const setTaskPanelOpen = useStore((s) => s.setTaskPanelOpen)
  const hasLoadedSessions = useRef(false)
  const relaunchAttemptsRef = useRef(new Set())

  useEffect(() => {
    let active = true
    async function poll() {
      try {
        const list = await api.listSessions()
        if (active) {
          setSdkSessions(list)
          const connectedIds = new Set()
          list.forEach((session) => {
            if (session.state === 'connected' || session.state === 'running') {
              connectedIds.add(session.sessionId)
              setCliConnected(session.sessionId, true)
            }
          })
          const knownIds = new Set([
            ...useStore.getState().sessions.keys(),
            ...list.map((session) => session.sessionId),
          ])
          knownIds.forEach((id) => {
            if (!connectedIds.has(id)) {
              setCliConnected(id, false)
            }
          })
          hasLoadedSessions.current = true
        }
      } catch {
        // Session list API unavailable — mark loaded so restoration effects
        // can fire and attempt WebSocket reconnection (the real source of truth).
        if (active) hasLoadedSessions.current = true
      }
    }
    poll()
    const interval = setInterval(poll, 5000)
    return () => {
      active = false
      clearInterval(interval)
    }
  }, [setSdkSessions, setCliConnected])

  const knownSessions = useMemo(() => {
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
    const knownIds = new Set(knownSessions.map((s) => s.session_id))
    if (knownIds.has(currentSessionId)) {
      return
    }
    // If sdkSessions is empty the API may be unavailable — don't clear yet.
    // Effect below will attempt a WebSocket connection (the real source of truth).
    if (sdkSessions.length === 0) return
    // Stale restored session id: stop reconnect loop immediately.
    disconnectSession(currentSessionId)
    setCurrentSession(null)
  }, [currentSessionId, knownSessions, setCurrentSession, sdkSessions])

  useEffect(() => {
    if (!currentSessionId) return
    if (!hasLoadedSessions.current) return

    const currentSdk = sdkSessions.find((session) => session.sessionId === currentSessionId)
    if (!currentSdk || currentSdk.archived) {
      relaunchAttemptsRef.current.delete(currentSessionId)
      // Session not in SDK list (API may be unavailable or session is ephemeral).
      // Try connecting via WebSocket — it's the source of truth for session liveness.
      connectSession(currentSessionId)
      return
    }

    if (currentSdk.state !== 'exited') {
      relaunchAttemptsRef.current.delete(currentSessionId)
      connectSession(currentSessionId)
      return
    }

    if (relaunchAttemptsRef.current.has(currentSessionId)) return
    relaunchAttemptsRef.current.add(currentSessionId)

    api.relaunchSession(currentSessionId)
      .then(() => {
        connectSession(currentSessionId)
      })
      .catch(() => {
        // Fall back to Home if restore/relaunch fails.
        setCurrentSession(null)
      })
  }, [currentSessionId, sdkSessions, setCurrentSession])

  useEffect(() => {
    if (currentSessionId) return
    if (!hasLoadedSessions.current) return
    const activeSdkSessions = [...sdkSessions]
      .filter((session) => !session.archived && session.state !== 'exited')
      .sort((a, b) => (b.createdAt || 0) - (a.createdAt || 0))
    if (activeSdkSessions.length === 0) return
    const nextId = activeSdkSessions[0].sessionId
    setCurrentSession(nextId)
    connectSession(nextId)
  }, [currentSessionId, sdkSessions, setCurrentSession])

  return (
    <div className="companion-wrapper">
      <CompanionApp />
    </div>
  )
}
