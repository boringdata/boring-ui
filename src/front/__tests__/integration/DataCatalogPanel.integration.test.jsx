/**
 * @vitest-environment jsdom
 */
import React, { useMemo, useState } from 'react'
import '../setup.ts'
import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'

import {
  CapabilitiesContext,
  CapabilitiesStatusContext,
  createCapabilityGatedPane,
} from '../../shared/components/CapabilityGate'
import { getGatedComponents } from '../../registry/panes'

const gatedComponents = getGatedComponents(createCapabilityGatedPane)
const DataCatalogPane = gatedComponents['data-catalog']

const noop = () => {}

function DataCatalogHarness({
  capabilities = { features: {}, services: {} },
  initialCollapsed = false,
  initialSectionCollapsed = false,
  onActivateSidebarPanel = noop,
}) {
  const [collapsed, setCollapsed] = useState(initialCollapsed)
  const [sectionCollapsed, setSectionCollapsed] = useState(initialSectionCollapsed)
  const [activeSidebarPanelId, setActiveSidebarPanelId] = useState('data-catalog')

  const params = useMemo(() => ({
    collapsed,
    onToggleCollapse: () => setCollapsed((value) => !value),
    showSidebarToggle: true,
    appName: 'Boring UI',
    onOpenChatTab: noop,
    sectionCollapsed,
    onToggleSection: () => setSectionCollapsed((value) => !value),
    onActivateSidebarPanel: (panelId, intent) => {
      setActiveSidebarPanelId(panelId)
      onActivateSidebarPanel(panelId, intent)
    },
    activeSidebarPanelId,
  }), [activeSidebarPanelId, collapsed, onActivateSidebarPanel, sectionCollapsed])

  return (
    <CapabilitiesStatusContext.Provider value={{ pending: false }}>
      <CapabilitiesContext.Provider value={capabilities}>
        <DataCatalogPane params={params} />
      </CapabilitiesContext.Provider>
    </CapabilitiesStatusContext.Provider>
  )
}

describe('DataCatalogPanel integration', () => {
  it('renders normally within the capability-aware layout even without backend features', () => {
    render(<DataCatalogHarness capabilities={{ features: {}, services: {} }} />)

    expect(screen.getByText('Data Catalog')).toBeInTheDocument()
    expect(screen.getByRole('tree', { name: 'Data Catalog' })).toBeInTheDocument()
    expect(screen.getByRole('treeitem')).toHaveTextContent('No data sources connected')
    expect(screen.queryByText('Data Catalog Unavailable')).not.toBeInTheDocument()
  })

  it('routes collapsed activity-bar actions to the expected sidebar targets', () => {
    const onActivateSidebarPanel = vi.fn()
    render(
      <DataCatalogHarness
        initialCollapsed
        onActivateSidebarPanel={onActivateSidebarPanel}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Files' }))
    fireEvent.click(screen.getByRole('button', { name: 'Git Changes' }))
    fireEvent.click(screen.getByRole('button', { name: 'Quick Search' }))
    fireEvent.click(screen.getByRole('button', { name: 'Data Catalog' }))

    expect(onActivateSidebarPanel).toHaveBeenNthCalledWith(1, 'filetree', { mode: 'files' })
    expect(onActivateSidebarPanel).toHaveBeenNthCalledWith(2, 'filetree', { mode: 'changes' })
    expect(onActivateSidebarPanel).toHaveBeenNthCalledWith(3, 'filetree', { mode: 'search' })
    expect(onActivateSidebarPanel).toHaveBeenNthCalledWith(4, 'data-catalog', undefined)
  })

  it('supports collapsing and re-expanding the sidebar', () => {
    render(<DataCatalogHarness />)

    expect(screen.getByRole('tree', { name: 'Data Catalog' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Collapse sidebar' }))

    expect(screen.getByRole('toolbar', { name: 'Sidebar activity' })).toBeInTheDocument()
    expect(screen.queryByRole('tree', { name: 'Data Catalog' })).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Expand sidebar' }))

    expect(screen.getByRole('tree', { name: 'Data Catalog' })).toBeInTheDocument()
    expect(screen.queryByRole('toolbar', { name: 'Sidebar activity' })).not.toBeInTheDocument()
  })

  it('supports collapsing and re-expanding the section body', () => {
    render(<DataCatalogHarness />)

    expect(screen.getByRole('tree', { name: 'Data Catalog' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Collapse Data Catalog' }))

    expect(screen.queryByRole('tree', { name: 'Data Catalog' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Expand Data Catalog' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Expand Data Catalog' }))

    expect(screen.getByRole('tree', { name: 'Data Catalog' })).toBeInTheDocument()
  })
})
