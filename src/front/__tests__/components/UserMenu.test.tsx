import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import UserMenu from '../../components/UserMenu'

const makeProps = () => ({
  email: 'john@example.com',
  workspaceName: 'My Workspace',
  workspaceId: 'ws-123',
  onSwitchWorkspace: vi.fn(),
  onCreateWorkspace: vi.fn(),
  onOpenUserSettings: vi.fn(),
  onLogout: vi.fn(),
})

describe('UserMenu', () => {
  describe('Avatar Rendering', () => {
    it('renders first letter of email as avatar', () => {
      render(<UserMenu {...makeProps()} />)
      expect(screen.getByRole('button', { name: 'User menu' })).toHaveTextContent('J')
    })

    it('renders question mark when email is missing', () => {
      render(<UserMenu {...makeProps()} email="" />)
      expect(screen.getByRole('button', { name: 'User menu' })).toHaveTextContent('?')
    })
  })

  describe('Dropdown Toggle', () => {
    it('opens and closes when trigger is clicked', () => {
      render(<UserMenu {...makeProps()} />)

      const trigger = screen.getByRole('button', { name: 'User menu' })
      fireEvent.click(trigger)
      expect(screen.getByRole('menu')).toBeInTheDocument()

      fireEvent.click(trigger)
      expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    })

    it('closes when clicking outside', () => {
      render(
        <div>
          <UserMenu {...makeProps()} />
          <button data-testid="outside">Outside</button>
        </div>
      )

      fireEvent.click(screen.getByRole('button', { name: 'User menu' }))
      expect(screen.getByRole('menu')).toBeInTheDocument()

      fireEvent.mouseDown(screen.getByTestId('outside'))
      expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    })
  })

  describe('Dropdown Content', () => {
    it('shows identity/workspace details and expected shell controls', () => {
      render(<UserMenu {...makeProps()} />)
      fireEvent.click(screen.getByRole('button', { name: 'User menu' }))

      const menu = screen.getByRole('menu')
      expect(within(menu).getByText('john@example.com')).toBeInTheDocument()
      expect(within(menu).getByText('workspace: My Workspace')).toBeInTheDocument()
      expect(screen.getByRole('menuitem', { name: 'Switch workspace' })).toBeInTheDocument()
      expect(screen.getByRole('menuitem', { name: 'Create workspace' })).toBeInTheDocument()
      expect(screen.getByRole('menuitem', { name: 'User settings' })).toBeInTheDocument()
      expect(screen.getByRole('menuitem', { name: 'Logout' })).toBeInTheDocument()
    })

    it('invokes callbacks and closes when action is selected', () => {
      const props = makeProps()
      render(<UserMenu {...props} />)
      fireEvent.click(screen.getByRole('button', { name: 'User menu' }))
      fireEvent.click(screen.getByRole('menuitem', { name: 'Switch workspace' }))

      expect(props.onSwitchWorkspace).toHaveBeenCalledWith({ workspaceId: 'ws-123' })
      expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    })

    it('safely handles async callback rejection paths', () => {
      const props = makeProps()
      props.onSwitchWorkspace = vi.fn().mockRejectedValue(new Error('network failure'))
      render(<UserMenu {...props} />)
      fireEvent.click(screen.getByRole('button', { name: 'User menu' }))
      fireEvent.click(screen.getByRole('menuitem', { name: 'Switch workspace' }))

      expect(props.onSwitchWorkspace).toHaveBeenCalledWith({ workspaceId: 'ws-123' })
      expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    })

    it('renders disabled action items when callbacks are not provided', () => {
      render(<UserMenu email="john@example.com" workspaceName="My Workspace" workspaceId="ws-123" />)
      fireEvent.click(screen.getByRole('button', { name: 'User menu' }))

      expect(screen.getByRole('menuitem', { name: 'Switch workspace' })).toBeDisabled()
      expect(screen.getByRole('menuitem', { name: 'Create workspace' })).toBeDisabled()
      expect(screen.getByRole('menuitem', { name: 'User settings' })).toBeDisabled()
      expect(screen.getByRole('menuitem', { name: 'Logout' })).toBeDisabled()
    })

    it('shows status banner, supports retry, and disables specified actions', () => {
      const props = makeProps()
      const onRetry = vi.fn()
      render(
        <UserMenu
          {...props}
          statusMessage="Not signed in."
          statusTone="error"
          onRetry={onRetry}
          disabledActions={['switch']}
        />
      )

      fireEvent.click(screen.getByRole('button', { name: 'User menu' }))
      expect(screen.getByRole('alert')).toHaveTextContent('Not signed in.')
      expect(screen.getByRole('menuitem', { name: 'Switch workspace' })).toBeDisabled()

      fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
      expect(onRetry).toHaveBeenCalledTimes(1)
      // Retry should not close the menu (user may want to see the refreshed state).
      expect(screen.getByRole('menu')).toBeInTheDocument()
    })
  })

  describe('Accessibility and Classes', () => {
    it('sets expected aria attributes', () => {
      render(<UserMenu {...makeProps()} />)
      const trigger = screen.getByRole('button', { name: 'User menu' })
      expect(trigger).toHaveAttribute('aria-haspopup', 'true')
      expect(trigger).toHaveAttribute('aria-expanded', 'false')
    })

    it('applies expected shell class names', () => {
      const { container } = render(<UserMenu {...makeProps()} />)
      fireEvent.click(screen.getByRole('button', { name: 'User menu' }))

      expect(container.querySelector('.user-menu')).toBeInTheDocument()
      expect(container.querySelector('.user-avatar')).toBeInTheDocument()
      expect(container.querySelector('.user-menu-dropdown')).toBeInTheDocument()
      expect(container.querySelector('.user-menu-item')).toBeInTheDocument()
    })
  })
})
