import { useEffect, useMemo, useRef } from 'react'
import { useStore } from '../companion/upstream/store'
import { connectSession } from '../companion/upstream/ws'
import CompanionApp from '../companion/upstream/App'
import { api } from '../companion/upstream/api'
import '../companion/overrides.css'

/**
 * PI native adapter.
 *
 * Dedicated adapter entrypoint for PI provider. It intentionally mirrors the
 * companion adapter behavior while allowing PI-specific evolution without
 * coupling to the companion adapter file.
 */
export default function PiNativeAdapter() {
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
  const missingCountsRef = useRef(new Map())

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
        // server not ready
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
      missingCountsRef.current.delete(currentSessionId)
      return
    }
    const nextCount = (missingCountsRef.current.get(currentSessionId) || 0) + 1
    missingCountsRef.current.set(currentSessionId, nextCount)
    if (nextCount >= 2) {
      missingCountsRef.current.delete(currentSessionId)
      setCurrentSession(null)
    }
  }, [currentSessionId, knownSessions, setCurrentSession])

  useEffect(() => {
    missingCountsRef.current.clear()
  }, [currentSessionId])

  useEffect(() => {
    if (currentSessionId) return
    if (!hasLoadedSessions.current) return
    if (knownSessions.length === 0) return
    const nextId = knownSessions[0].session_id
    setCurrentSession(nextId)
    connectSession(nextId)
  }, [currentSessionId, knownSessions, setCurrentSession])

  return (
    <div className="companion-wrapper pi-native-wrapper">
      <CompanionApp />
    </div>
  )
}
