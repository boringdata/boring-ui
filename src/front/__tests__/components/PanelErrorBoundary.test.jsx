import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import PanelErrorBoundary from '../../shared/components/PanelErrorBoundary'

function BrokenChild() {
  throw new Error('Panel exploded')
}

function GoodChild() {
  return <div>Working panel</div>
}

describe('PanelErrorBoundary', () => {
  it('renders children when no error', () => {
    render(
      <PanelErrorBoundary panelName="Test">
        <GoodChild />
      </PanelErrorBoundary>,
    )
    expect(screen.getByText('Working panel')).toBeTruthy()
  })

  it('catches render errors and shows crash UI', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    render(
      <PanelErrorBoundary panelName="Editor">
        <BrokenChild />
      </PanelErrorBoundary>,
    )
    expect(screen.getByText('Editor Crashed')).toBeTruthy()
    expect(screen.getByText('Panel exploded')).toBeTruthy()
    expect(screen.getByText('Retry')).toBeTruthy()
    spy.mockRestore()
  })

  it('uses default panel name when not provided', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    render(
      <PanelErrorBoundary>
        <BrokenChild />
      </PanelErrorBoundary>,
    )
    expect(screen.getByText('Panel Crashed')).toBeTruthy()
    spy.mockRestore()
  })

  it('retry button resets error state', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    let shouldThrow = true
    function MaybeBreak() {
      if (shouldThrow) throw new Error('boom')
      return <div>Recovered</div>
    }
    render(
      <PanelErrorBoundary panelName="Test">
        <MaybeBreak />
      </PanelErrorBoundary>,
    )
    expect(screen.getByText('Test Crashed')).toBeTruthy()
    shouldThrow = false
    fireEvent.click(screen.getByText('Retry'))
    expect(screen.getByText('Recovered')).toBeTruthy()
    spy.mockRestore()
  })
})
