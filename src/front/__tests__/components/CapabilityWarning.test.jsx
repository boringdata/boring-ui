import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { CapabilityWarning } from '../../components/CapabilityWarning'

describe('CapabilityWarning', () => {
  it('returns null when no unavailable essentials', () => {
    const { container } = render(<CapabilityWarning unavailableEssentials={[]} />)
    expect(container.innerHTML).toBe('')
  })

  it('returns null when unavailableEssentials is null', () => {
    const { container } = render(<CapabilityWarning unavailableEssentials={null} />)
    expect(container.innerHTML).toBe('')
  })

  it('returns null when unavailableEssentials is undefined', () => {
    const { container } = render(<CapabilityWarning />)
    expect(container.innerHTML).toBe('')
  })

  it('shows warning with pane titles', () => {
    const essentials = [
      { id: 'terminal', title: 'Terminal' },
      { id: 'editor', title: 'Editor' },
    ]
    render(<CapabilityWarning unavailableEssentials={essentials} />)

    expect(screen.getByText(/Warning:/)).toBeTruthy()
    expect(screen.getByText(/Terminal, Editor/)).toBeTruthy()
  })

  it('falls back to id when no title', () => {
    const essentials = [{ id: 'shell' }]
    render(<CapabilityWarning unavailableEssentials={essentials} />)

    expect(screen.getByText(/shell/)).toBeTruthy()
  })

  it('has correct CSS class', () => {
    const essentials = [{ id: 'terminal', title: 'Terminal' }]
    const { container } = render(
      <CapabilityWarning unavailableEssentials={essentials} />,
    )

    expect(container.querySelector('.capability-warning')).toBeTruthy()
  })

  it('shows single unavailable essential', () => {
    const essentials = [{ id: 'filetree', title: 'File Tree' }]
    render(<CapabilityWarning unavailableEssentials={essentials} />)

    expect(screen.getByText(/File Tree/)).toBeTruthy()
    expect(screen.getByText(/Some features are unavailable/)).toBeTruthy()
  })
})
