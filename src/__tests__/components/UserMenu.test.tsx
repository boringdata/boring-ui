/**
 * Tests for UserMenu component
 *
 * Features tested:
 * - Avatar rendering with email initial, displayName, or avatar URL
 * - Dropdown open/close behavior
 * - Click outside to close
 * - Workspace name display
 * - Cloud mode vs local mode
 * - onLogout callback
 * - Accessibility attributes
 * - className prop
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import UserMenu from '../../components/UserMenu'

describe('UserMenu', () => {
  const defaultProps = {
    user: {
      email: 'john@example.com',
      workspace: 'My Workspace',
      displayName: 'John Doe',
    },
    isCloudMode: true,
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('Avatar Rendering', () => {
    it('renders first letter of displayName as avatar', () => {
      render(<UserMenu {...defaultProps} />)

      const avatar = screen.getByRole('button', { name: 'User menu' })
      expect(avatar).toHaveTextContent('J')
    })

    it('renders first letter of email when no displayName', () => {
      render(<UserMenu user={{ email: 'alice@example.com' }} />)

      const avatar = screen.getByRole('button', { name: 'User menu' })
      expect(avatar).toHaveTextContent('A')
    })

    it('renders uppercase letter for avatar', () => {
      render(<UserMenu user={{ displayName: 'alice' }} />)

      const avatar = screen.getByRole('button', { name: 'User menu' })
      expect(avatar).toHaveTextContent('A')
    })

    it('renders question mark when no user data', () => {
      render(<UserMenu user={{}} />)

      const avatar = screen.getByRole('button', { name: 'User menu' })
      expect(avatar).toHaveTextContent('?')
    })

    it('renders question mark when user is undefined', () => {
      render(<UserMenu />)

      const avatar = screen.getByRole('button', { name: 'User menu' })
      expect(avatar).toHaveTextContent('?')
    })

    it('renders avatar image when avatar URL is provided', () => {
      render(<UserMenu user={{ avatar: 'https://example.com/avatar.png' }} />)

      const avatar = screen.getByRole('button', { name: 'User menu' })
      const img = avatar.querySelector('img')
      expect(img).toBeInTheDocument()
      expect(img).toHaveAttribute('src', 'https://example.com/avatar.png')
      expect(img).toHaveAttribute('alt', 'User avatar')
    })
  })

  describe('Dropdown Toggle', () => {
    it('dropdown is closed by default', () => {
      render(<UserMenu {...defaultProps} />)

      expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    })

    it('opens dropdown when avatar is clicked', () => {
      render(<UserMenu {...defaultProps} />)

      const avatar = screen.getByRole('button', { name: 'User menu' })
      fireEvent.click(avatar)

      expect(screen.getByRole('menu')).toBeInTheDocument()
    })

    it('closes dropdown when avatar is clicked again', () => {
      render(<UserMenu {...defaultProps} />)

      const avatar = screen.getByRole('button', { name: 'User menu' })
      fireEvent.click(avatar) // Open
      fireEvent.click(avatar) // Close

      expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    })

    it('closes dropdown when clicking outside', () => {
      render(
        <div>
          <UserMenu {...defaultProps} />
          <button data-testid="outside">Outside</button>
        </div>
      )

      const avatar = screen.getByRole('button', { name: 'User menu' })
      fireEvent.click(avatar)
      expect(screen.getByRole('menu')).toBeInTheDocument()

      fireEvent.mouseDown(screen.getByTestId('outside'))
      expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    })

    it('does not close when clicking inside dropdown', () => {
      render(<UserMenu {...defaultProps} />)

      const avatar = screen.getByRole('button', { name: 'User menu' })
      fireEvent.click(avatar)

      const dropdown = screen.getByRole('menu')
      fireEvent.mouseDown(dropdown)

      expect(screen.getByRole('menu')).toBeInTheDocument()
    })
  })

  describe('Dropdown Content - Cloud Mode', () => {
    it('displays user email', () => {
      render(<UserMenu {...defaultProps} />)

      const avatar = screen.getByRole('button', { name: 'User menu' })
      fireEvent.click(avatar)

      expect(screen.getByText('john@example.com')).toBeInTheDocument()
    })

    it('displays display name', () => {
      render(<UserMenu {...defaultProps} />)

      const avatar = screen.getByRole('button', { name: 'User menu' })
      fireEvent.click(avatar)

      expect(screen.getByText('John Doe')).toBeInTheDocument()
    })

    it('displays workspace name when available', () => {
      render(<UserMenu {...defaultProps} />)

      const avatar = screen.getByRole('button', { name: 'User menu' })
      fireEvent.click(avatar)

      expect(screen.getByText('workspace: My Workspace')).toBeInTheDocument()
    })

    it('hides workspace when name looks like UUID', () => {
      render(
        <UserMenu
          user={{ email: 'test@example.com', workspace: '9459aaea-4d1e-4933-88f9-538646f60e7e' }}
          isCloudMode={true}
        />
      )

      const avatar = screen.getByRole('button', { name: 'User menu' })
      fireEvent.click(avatar)

      // Should not show UUID as workspace name
      expect(screen.queryByText(/9459aaea/)).not.toBeInTheDocument()
    })

    it('displays logout button when onLogout is provided', () => {
      const onLogout = vi.fn()
      render(<UserMenu {...defaultProps} onLogout={onLogout} />)

      const avatar = screen.getByRole('button', { name: 'User menu' })
      fireEvent.click(avatar)

      expect(screen.getByRole('menuitem', { name: 'Logout' })).toBeInTheDocument()
    })

    it('does not display logout button when onLogout is not provided', () => {
      render(<UserMenu {...defaultProps} />)

      const avatar = screen.getByRole('button', { name: 'User menu' })
      fireEvent.click(avatar)

      expect(screen.queryByRole('menuitem', { name: 'Logout' })).not.toBeInTheDocument()
    })

    it('calls onLogout and closes dropdown when logout is clicked', () => {
      const onLogout = vi.fn()
      render(<UserMenu {...defaultProps} onLogout={onLogout} />)

      const avatar = screen.getByRole('button', { name: 'User menu' })
      fireEvent.click(avatar)

      const logoutButton = screen.getByRole('menuitem', { name: 'Logout' })
      fireEvent.click(logoutButton)

      expect(onLogout).toHaveBeenCalledTimes(1)
      expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    })
  })

  describe('Local Mode', () => {
    it('displays "Local Mode" text in local mode', () => {
      render(<UserMenu isCloudMode={false} />)

      const avatar = screen.getByRole('button', { name: 'User menu' })
      fireEvent.click(avatar)

      expect(screen.getByText('Local Mode')).toBeInTheDocument()
    })

    it('applies local mode class to avatar', () => {
      render(<UserMenu isCloudMode={false} />)

      expect(document.querySelector('.user-avatar--local')).toBeInTheDocument()
    })

    it('displays Exit button instead of Logout in local mode', () => {
      const onLogout = vi.fn()
      render(<UserMenu isCloudMode={false} onLogout={onLogout} />)

      const avatar = screen.getByRole('button', { name: 'User menu' })
      fireEvent.click(avatar)

      expect(screen.getByRole('menuitem', { name: 'Exit' })).toBeInTheDocument()
      expect(screen.queryByRole('menuitem', { name: 'Logout' })).not.toBeInTheDocument()
    })

    it('calls onLogout when Exit is clicked in local mode', () => {
      const onLogout = vi.fn()
      render(<UserMenu isCloudMode={false} onLogout={onLogout} />)

      const avatar = screen.getByRole('button', { name: 'User menu' })
      fireEvent.click(avatar)

      const exitButton = screen.getByRole('menuitem', { name: 'Exit' })
      fireEvent.click(exitButton)

      expect(onLogout).toHaveBeenCalledTimes(1)
    })

    it('does not show user info in local mode', () => {
      render(
        <UserMenu
          user={{ email: 'test@example.com', displayName: 'Test User' }}
          isCloudMode={false}
        />
      )

      const avatar = screen.getByRole('button', { name: 'User menu' })
      fireEvent.click(avatar)

      expect(screen.queryByText('test@example.com')).not.toBeInTheDocument()
      expect(screen.queryByText('Test User')).not.toBeInTheDocument()
    })
  })

  describe('className prop', () => {
    it('applies additional className to container', () => {
      render(<UserMenu {...defaultProps} className="custom-class" />)

      expect(document.querySelector('.user-menu.custom-class')).toBeInTheDocument()
    })

    it('applies className in local mode', () => {
      render(<UserMenu isCloudMode={false} className="local-custom" />)

      expect(document.querySelector('.user-menu.local-custom')).toBeInTheDocument()
    })
  })

  describe('Accessibility', () => {
    it('has correct aria-label on avatar button', () => {
      render(<UserMenu {...defaultProps} />)

      const avatar = screen.getByRole('button', { name: 'User menu' })
      expect(avatar).toHaveAttribute('aria-label', 'User menu')
    })

    it('has aria-expanded false when closed', () => {
      render(<UserMenu {...defaultProps} />)

      const avatar = screen.getByRole('button', { name: 'User menu' })
      expect(avatar).toHaveAttribute('aria-expanded', 'false')
    })

    it('has aria-expanded true when open', () => {
      render(<UserMenu {...defaultProps} />)

      const avatar = screen.getByRole('button', { name: 'User menu' })
      fireEvent.click(avatar)

      expect(avatar).toHaveAttribute('aria-expanded', 'true')
    })

    it('has aria-haspopup attribute', () => {
      render(<UserMenu {...defaultProps} />)

      const avatar = screen.getByRole('button', { name: 'User menu' })
      expect(avatar).toHaveAttribute('aria-haspopup', 'true')
    })

    it('dropdown has role menu', () => {
      render(<UserMenu {...defaultProps} />)

      const avatar = screen.getByRole('button', { name: 'User menu' })
      fireEvent.click(avatar)

      expect(screen.getByRole('menu')).toBeInTheDocument()
    })

    it('menu items have role menuitem', () => {
      const onLogout = vi.fn()
      render(<UserMenu {...defaultProps} onLogout={onLogout} />)

      const avatar = screen.getByRole('button', { name: 'User menu' })
      fireEvent.click(avatar)

      const menuItems = screen.getAllByRole('menuitem')
      expect(menuItems).toHaveLength(1) // Logout
    })
  })

  describe('CSS Classes', () => {
    it('applies user-menu class to container', () => {
      render(<UserMenu {...defaultProps} />)

      expect(document.querySelector('.user-menu')).toBeInTheDocument()
    })

    it('applies user-avatar class to button', () => {
      render(<UserMenu {...defaultProps} />)

      expect(document.querySelector('.user-avatar')).toBeInTheDocument()
    })

    it('applies user-menu-dropdown class when open', () => {
      render(<UserMenu {...defaultProps} />)

      const avatar = screen.getByRole('button', { name: 'User menu' })
      fireEvent.click(avatar)

      expect(document.querySelector('.user-menu-dropdown')).toBeInTheDocument()
    })

    it('applies user-menu-email class to email', () => {
      render(<UserMenu {...defaultProps} />)

      const avatar = screen.getByRole('button', { name: 'User menu' })
      fireEvent.click(avatar)

      expect(document.querySelector('.user-menu-email')).toBeInTheDocument()
    })

    it('applies user-menu-name class to display name', () => {
      render(<UserMenu {...defaultProps} />)

      const avatar = screen.getByRole('button', { name: 'User menu' })
      fireEvent.click(avatar)

      expect(document.querySelector('.user-menu-name')).toBeInTheDocument()
    })

    it('applies user-menu-workspace class when workspace name available', () => {
      render(<UserMenu {...defaultProps} />)

      const avatar = screen.getByRole('button', { name: 'User menu' })
      fireEvent.click(avatar)

      expect(document.querySelector('.user-menu-workspace')).toBeInTheDocument()
    })

    it('applies user-menu-divider class', () => {
      const onLogout = vi.fn()
      render(<UserMenu {...defaultProps} onLogout={onLogout} />)

      const avatar = screen.getByRole('button', { name: 'User menu' })
      fireEvent.click(avatar)

      expect(document.querySelector('.user-menu-divider')).toBeInTheDocument()
    })

    it('applies user-menu-item class to menu items', () => {
      const onLogout = vi.fn()
      render(<UserMenu {...defaultProps} onLogout={onLogout} />)

      const avatar = screen.getByRole('button', { name: 'User menu' })
      fireEvent.click(avatar)

      expect(document.querySelector('.user-menu-item')).toBeInTheDocument()
    })

    it('applies user-menu-header class to header section', () => {
      render(<UserMenu {...defaultProps} />)

      const avatar = screen.getByRole('button', { name: 'User menu' })
      fireEvent.click(avatar)

      expect(document.querySelector('.user-menu-header')).toBeInTheDocument()
    })
  })

  // Backward compatibility tests
  describe('Backward Compatibility', () => {
    it('works with minimal props', () => {
      render(<UserMenu />)

      const avatar = screen.getByRole('button', { name: 'User menu' })
      expect(avatar).toBeInTheDocument()
      expect(avatar).toHaveTextContent('?')
    })

    it('works with only email provided', () => {
      render(<UserMenu user={{ email: 'test@example.com' }} />)

      const avatar = screen.getByRole('button', { name: 'User menu' })
      fireEvent.click(avatar)

      expect(avatar).toHaveTextContent('T')
      expect(screen.getByText('test@example.com')).toBeInTheDocument()
    })
  })
})
