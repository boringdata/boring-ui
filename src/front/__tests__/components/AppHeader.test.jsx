import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AppHeader } from '../../components/AppHeader'

// Mock ThemeToggle
vi.mock('../../components/ThemeToggle', () => ({
  default: () => <button data-testid="theme-toggle">Toggle</button>,
}))

describe('AppHeader', () => {
  it('renders brand logo from config', () => {
    render(<AppHeader config={{ branding: { logo: '🚀' } }} projectRoot={null} />)
    expect(screen.getByText('🚀')).toBeTruthy()
  })

  it('falls back to B when no logo', () => {
    render(<AppHeader config={{}} projectRoot={null} />)
    expect(screen.getByText('B')).toBeTruthy()
  })

  it('shows project folder name as title', () => {
    render(<AppHeader config={{}} projectRoot="/home/user/my-project" />)
    expect(screen.getByText('my-project')).toBeTruthy()
  })

  it('falls back to branding name when no projectRoot', () => {
    render(<AppHeader config={{ branding: { name: 'My App' } }} projectRoot={null} />)
    expect(screen.getByText('My App')).toBeTruthy()
  })

  it('falls back to Workspace when no projectRoot or branding', () => {
    render(<AppHeader config={{}} projectRoot={null} />)
    expect(screen.getByText('Workspace')).toBeTruthy()
  })

  it('renders ThemeToggle', () => {
    render(<AppHeader config={{}} projectRoot={null} />)
    expect(screen.getByTestId('theme-toggle')).toBeTruthy()
  })

  it('has correct semantic structure', () => {
    const { container } = render(<AppHeader config={{}} projectRoot={null} />)
    expect(container.querySelector('header.app-header')).toBeTruthy()
    expect(container.querySelector('.app-header-brand')).toBeTruthy()
    expect(container.querySelector('.app-header-controls')).toBeTruthy()
  })

  it('logo has aria-hidden', () => {
    const { container } = render(<AppHeader config={{}} projectRoot={null} />)
    const logo = container.querySelector('.app-header-logo')
    expect(logo.getAttribute('aria-hidden')).toBe('true')
  })
})
