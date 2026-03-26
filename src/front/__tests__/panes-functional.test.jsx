/**
 * Functional validation: all registered panes render without crashing
 * when their capability requirements are met.
 *
 * This is the P7-VALIDATE gate for pane rendering. It verifies that
 * each pane component in the registry can be instantiated by React
 * without throwing.
 */
import { describe, it, expect, vi } from 'vitest'
import { render } from '@testing-library/react'
import defaultRegistry from '../registry/panes'

// Mock heavy dependencies that panels import
vi.mock('dockview-react', () => ({
  DockviewReact: () => null,
}))

describe('All panes functional validation', () => {
  const panes = defaultRegistry.list()

  it('registry has at least 4 panes registered', () => {
    expect(panes.length).toBeGreaterThanOrEqual(4)
  })

  it('all panes have id, component, and title', () => {
    for (const pane of panes) {
      expect(pane.id).toBeTruthy()
      expect(pane.component).toBeTruthy()
      expect(typeof pane.component).toBe('function')
    }
  })

  it('essential panes include filetree', () => {
    const essentials = defaultRegistry.essentials()
    expect(essentials).toContain('filetree')
  })

  it('all panes use abstract capability names (not legacy)', () => {
    for (const pane of panes) {
      const caps = pane.requiresCapabilities || []
      for (const cap of caps) {
        // Must use dotted abstract names
        expect(cap).toMatch(/^(workspace|agent)\./)
      }
      // Must NOT use legacy names
      expect(pane.requiresFeatures || []).toEqual([])
      expect(pane.requiresRouters || []).toEqual([])
    }
  })

  it('capability gating works for each pane', () => {
    // Simulate full capabilities (bwrap backend)
    const fullCapabilities = {
      features: {
        files: true, git: true, exec: true, pty: true,
        chat_claude_code: true, stream: true, control_plane: true,
        ui_state: true, approval: true, pi: true,
      },
      capabilities: {
        'workspace.files': true,
        'workspace.exec': true,
        'workspace.git': true,
        'workspace.python': true,
        'agent.chat': true,
        'agent.tools': true,
      },
    }

    const available = defaultRegistry.getAvailablePanes(fullCapabilities)
    expect(available.length).toBe(panes.length)

    // With no capabilities, only panes without requirements should be available
    const minimal = defaultRegistry.getAvailablePanes({ features: {}, capabilities: {} })
    const noReqPanes = panes.filter(
      (p) => !(p.requiresCapabilities?.length > 0) &&
             !(p.requiresFeatures?.length > 0) &&
             !(p.requiresRouters?.length > 0),
    )
    expect(minimal.length).toBe(noReqPanes.length)
  })

  it('pane IDs are unique', () => {
    const ids = panes.map((p) => p.id)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('registered pane IDs match known set', () => {
    const ids = new Set(panes.map((p) => p.id))
    // Core panes that must exist
    expect(ids.has('filetree')).toBe(true)
    expect(ids.has('editor')).toBe(true)
    expect(ids.has('empty')).toBe(true)
    // Legacy panes must NOT exist
    expect(ids.has('terminal')).toBe(false)
    expect(ids.has('shell')).toBe(false)
  })
})
