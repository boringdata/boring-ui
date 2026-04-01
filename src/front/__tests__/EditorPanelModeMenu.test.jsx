import React from 'react'
import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import DataContext from '../shared/providers/data/DataContext'
import EditorPanel from '../shared/panels/EditorPanel'

vi.mock('../shared/components/Editor', () => ({
  default: () => <div data-testid="editor-stub" />,
}))

vi.mock('../shared/components/CodeEditor', () => ({
  default: () => <div data-testid="code-editor-stub" />,
}))

vi.mock('../shared/components/GitDiff', () => ({
  default: () => <div data-testid="git-diff-stub" />,
}))

const createProvider = () => ({
  files: {
    list: vi.fn(),
    read: vi.fn(async () => 'print("hello")'),
    write: vi.fn(async () => undefined),
    delete: vi.fn(),
    rename: vi.fn(),
    move: vi.fn(),
    search: vi.fn(),
  },
  git: {
    status: vi.fn(async () => ({ available: true, files: [] })),
    diff: vi.fn(async () => 'diff --git a/main.py b/main.py'),
    show: vi.fn(async () => 'print("before")'),
  },
})

describe('EditorPanel code mode dropdown', () => {
  it('switches from code mode to patch mode via dropdown menu', async () => {
    const provider = createProvider()
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0 },
        mutations: { retry: false },
      },
    })

    render(
      <QueryClientProvider client={queryClient}>
        <DataContext.Provider value={provider}>
          <EditorPanel params={{ path: 'main.py', initialContent: 'print("hello")', initialMode: 'rendered' }} />
        </DataContext.Provider>
      </QueryClientProvider>,
    )

    const trigger = await screen.findByRole('button', { name: /Code/i })
    fireEvent.keyDown(trigger, { key: 'Enter' })

    await waitFor(() => {
      expect(trigger).toHaveAttribute('aria-expanded', 'true')
    })

    const patchOption = await screen.findByRole('menuitem', { name: /Patch/i })
    fireEvent.click(patchOption)

    await waitFor(() => {
      expect(screen.getByTestId('git-diff-stub')).toBeInTheDocument()
    })
  })
})
