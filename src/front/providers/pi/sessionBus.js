const PI_SESSION_STATE_EVENT = 'boring-ui:pi-session-state'
const PI_SESSION_SWITCH_EVENT = 'boring-ui:pi-session-switch'
const PI_SESSION_NEW_EVENT = 'boring-ui:pi-session-new'
const PI_SESSION_REQUEST_EVENT = 'boring-ui:pi-session-request'

const eventTarget = () => (typeof window !== 'undefined' ? window : null)

export function publishPiSessionState(detail) {
  const target = eventTarget()
  if (!target) return
  target.dispatchEvent(new CustomEvent(PI_SESSION_STATE_EVENT, { detail }))
}

export function subscribePiSessionState(listener) {
  const target = eventTarget()
  if (!target) return () => {}

  const handler = (event) => {
    listener(event.detail || { currentSessionId: '', sessions: [] })
  }

  target.addEventListener(PI_SESSION_STATE_EVENT, handler)
  return () => target.removeEventListener(PI_SESSION_STATE_EVENT, handler)
}

export function requestPiSessionState() {
  const target = eventTarget()
  if (!target) return
  target.dispatchEvent(new Event(PI_SESSION_REQUEST_EVENT))
}

export function requestPiSwitchSession(sessionId) {
  const target = eventTarget()
  if (!target || !sessionId) return
  target.dispatchEvent(new CustomEvent(PI_SESSION_SWITCH_EVENT, { detail: { sessionId } }))
}

export function requestPiNewSession() {
  const target = eventTarget()
  if (!target) return
  target.dispatchEvent(new Event(PI_SESSION_NEW_EVENT))
}

export function subscribePiSessionActions({ onSwitch, onNew, onRequestState }) {
  const target = eventTarget()
  if (!target) return () => {}

  const handleSwitch = (event) => {
    onSwitch?.(event.detail?.sessionId || '')
  }
  const handleNew = () => {
    onNew?.()
  }
  const handleRequest = () => {
    onRequestState?.()
  }

  target.addEventListener(PI_SESSION_SWITCH_EVENT, handleSwitch)
  target.addEventListener(PI_SESSION_NEW_EVENT, handleNew)
  target.addEventListener(PI_SESSION_REQUEST_EVENT, handleRequest)

  return () => {
    target.removeEventListener(PI_SESSION_SWITCH_EVENT, handleSwitch)
    target.removeEventListener(PI_SESSION_NEW_EVENT, handleNew)
    target.removeEventListener(PI_SESSION_REQUEST_EVENT, handleRequest)
  }
}
