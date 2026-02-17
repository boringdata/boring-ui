import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import FileTreePanel from '../../panels/FileTreePanel'

vi.mock('../../components/FileTree', () => ({
  default: () => <div data-testid="file-tree">File tree</div>,
}))

vi.mock('../../components/GitChangesView', () => ({
  default: () => <div data-testid="git-changes-view">Git changes</div>,
}))

const makeParams = (overrides = {}) => ({
  onOpenFile: vi.fn(),
  onOpenFileToSide: vi.fn(),
  onOpenDiff: vi.fn(),
  projectRoot: '.',
  activeFile: null,
  activeDiffFile: null,
  collapsed: true,
  onToggleCollapse: vi.fn(),
  userEmail: 'john@example.com',
  workspaceName: 'my-workspace',
  workspaceId: 'ws-123',
  onSwitchWorkspace: vi.fn(),
  onCreateWorkspace: vi.fn(),
  onOpenUserSettings: vi.fn(),
  onLogout: vi.fn(),
  ...overrides,
})

describe('FileTreePanel + UserMenu integration', () => {
  it('renders real collapsed menu and triggers action callbacks', async () => {
    const params = makeParams()
    const user = userEvent.setup()
    render(<FileTreePanel params={params} />)

    await user.click(screen.getByRole('button', { name: 'User menu' }))
    expect(screen.getByRole('menu')).toBeInTheDocument()
    expect(screen.getByText('workspace: my-workspace')).toBeInTheDocument()

    await user.click(screen.getByRole('menuitem', { name: 'Logout' }))
    expect(params.onLogout).toHaveBeenCalledWith({ workspaceId: 'ws-123' })
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })
})
