/**
 * WorkspaceSwitcher component unit tests.
 *
 * Bead: bd-223o.14.2 (H2)
 *
 * Validates:
 *   - Renders trigger with current workspace name.
 *   - Opens dropdown on click; lists other workspaces.
 *   - Calls onSwitchWorkspace with workspace_id on selection.
 *   - Calls onCreateWorkspace when "New workspace" clicked.
 *   - Does not render when workspaces list is empty.
 *   - Closes dropdown on outside click (Escape).
 *   - Shows "Current" badge for selected workspace.
 *   - Does not call onSwitchWorkspace when re-selecting current workspace.
 *   - Supports workspace_id field aliases.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import WorkspaceSwitcher from './WorkspaceSwitcher.jsx'

const WORKSPACES = [
  { id: 'ws_1', name: 'Alpha' },
  { id: 'ws_2', name: 'Beta' },
  { id: 'ws_3', name: 'Gamma' },
]

afterEach(cleanup)

describe('WorkspaceSwitcher', () => {
  it('renders trigger with current workspace name', () => {
    render(
      <WorkspaceSwitcher
        workspaces={WORKSPACES}
        selectedWorkspaceId="ws_1"
      />,
    )
    expect(screen.getByTestId('workspace-switcher-trigger')).toBeTruthy()
    expect(screen.getByText('Alpha')).toBeTruthy()
  })

  it('does not render when workspaces is empty', () => {
    const { container } = render(
      <WorkspaceSwitcher workspaces={[]} selectedWorkspaceId={null} />,
    )
    expect(container.innerHTML).toBe('')
  })

  it('opens dropdown on click', () => {
    render(
      <WorkspaceSwitcher
        workspaces={WORKSPACES}
        selectedWorkspaceId="ws_1"
      />,
    )
    expect(screen.queryByTestId('workspace-switcher-dropdown')).toBeNull()
    fireEvent.click(screen.getByTestId('workspace-switcher-trigger'))
    expect(screen.getByTestId('workspace-switcher-dropdown')).toBeTruthy()
  })

  it('shows other workspaces in dropdown', () => {
    render(
      <WorkspaceSwitcher
        workspaces={WORKSPACES}
        selectedWorkspaceId="ws_1"
      />,
    )
    fireEvent.click(screen.getByTestId('workspace-switcher-trigger'))
    expect(screen.getByText('Beta')).toBeTruthy()
    expect(screen.getByText('Gamma')).toBeTruthy()
  })

  it('shows "Current" badge for selected workspace', () => {
    render(
      <WorkspaceSwitcher
        workspaces={WORKSPACES}
        selectedWorkspaceId="ws_1"
      />,
    )
    fireEvent.click(screen.getByTestId('workspace-switcher-trigger'))
    expect(screen.getByText('Current')).toBeTruthy()
  })

  it('calls onSwitchWorkspace with workspace_id on selection', () => {
    const onSwitch = vi.fn()
    render(
      <WorkspaceSwitcher
        workspaces={WORKSPACES}
        selectedWorkspaceId="ws_1"
        onSwitchWorkspace={onSwitch}
      />,
    )
    fireEvent.click(screen.getByTestId('workspace-switcher-trigger'))
    fireEvent.click(screen.getByTestId('workspace-option-ws_2'))
    expect(onSwitch).toHaveBeenCalledWith('ws_2')
  })

  it('does not call onSwitchWorkspace when dropdown closes', () => {
    const onSwitch = vi.fn()
    render(
      <WorkspaceSwitcher
        workspaces={WORKSPACES}
        selectedWorkspaceId="ws_1"
        onSwitchWorkspace={onSwitch}
      />,
    )
    fireEvent.click(screen.getByTestId('workspace-switcher-trigger'))
    // Click trigger again to close.
    fireEvent.click(screen.getByTestId('workspace-switcher-trigger'))
    expect(onSwitch).not.toHaveBeenCalled()
  })

  it('calls onCreateWorkspace when "New workspace" clicked', () => {
    const onCreate = vi.fn()
    render(
      <WorkspaceSwitcher
        workspaces={WORKSPACES}
        selectedWorkspaceId="ws_1"
        onCreateWorkspace={onCreate}
      />,
    )
    fireEvent.click(screen.getByTestId('workspace-switcher-trigger'))
    fireEvent.click(screen.getByTestId('workspace-create-btn'))
    expect(onCreate).toHaveBeenCalledOnce()
  })

  it('closes dropdown after selection', () => {
    const onSwitch = vi.fn()
    render(
      <WorkspaceSwitcher
        workspaces={WORKSPACES}
        selectedWorkspaceId="ws_1"
        onSwitchWorkspace={onSwitch}
      />,
    )
    fireEvent.click(screen.getByTestId('workspace-switcher-trigger'))
    fireEvent.click(screen.getByTestId('workspace-option-ws_2'))
    expect(screen.queryByTestId('workspace-switcher-dropdown')).toBeNull()
  })

  it('closes dropdown on Escape key', () => {
    render(
      <WorkspaceSwitcher
        workspaces={WORKSPACES}
        selectedWorkspaceId="ws_1"
      />,
    )
    fireEvent.click(screen.getByTestId('workspace-switcher-trigger'))
    expect(screen.getByTestId('workspace-switcher-dropdown')).toBeTruthy()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByTestId('workspace-switcher-dropdown')).toBeNull()
  })

  it('shows "Select workspace" when no workspace selected', () => {
    render(
      <WorkspaceSwitcher
        workspaces={WORKSPACES}
        selectedWorkspaceId={null}
      />,
    )
    expect(screen.getByText('Select workspace')).toBeTruthy()
  })

  it('supports workspace_id field alias', () => {
    const ws = [{ workspace_id: 'ws_x', name: 'X-Project' }]
    render(
      <WorkspaceSwitcher
        workspaces={ws}
        selectedWorkspaceId="ws_x"
      />,
    )
    expect(screen.getByText('X-Project')).toBeTruthy()
  })

  it('supports workspaceId field alias', () => {
    const ws = [{ workspaceId: 'ws_y', name: 'Y-Project' }]
    render(
      <WorkspaceSwitcher
        workspaces={ws}
        selectedWorkspaceId="ws_y"
      />,
    )
    expect(screen.getByText('Y-Project')).toBeTruthy()
  })

  it('shows only single workspace as current with no other options', () => {
    render(
      <WorkspaceSwitcher
        workspaces={[{ id: 'ws_solo', name: 'Solo' }]}
        selectedWorkspaceId="ws_solo"
      />,
    )
    fireEvent.click(screen.getByTestId('workspace-switcher-trigger'))
    // Should have current badge but no selectable options.
    expect(screen.getByText('Current')).toBeTruthy()
    expect(screen.queryByTestId('workspace-option-ws_solo')).toBeNull()
  })
})
