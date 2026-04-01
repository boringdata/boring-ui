import React from 'react'
import { Clock3 } from 'lucide-react'

function groupSessionsByRecency(sessionList) {
  const oneDayMs = 86400000
  const todayStart = new Date()
  todayStart.setHours(0, 0, 0, 0)
  const yesterdayStart = new Date(todayStart.getTime() - oneDayMs)

  const groups = { Today: [], Yesterday: [], Earlier: [] }

  for (const session of sessionList) {
    const modified = session.lastModified || 0
    if (modified >= todayStart.getTime()) {
      groups.Today.push(session)
    } else if (modified >= yesterdayStart.getTime()) {
      groups.Yesterday.push(session)
    } else {
      groups.Earlier.push(session)
    }
  }

  return groups
}

function formatRelativeTime(ts) {
  if (!Number.isFinite(ts)) return ''
  const diff = Date.now() - ts
  const minute = 60000
  const hour = minute * 60
  const day = hour * 24
  if (diff < hour) return `${Math.max(1, Math.round(diff / minute))}m`
  if (diff < day) return `${Math.max(1, Math.round(diff / hour))}h`
  return `${Math.max(1, Math.round(diff / day))}d`
}

function SessionList({ sessions, activeSessionId, onSwitchSession }) {
  if (sessions.length === 0) {
    return <div className="browse-drawer-empty">No sessions yet</div>
  }

  const groups = groupSessionsByRecency(sessions)

  return (
    <div className="browse-drawer-sessions" data-testid="browse-drawer-sessions">
      {Object.entries(groups).map(([label, items]) => {
        if (items.length === 0) return null
        return (
          <div key={label} className="browse-drawer-group">
            <div className="browse-drawer-date" data-testid={`browse-drawer-date-${label.toLowerCase()}`}>
              {label}
            </div>
            {items.map((session) => (
              <button
                key={session.id}
                className={`browse-drawer-btn${session.id === activeSessionId ? ' active' : ''}`}
                data-testid={`browse-drawer-session-${session.id}`}
                onClick={() => onSwitchSession(session.id)}
                type="button"
              >
                <span className={`rail-session-dot ${session.status || 'idle'}`} />
                <span className="browse-drawer-btn-copy">
                  <span className="browse-drawer-btn-label">{session.title}</span>
                  <span className="browse-drawer-btn-meta">{formatRelativeTime(session.lastModified)}</span>
                </span>
              </button>
            ))}
          </div>
        )
      })}
    </div>
  )
}

/**
 * BrowseDrawer — left-side sessions drawer for the chat-centered shell.
 */
export default function BrowseDrawer({
  open = false,
  sessions = [],
  activeSessionId = null,
  onSwitchSession,
}) {
  if (!open) {
    return null
  }

  return (
    <aside className="browse-drawer" data-testid="browse-drawer">
      <div className="browse-drawer-head-row">
        <div className="browse-drawer-head-copy">
          <div className="browse-drawer-eyebrow">Sessions</div>
          <div className="browse-drawer-title">Conversation history</div>
        </div>
        <span className="browse-drawer-icon-pill" aria-hidden="true">
          <Clock3 size={14} />
        </span>
      </div>

      <SessionList
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSwitchSession={onSwitchSession}
      />
    </aside>
  )
}
