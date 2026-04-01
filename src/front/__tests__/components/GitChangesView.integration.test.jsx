import React from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import GitChangesView from '../../shared/components/GitChangesView'
import DataContext from '../../shared/providers/data/DataContext'
import { createHttpProvider } from '../../shared/providers/data'
import { setupApiMocks } from '../utils'

const renderWithProvider = (provider, props = {}) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <DataContext.Provider value={provider}>
        <GitChangesView {...props} />
      </DataContext.Provider>
    </QueryClientProvider>,
  )
}

describe('GitChangesView integration', () => {
  beforeEach(() => {
    setupApiMocks({
      '/api/v1/git/status': {
        available: true,
        files: [
          { path: 'src/App.jsx', status: 'M' },
          { path: 'README.md', status: 'U' },
        ],
      },
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('renders HTTP-provider git status groups and opens diff on click', async () => {
    const onOpenDiff = vi.fn()

    renderWithProvider(createHttpProvider(), { onOpenDiff })

    await waitFor(() => {
      expect(screen.getByText('Modified (1)')).toBeInTheDocument()
      expect(screen.getByText('Untracked (1)')).toBeInTheDocument()
      expect(screen.getByText('App.jsx')).toBeInTheDocument()
      expect(screen.getByText('README.md')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('App.jsx'))
    expect(onOpenDiff).toHaveBeenCalledWith('src/App.jsx', 'M')
  })
})
