import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import UserSettingsPage from '../pages/UserSettingsPage'

// Mock transport
const mockApiFetchJson = vi.fn()
vi.mock('../utils/transport', () => ({
  apiFetchJson: (...args) => mockApiFetchJson(...args),
}))

// Mock apiBase
vi.mock('../utils/apiBase', () => ({
  buildApiUrl: (path, query) => path,
}))

// Mock ThemeToggle
vi.mock('../components/ThemeToggle', () => ({
  default: () => <button data-testid="theme-toggle">Toggle</button>,
}))

// Mock useTheme
const mockToggleTheme = vi.fn()
vi.mock('../hooks/useTheme', () => ({
  useTheme: () => ({ theme: 'light', toggleTheme: mockToggleTheme }),
}))

describe('UserSettingsPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    mockApiFetchJson.mockReset()
  })

  it('shows loading state initially', () => {
    mockApiFetchJson.mockReturnValue(new Promise(() => {})) // never resolves
    render(<UserSettingsPage />)
    expect(screen.getByText('Loading settings...')).toBeInTheDocument()
  })

  it('renders profile section when authenticated', async () => {
    mockApiFetchJson.mockResolvedValue({
      response: { ok: true, status: 200 },
      data: { email: 'user@test.com', display_name: 'Test User' },
    })

    render(<UserSettingsPage />)

    await waitFor(() => {
      expect(screen.getByText('Profile')).toBeInTheDocument()
    })
    expect(screen.getByDisplayValue('user@test.com')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Test User')).toBeInTheDocument()
  })

  it('email field is disabled (read-only)', async () => {
    mockApiFetchJson.mockResolvedValue({
      response: { ok: true, status: 200 },
      data: { email: 'user@test.com', display_name: '' },
    })

    render(<UserSettingsPage />)

    await waitFor(() => {
      expect(screen.getByDisplayValue('user@test.com')).toBeDisabled()
    })
  })

  it('hides profile and account sections when not authenticated (401)', async () => {
    mockApiFetchJson.mockResolvedValue({
      response: { ok: false, status: 401 },
      data: {},
    })

    render(<UserSettingsPage />)

    await waitFor(() => {
      expect(screen.getByText('Appearance')).toBeInTheDocument()
    })
    expect(screen.queryByText('Profile')).not.toBeInTheDocument()
    expect(screen.queryByText('Account')).not.toBeInTheDocument()
  })

  it('renders appearance section with theme toggle', async () => {
    mockApiFetchJson.mockResolvedValue({
      response: { ok: false, status: 401 },
      data: {},
    })

    render(<UserSettingsPage />)

    await waitFor(() => {
      expect(screen.getByText('Appearance')).toBeInTheDocument()
    })
    expect(screen.getByText('Light')).toBeInTheDocument()
  })

  it('toggles theme when clicking theme button', async () => {
    mockApiFetchJson.mockResolvedValue({
      response: { ok: false, status: 401 },
      data: {},
    })

    render(<UserSettingsPage />)

    await waitFor(() => {
      expect(screen.getByText('Appearance')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('Light'))
    expect(mockToggleTheme).toHaveBeenCalled()
  })

  it('edits display name and saves', async () => {
    mockApiFetchJson
      .mockResolvedValueOnce({
        response: { ok: true, status: 200 },
        data: { email: 'user@test.com', display_name: 'Old Name' },
      })
      .mockResolvedValueOnce({
        response: { ok: true, status: 200 },
        data: {},
      })

    render(<UserSettingsPage />)

    await waitFor(() => {
      expect(screen.getByDisplayValue('Old Name')).toBeInTheDocument()
    })

    const nameInput = screen.getByDisplayValue('Old Name')
    fireEvent.change(nameInput, { target: { value: 'New Name' } })
    expect(nameInput.value).toBe('New Name')

    fireEvent.click(screen.getByText('Save Changes'))

    await waitFor(() => {
      expect(screen.getByText('Settings saved')).toBeInTheDocument()
    })

    // Verify save API was called with correct payload
    expect(mockApiFetchJson).toHaveBeenCalledTimes(2)
    const saveCall = mockApiFetchJson.mock.calls[1]
    expect(saveCall[0]).toBe('/api/v1/me/settings')
    expect(saveCall[1].method).toBe('PUT')
    expect(JSON.parse(saveCall[1].body)).toEqual({ display_name: 'New Name' })
  })

  it('shows error message on save failure', async () => {
    mockApiFetchJson
      .mockResolvedValueOnce({
        response: { ok: true, status: 200 },
        data: { email: 'user@test.com', display_name: 'Name' },
      })
      .mockRejectedValueOnce(new Error('Network error'))

    render(<UserSettingsPage />)

    await waitFor(() => {
      expect(screen.getByText('Save Changes')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('Save Changes'))

    await waitFor(() => {
      expect(screen.getByText('Failed to save')).toBeInTheDocument()
    })
  })

  it('renders sign out button when authenticated', async () => {
    mockApiFetchJson.mockResolvedValue({
      response: { ok: true, status: 200 },
      data: { email: 'user@test.com', display_name: '' },
    })

    render(<UserSettingsPage />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Sign Out' })).toBeInTheDocument()
    })
  })

  it('shows error state on API failure', async () => {
    mockApiFetchJson.mockResolvedValue({
      response: { ok: false, status: 500 },
      data: {},
    })

    render(<UserSettingsPage />)

    await waitFor(() => {
      expect(screen.getByText('Failed to load user info')).toBeInTheDocument()
    })
  })

  it('shows back link to workspace when workspaceId provided', async () => {
    mockApiFetchJson.mockResolvedValue({
      response: { ok: false, status: 401 },
      data: {},
    })

    render(<UserSettingsPage workspaceId="ws-123" />)

    await waitFor(() => {
      expect(screen.getByText('Appearance')).toBeInTheDocument()
    })

    const backLink = screen.getByText('Back to workspace')
    expect(backLink.closest('a')).toHaveAttribute('href', '/w/ws-123/')
  })

  it('shows page title "User Settings"', async () => {
    mockApiFetchJson.mockResolvedValue({
      response: { ok: false, status: 401 },
      data: {},
    })

    render(<UserSettingsPage />)

    await waitFor(() => {
      expect(screen.getByText('User Settings')).toBeInTheDocument()
    })
  })
})
