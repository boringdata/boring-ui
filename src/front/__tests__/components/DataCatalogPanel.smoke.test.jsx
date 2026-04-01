import React from 'react'
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

import { getPane } from '../../registry/panes'
import DataCatalogPanel from '../../shared/panels/DataCatalogPanel'

vi.mock('../../shared/components/SidebarSectionHeader', () => ({
  __esModule: true,
  default: ({ title }) => <div data-testid="sidebar-section-header">{title}</div>,
  LeftPaneHeader: () => <div data-testid="left-pane-header">left-pane-header</div>,
  CollapsedSidebarActivityBar: ({ items = [] }) => (
    <div
      data-testid="collapsed-activity-items"
      data-count={String(items.length)}
    >
      {items.map((item) => item.id).join(',')}
    </div>
  ),
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

describe('DataCatalogPanel smoke', () => {
  it('keeps the data-catalog pane registry contract stable', () => {
    const config = getPane('data-catalog')

    expect(config).toBeDefined()
    expect(config).toMatchObject({
      id: 'data-catalog',
      essential: false,
      placement: 'left',
      locked: true,
      hideHeader: true,
      constraints: {
        minWidth: 180,
      },
    })
    expect(config.requiresFeatures ?? []).toEqual([])
    expect(config.requiresRouters ?? []).toEqual([])
  })

  it('renders the placeholder body with the expected ARIA contract', () => {
    render(<DataCatalogPanel params={makeParams()} />)

    expect(screen.getByTestId('left-pane-header')).toBeInTheDocument()
    expect(screen.getByTestId('sidebar-section-header')).toHaveTextContent('Data Catalog')
    expect(screen.getByRole('tree', { name: 'Data Catalog' })).toBeInTheDocument()
    expect(screen.getByRole('treeitem')).toHaveTextContent('No data sources connected')
  })

  it('keeps the collapsed activity inventory stable', () => {
    render(<DataCatalogPanel params={makeParams({ collapsed: true })} />)

    expect(screen.getByTestId('collapsed-activity-items')).toHaveAttribute('data-count', '4')
    expect(screen.getByTestId('collapsed-activity-items')).toHaveTextContent(
      'files,data-catalog,git,search',
    )
  })
})
