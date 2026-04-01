import { describe, expect, it } from 'vitest'
import { createShellStateSnapshot } from '../utils/shellStateReporter'

describe('createShellStateSnapshot', () => {
  it('creates correct snapshot shape from full shell state', () => {
    const snapshot = createShellStateSnapshot({
      activeDestination: 'workspace',
      drawerOpen: true,
      drawerMode: 'workspace',
      surfaceCollapsed: false,
      activeArtifactId: 'art-1',
      orderedArtifactIds: ['art-1', 'art-2'],
      activeSessionId: 'session-abc',
    })

    expect(snapshot).toEqual({
      'shell.mode': 'chat-centered',
      'shell.rail_destination': 'workspace',
      'browse.open': true,
      'browse.mode': 'workspace',
      'surface.open': true,
      'surface.collapsed': false,
      'surface.active_artifact_id': 'art-1',
      'surface.open_artifacts': ['art-1', 'art-2'],
      'chat.active_session_id': 'session-abc',
    })
  })

  it('includes all required fields', () => {
    const snapshot = createShellStateSnapshot({
      activeDestination: null,
      drawerOpen: false,
      drawerMode: 'sessions',
      surfaceCollapsed: true,
      activeArtifactId: null,
      orderedArtifactIds: [],
      activeSessionId: null,
    })

    const requiredFields = [
      'shell.mode',
      'shell.rail_destination',
      'browse.open',
      'browse.mode',
      'surface.open',
      'surface.collapsed',
      'surface.active_artifact_id',
      'surface.open_artifacts',
      'chat.active_session_id',
    ]

    for (const field of requiredFields) {
      expect(snapshot).toHaveProperty(field)
    }
  })

  it('handles null/undefined values gracefully', () => {
    const snapshot = createShellStateSnapshot({
      activeDestination: null,
      drawerOpen: undefined,
      drawerMode: undefined,
      surfaceCollapsed: undefined,
      activeArtifactId: null,
      orderedArtifactIds: undefined,
      activeSessionId: null,
    })

    // null activeDestination -> 'none'
    expect(snapshot['shell.rail_destination']).toBe('none')
    // undefined drawerOpen -> undefined (falsy)
    expect(snapshot['browse.open']).toBeUndefined()
    // undefined drawerMode -> falls back to 'sessions'
    expect(snapshot['browse.mode']).toBe('sessions')
    // undefined surfaceCollapsed -> surface.open is true (!undefined === true)
    expect(snapshot['surface.open']).toBe(true)
    expect(snapshot['surface.collapsed']).toBeUndefined()
    // null artifact/session pass through
    expect(snapshot['surface.active_artifact_id']).toBeNull()
    expect(snapshot['chat.active_session_id']).toBeNull()
  })

  it('always reports shell.mode as chat-centered', () => {
    const snapshot = createShellStateSnapshot({
      activeDestination: null,
      drawerOpen: false,
      drawerMode: 'sessions',
      surfaceCollapsed: false,
      activeArtifactId: null,
      orderedArtifactIds: [],
      activeSessionId: null,
    })

    expect(snapshot['shell.mode']).toBe('chat-centered')
  })

  it('maps surfaceCollapsed to surface.open (inverse)', () => {
    const collapsed = createShellStateSnapshot({
      activeDestination: null,
      drawerOpen: false,
      drawerMode: 'sessions',
      surfaceCollapsed: true,
      activeArtifactId: null,
      orderedArtifactIds: [],
      activeSessionId: null,
    })

    expect(collapsed['surface.open']).toBe(false)
    expect(collapsed['surface.collapsed']).toBe(true)

    const expanded = createShellStateSnapshot({
      activeDestination: null,
      drawerOpen: false,
      drawerMode: 'sessions',
      surfaceCollapsed: false,
      activeArtifactId: null,
      orderedArtifactIds: [],
      activeSessionId: null,
    })

    expect(expanded['surface.open']).toBe(true)
    expect(expanded['surface.collapsed']).toBe(false)
  })
})
