/**
 * Tests for Header component
 *
 * Features tested:
 * - Branding display (logo, name)
 * - Title formatting with context
 * - Logo rendering (string, component, element)
 * - User menu integration
 * - Theme toggle visibility
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import Header from '../../components/Header'
import { ConfigProvider } from '../../config'

// Mock child components
vi.mock('../../components/ThemeToggle', () => ({
  default: () => <div data-testid="theme-toggle">Theme Toggle</div>,
}))

vi.mock('../../components/UserMenu', () => ({
  default: ({ email, workspaceName }: any) => (
    <div data-testid="user-menu">
      {email} - {workspaceName}
    </div>
  ),
}))

const createConfig = (overrides = {}) => ({
  branding: {
    name: 'Test App',
    logo: 'T',
    titleFormat: (ctx: any) =>
      ctx.workspace ? `${ctx.workspace} - Test App` : 'Test App',
    ...overrides.branding,
  },
  storage: { prefix: 'test' },
  ...overrides,
})

describe('Header', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Branding Display', () => {
    it('renders app name from config', () => {
      const config = createConfig()
      render(
        <ConfigProvider config={config}>
          <Header />
        </ConfigProvider>
      )
      expect(screen.getByText('Test App')).toBeInTheDocument()
    })

    it('renders string logo as character', () => {
      const config = createConfig()
      render(
        <ConfigProvider config={config}>
          <Header />
        </ConfigProvider>
      )
      const logo = screen.getByText('T')
      expect(logo.closest('.app-header-logo')).toBeInTheDocument()
    })

    it('renders component logo when provided', () => {
      const CustomLogo = () => <span>CustomLogo</span>
      const config = createConfig({
        branding: { logo: CustomLogo },
      })

      render(
        <ConfigProvider config={config}>
          <Header />
        </ConfigProvider>
      )
      expect(screen.getByText('CustomLogo')).toBeInTheDocument()
    })

    it('renders element logo when provided', () => {
      const config = createConfig({
        branding: { logo: <span data-testid="element-logo">EL</span> },
      })

      render(
        <ConfigProvider config={config}>
          <Header />
        </ConfigProvider>
      )
      expect(screen.getByTestId('element-logo')).toBeInTheDocument()
    })

    it('fallbacks to first character of name when logo missing', () => {
      const config = createConfig({
        branding: { name: 'MyApp', logo: undefined },
      })

      render(
        <ConfigProvider config={config}>
          <Header />
        </ConfigProvider>
      )
      // Should fall back to 'M' (first char of 'MyApp')
      expect(screen.getByText('M')).toBeInTheDocument()
    })
  })

  describe('Title Formatting', () => {
    it('sets document title using titleFormat function', () => {
      const config = createConfig()
      const mockUserContext = {
        workspace: { name: 'MyWorkspace' },
      }

      render(
        <ConfigProvider config={config}>
          <Header userContext={mockUserContext} />
        </ConfigProvider>
      )

      expect(document.title).toBe('MyWorkspace - Test App')
    })

    it('ignores UUID-like workspace names in title', () => {
      const config = createConfig()
      const mockUserContext = {
        workspace: { name: 'a1b2c3d4-e5f6-4g7h-8i9j-k0l1m2n3o4p5' },
      }

      render(
        <ConfigProvider config={config}>
          <Header userContext={mockUserContext} />
        </ConfigProvider>
      )

      // Should use default title since workspace name looks like a UUID
      expect(document.title).toBe('Test App')
    })

    it('includes folder name in title context when projectRoot provided', () => {
      let titleContext: any
      const titleFormat = vi.fn((ctx) => {
        titleContext = ctx
        return 'Custom Title'
      })

      const config = createConfig({
        branding: { titleFormat },
      })

      render(
        <ConfigProvider config={config}>
          <Header projectRoot="/path/to/my-project" />
        </ConfigProvider>
      )

      expect(titleContext?.folder).toBe('my-project')
    })
  })

  describe('User Integration', () => {
    it('renders theme toggle', () => {
      const config = createConfig()
      render(
        <ConfigProvider config={config}>
          <Header />
        </ConfigProvider>
      )
      expect(screen.getByTestId('theme-toggle')).toBeInTheDocument()
    })

    it('renders user menu when cloud mode enabled with user', () => {
      const config = createConfig()
      const mockUserContext = {
        is_cloud_mode: true,
        user: {
          email: 'user@example.com',
        },
        workspace: {
          name: 'My Workspace',
        },
      }

      render(
        <ConfigProvider config={config}>
          <Header userContext={mockUserContext} />
        </ConfigProvider>
      )

      expect(screen.getByTestId('user-menu')).toBeInTheDocument()
      expect(screen.getByText(/user@example.com/)).toBeInTheDocument()
    })

    it('does not render user menu when cloud mode disabled', () => {
      const config = createConfig()
      const mockUserContext = {
        is_cloud_mode: false,
        user: {
          email: 'user@example.com',
        },
      }

      render(
        <ConfigProvider config={config}>
          <Header userContext={mockUserContext} />
        </ConfigProvider>
      )

      expect(screen.queryByTestId('user-menu')).not.toBeInTheDocument()
    })

    it('does not render user menu when no user provided', () => {
      const config = createConfig()
      const mockUserContext = {
        is_cloud_mode: true,
      }

      render(
        <ConfigProvider config={config}>
          <Header userContext={mockUserContext} />
        </ConfigProvider>
      )

      expect(screen.queryByTestId('user-menu')).not.toBeInTheDocument()
    })
  })

  describe('Structure', () => {
    it('renders as header element', () => {
      const config = createConfig()
      render(
        <ConfigProvider config={config}>
          <Header />
        </ConfigProvider>
      )

      const header = screen.getByRole('banner')
      expect(header).toHaveClass('app-header')
    })

    it('has branding section', () => {
      const config = createConfig()
      const { container } = render(
        <ConfigProvider config={config}>
          <Header />
        </ConfigProvider>
      )

      const brandingSection = container.querySelector('.app-header-brand')
      expect(brandingSection).toBeInTheDocument()
    })

    it('has controls section', () => {
      const config = createConfig()
      const { container } = render(
        <ConfigProvider config={config}>
          <Header />
        </ConfigProvider>
      )

      const controlsSection = container.querySelector('.app-header-controls')
      expect(controlsSection).toBeInTheDocument()
    })
  })
})
