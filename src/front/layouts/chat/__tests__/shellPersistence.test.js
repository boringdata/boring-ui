import { describe, expect, it, beforeEach } from 'vitest'
import {
  saveShellState,
  loadShellState,
  saveArtifactState,
  loadArtifactState,
  saveSurfaceLayout,
  loadSurfaceLayout,
  clearShellState,
} from '../utils/shellPersistence'

describe('shellPersistence', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  describe('saveShellState + loadShellState', () => {
    it('round-trips shell state correctly', () => {
      const state = {
        surfaceCollapsed: true,
        surfaceWidth: 800,
        surfaceSidebarWidth: 320,
        activeDestination: 'workspace',
      }

      saveShellState(state)
      const loaded = loadShellState()

      expect(loaded).toEqual({
        surfaceCollapsed: true,
        surfaceWidth: 800,
        surfaceSidebarWidth: 320,
        activeDestination: 'workspace',
      })
    })

    it('preserves falsy values correctly', () => {
      const state = {
        surfaceCollapsed: false,
        surfaceWidth: 0,
        surfaceSidebarWidth: 240,
        activeDestination: null,
      }

      saveShellState(state)
      const loaded = loadShellState()

      expect(loaded.surfaceCollapsed).toBe(false)
      expect(loaded.surfaceWidth).toBe(0)
      expect(loaded.surfaceSidebarWidth).toBe(240)
      expect(loaded.activeDestination).toBeNull()
    })

    it('overwrites previous state on re-save', () => {
      saveShellState({
        surfaceCollapsed: false,
        surfaceWidth: 400,
        surfaceSidebarWidth: 280,
        activeDestination: null,
      })
      saveShellState({
        surfaceCollapsed: true,
        surfaceWidth: 900,
        surfaceSidebarWidth: 360,
        activeDestination: 'sessions',
      })

      const loaded = loadShellState()
      expect(loaded.surfaceCollapsed).toBe(true)
      expect(loaded.surfaceWidth).toBe(900)
      expect(loaded.surfaceSidebarWidth).toBe(360)
      expect(loaded.activeDestination).toBe('sessions')
    })
  })

  describe('saveArtifactState + loadArtifactState', () => {
    it('round-trips artifact metadata correctly', () => {
      const artifacts = new Map([
        ['art-1', {
          id: 'art-1',
          canonicalKey: 'src/auth.js',
          kind: 'code',
          title: 'auth.js',
          source: 'tool',
          rendererKey: 'code-editor',
          params: { lang: 'javascript' },
        }],
        ['art-2', {
          id: 'art-2',
          canonicalKey: 'src/app.css',
          kind: 'style',
          title: 'app.css',
          source: 'user',
          rendererKey: null,
          params: {},
        }],
      ])
      const orderedIds = ['art-1', 'art-2']
      const activeId = 'art-2'

      saveArtifactState(artifacts, orderedIds, activeId)
      const loaded = loadArtifactState()

      expect(loaded.activeId).toBe('art-2')
      expect(loaded.artifacts).toHaveLength(2)
      expect(loaded.artifacts[0]).toEqual({
        id: 'art-1',
        canonicalKey: 'src/auth.js',
        kind: 'code',
        title: 'auth.js',
        source: 'tool',
        rendererKey: 'code-editor',
        params: { lang: 'javascript' },
      })
      expect(loaded.artifacts[1]).toEqual({
        id: 'art-2',
        canonicalKey: 'src/app.css',
        kind: 'style',
        title: 'app.css',
        source: 'user',
        rendererKey: null,
        params: {},
      })
    })

    it('filters out ids not found in artifacts Map', () => {
      const artifacts = new Map([
        ['art-1', {
          id: 'art-1',
          canonicalKey: 'src/a.js',
          kind: 'code',
          title: 'a.js',
          source: 'tool',
          rendererKey: null,
          params: {},
        }],
      ])
      // orderedIds contains an id not in the Map
      const orderedIds = ['art-1', 'art-missing']

      saveArtifactState(artifacts, orderedIds, 'art-1')
      const loaded = loadArtifactState()

      expect(loaded.artifacts).toHaveLength(1)
      expect(loaded.artifacts[0].id).toBe('art-1')
    })

    it('handles empty artifacts', () => {
      saveArtifactState(new Map(), [], null)
      const loaded = loadArtifactState()

      expect(loaded.artifacts).toEqual([])
      expect(loaded.activeId).toBeNull()
    })
  })

  describe('saveSurfaceLayout + loadSurfaceLayout', () => {
    it('round-trips Dockview layout JSON', () => {
      const layout = {
        grid: {
          root: {
            type: 'branch',
            data: [{ type: 'leaf', data: ['art-1'] }],
          },
        },
      }

      saveSurfaceLayout(layout)
      expect(loadSurfaceLayout()).toEqual(layout)
    })

    it('returns null for invalid stored layout JSON', () => {
      localStorage.setItem('boring-ui:chat-shell-surface-layout:v1', '{broken')
      expect(loadSurfaceLayout()).toBeNull()
    })
  })

  describe('loadShellState', () => {
    it('returns null when nothing saved', () => {
      expect(loadShellState()).toBeNull()
    })

    it('returns null when stored value is invalid JSON', () => {
      localStorage.setItem('boring-ui:chat-shell:v1', '{not valid json')
      expect(loadShellState()).toBeNull()
    })
  })

  describe('loadArtifactState', () => {
    it('returns null when nothing saved', () => {
      expect(loadArtifactState()).toBeNull()
    })

    it('returns null when stored value is invalid JSON', () => {
      localStorage.setItem('boring-ui:chat-shell-artifacts:v1', 'broken')
      expect(loadArtifactState()).toBeNull()
    })
  })

  describe('clearShellState', () => {
    it('removes both shell and artifact stored data', () => {
      saveShellState({
        surfaceCollapsed: false,
        surfaceWidth: 500,
        surfaceSidebarWidth: 296,
        activeDestination: null,
      })
      saveArtifactState(new Map(), [], null)

      // Verify data exists
      expect(loadShellState()).not.toBeNull()
      expect(loadArtifactState()).not.toBeNull()
      saveSurfaceLayout({ grid: { root: { type: 'leaf' } } })
      expect(loadSurfaceLayout()).not.toBeNull()

      clearShellState()

      // Verify data removed
      expect(loadShellState()).toBeNull()
      expect(loadArtifactState()).toBeNull()
      expect(loadSurfaceLayout()).toBeNull()
    })

    it('does not throw when nothing is stored', () => {
      expect(() => clearShellState()).not.toThrow()
    })
  })
})
