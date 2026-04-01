import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

// Mock SurfaceDockview to avoid DockviewReact DOM issues in tests
vi.mock('../SurfaceDockview', () => ({
  default: ({ artifacts }) => (
    <div data-testid="mock-dockview">
      {artifacts?.map(a => <div key={a.id}>{a.title}</div>)}
    </div>
  ),
}))

vi.mock('../../../shared/components/FileTree', () => ({
  default: ({ searchExpanded }) => (
    <div data-testid="mock-file-tree">{searchExpanded ? 'search-open' : 'search-closed'}</div>
  ),
}))

vi.mock('../../../shared/providers/data', () => ({
  useFileSearch: vi.fn(() => ({
    data: [],
    isFetching: false,
  })),
}))

import SurfaceShell from '../SurfaceShell'

const mockArtifacts = [
  { id: 'art-1', title: 'Revenue Chart', kind: 'chart', canonicalKey: 'chart:revenue' },
  { id: 'art-2', title: 'Data Table', kind: 'table', canonicalKey: 'table:data' },
]

describe('SurfaceShell', () => {
  it('when open=false, has display:none style', () => {
    render(
      <SurfaceShell
        open={false}
        collapsed={false}
        artifacts={[]}
        onClose={vi.fn()}
        onCollapse={vi.fn()}
        onResize={vi.fn()}
        onSelectArtifact={vi.fn()}
        onCloseArtifact={vi.fn()}
      />
    )
    const surface = screen.getByTestId('surface-shell')
    expect(surface).toHaveStyle({ display: 'none' })
  })

  it('when open=true, is visible', () => {
    render(
      <SurfaceShell
        open={true}
        collapsed={false}
        artifacts={[]}
        onClose={vi.fn()}
        onCollapse={vi.fn()}
        onResize={vi.fn()}
        onSelectArtifact={vi.fn()}
        onCloseArtifact={vi.fn()}
      />
    )
    const surface = screen.getByTestId('surface-shell')
    expect(surface).toHaveStyle({ display: 'flex' })
  })

  it('when collapsed=true, shows handle with artifact count', () => {
    render(
      <SurfaceShell
        open={true}
        collapsed={true}
        artifacts={mockArtifacts}
        onClose={vi.fn()}
        onCollapse={vi.fn()}
        onResize={vi.fn()}
        onSelectArtifact={vi.fn()}
        onCloseArtifact={vi.fn()}
      />
    )
    const handle = screen.getByTestId('surface-shell-handle')
    expect(handle).toBeInTheDocument()
    const count = screen.getByTestId('surface-handle-count')
    expect(count).toHaveTextContent('2')
  })

  it('clicking the collapsed handle reopens the surface', () => {
    const onCollapse = vi.fn()

    render(
      <SurfaceShell
        open={true}
        collapsed={true}
        artifacts={mockArtifacts}
        onClose={vi.fn()}
        onCollapse={onCollapse}
        onResize={vi.fn()}
        onSelectArtifact={vi.fn()}
        onCloseArtifact={vi.fn()}
      />
    )

    fireEvent.click(screen.getByRole('button', { name: /open surface/i }))
    expect(onCollapse).toHaveBeenCalledTimes(1)
  })

  it('close button calls onClose', () => {
    const onClose = vi.fn()
    render(
      <SurfaceShell
        open={true}
        collapsed={false}
        artifacts={mockArtifacts}
        activeArtifactId="art-1"
        onClose={onClose}
        onCollapse={vi.fn()}
        onResize={vi.fn()}
        onSelectArtifact={vi.fn()}
        onCloseArtifact={vi.fn()}
      />
    )
    const closeBtn = screen.getByTestId('surface-close')
    fireEvent.click(closeBtn)
    expect(onClose).toHaveBeenCalled()
  })

  it('renders tab for each artifact in the list', () => {
    render(
      <SurfaceShell
        open={true}
        collapsed={false}
        artifacts={mockArtifacts}
        activeArtifactId="art-1"
        onClose={vi.fn()}
        onCollapse={vi.fn()}
        onResize={vi.fn()}
        onSelectArtifact={vi.fn()}
        onCloseArtifact={vi.fn()}
      />
    )
    expect(screen.getByTestId('mock-dockview')).toHaveTextContent('Revenue Chart')
    expect(screen.getByTestId('mock-dockview')).toHaveTextContent('Data Table')
  })

  it('renders the reusable file tree in the sidebar', () => {
    render(
      <SurfaceShell
        open={true}
        collapsed={false}
        artifacts={mockArtifacts}
        activeArtifactId="art-1"
        onClose={vi.fn()}
        onCollapse={vi.fn()}
        onResize={vi.fn()}
        onSelectArtifact={vi.fn()}
        onCloseArtifact={vi.fn()}
      />
    )
    expect(screen.getByTestId('mock-file-tree')).toBeInTheDocument()
  })

  it('can collapse the internal sidebar to the activity bar', () => {
    render(
      <SurfaceShell
        open={true}
        collapsed={false}
        artifacts={mockArtifacts}
        activeArtifactId="art-1"
        onClose={vi.fn()}
        onCollapse={vi.fn()}
        onResize={vi.fn()}
        onSelectArtifact={vi.fn()}
        onCloseArtifact={vi.fn()}
      />
    )

    fireEvent.click(screen.getByRole('button', { name: /collapse sidebar/i }))
    expect(screen.getByRole('button', { name: /expand sidebar/i })).toBeInTheDocument()
  })

  it('can switch the sidebar to the data catalog view', () => {
    render(
      <SurfaceShell
        open={true}
        collapsed={false}
        artifacts={mockArtifacts}
        activeArtifactId="art-1"
        onClose={vi.fn()}
        onCollapse={vi.fn()}
        onResize={vi.fn()}
        onSelectArtifact={vi.fn()}
        onCloseArtifact={vi.fn()}
      />
    )

    fireEvent.click(screen.getByRole('tab', { name: /data catalog/i }))
    expect(screen.getByTestId('surface-data-catalog')).toBeInTheDocument()
  })

  it('resizes the workbench sidebar independently from the surface width', () => {
    const onSidebarResize = vi.fn()

    render(
      <SurfaceShell
        open={true}
        collapsed={false}
        width={620}
        sidebarWidth={296}
        artifacts={mockArtifacts}
        activeArtifactId="art-1"
        onClose={vi.fn()}
        onCollapse={vi.fn()}
        onResize={vi.fn()}
        onSidebarResize={onSidebarResize}
        onSelectArtifact={vi.fn()}
        onCloseArtifact={vi.fn()}
      />
    )

    const resizeHandle = screen.getByTestId('surface-sidebar-resize')
    fireEvent.mouseDown(resizeHandle, { clientX: 300 })
    fireEvent.mouseMove(document, { clientX: 340 })
    fireEvent.mouseUp(document)

    expect(onSidebarResize).toHaveBeenCalledWith(336)
  })

  it('does not render the user menu inside the workbench sidebar', () => {
    render(
      <SurfaceShell
        open={true}
        collapsed={false}
        artifacts={mockArtifacts}
        activeArtifactId="art-1"
        onClose={vi.fn()}
        onCollapse={vi.fn()}
        onResize={vi.fn()}
        onSelectArtifact={vi.fn()}
        onCloseArtifact={vi.fn()}
      />
    )

    expect(screen.queryByTestId('surface-sidebar-footer')).not.toBeInTheDocument()
  })
})
