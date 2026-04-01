import React from 'react'
import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'

import DataCatalogPanel from '../../shared/panels/DataCatalogPanel'

vi.mock('../../shared/components/Tooltip', () => ({
  default: ({ children }) => <>{children}</>,
}))

const makeParams = (overrides = {}) => ({
  collapsed: false,
  onToggleCollapse: vi.fn(),
  showSidebarToggle: true,
  appName: 'Boring UI',
  onOpenChatTab: vi.fn(),
  sectionCollapsed: false,
  onToggleSection: vi.fn(),
  onActivateSidebarPanel: vi.fn(),
  activeSidebarPanelId: 'data-catalog',
  ...overrides,
})

describe('DataCatalogPanel', () => {
  it('renders the expanded structural shell and placeholder tree', () => {
    const { container } = render(<DataCatalogPanel params={makeParams()} />)

    expect(container.querySelector('.panel-content.datacatalog-panel')).toBeInTheDocument()
    expect(container.querySelector('.left-pane-header')).toBeInTheDocument()
    expect(screen.getByText('Data Catalog')).toBeInTheDocument()
    expect(screen.getByRole('tree', { name: 'Data Catalog' })).toBeInTheDocument()
    expect(screen.getByRole('treeitem')).toHaveTextContent('No data sources connected')
    expect(container.querySelector('.datacatalog-body')).toBeInTheDocument()
  })

  it('hides the left pane header when the sidebar toggle is disabled', () => {
    const { container } = render(
      <DataCatalogPanel params={makeParams({ showSidebarToggle: false })} />,
    )

    expect(container.querySelector('.left-pane-header')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Collapse sidebar' })).not.toBeInTheDocument()
  })

  it('hides the body when the section is collapsed', () => {
    const { container } = render(
      <DataCatalogPanel params={makeParams({ sectionCollapsed: true })} />,
    )

    expect(container.querySelector('.datacatalog-body')).not.toBeInTheDocument()
    expect(screen.queryByRole('tree', { name: 'Data Catalog' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Expand Data Catalog' })).toBeInTheDocument()
  })

  it('renders the collapsed activity bar and forwards the expected callbacks', () => {
    const onToggleCollapse = vi.fn()
    const onActivateSidebarPanel = vi.fn()
    const { container } = render(
      <DataCatalogPanel
        params={makeParams({
          collapsed: true,
          onToggleCollapse,
          onActivateSidebarPanel,
          activeSidebarPanelId: 'data-catalog',
        })}
      />,
    )

    expect(container.querySelector('.panel-content.datacatalog-panel')).toBeInTheDocument()
    expect(screen.getByRole('toolbar', { name: 'Sidebar activity' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Data Catalog' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Files' })).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByRole('button', { name: 'Git Changes' })).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByRole('button', { name: 'Quick Search' })).toHaveAttribute('aria-pressed', 'false')

    fireEvent.click(screen.getByRole('button', { name: 'Expand sidebar' }))
    fireEvent.click(screen.getByRole('button', { name: 'Files' }))
    fireEvent.click(screen.getByRole('button', { name: 'Data Catalog' }))
    fireEvent.click(screen.getByRole('button', { name: 'Git Changes' }))
    fireEvent.click(screen.getByRole('button', { name: 'Quick Search' }))

    expect(onToggleCollapse).toHaveBeenCalledTimes(1)
    expect(onActivateSidebarPanel).toHaveBeenNthCalledWith(1, 'filetree', { mode: 'files' })
    expect(onActivateSidebarPanel).toHaveBeenNthCalledWith(2, 'data-catalog')
    expect(onActivateSidebarPanel).toHaveBeenNthCalledWith(3, 'filetree', { mode: 'changes' })
    expect(onActivateSidebarPanel).toHaveBeenNthCalledWith(4, 'filetree', { mode: 'search' })
  })
})
