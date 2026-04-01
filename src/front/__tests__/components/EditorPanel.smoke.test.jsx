import React from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

import { getPane } from '../../registry/panes'
import EditorPanel from '../../shared/panels/EditorPanel'
import { isMarkdownFile } from '../../shared/utils/editorFiles'

let mockGitStatus

vi.mock('../../shared/components/Editor', () => ({
  default: () => <div data-testid="editor-stub">editor</div>,
}))

vi.mock('../../shared/components/CodeEditor', () => ({
  default: () => <div data-testid="code-editor-stub">code-editor</div>,
}))

vi.mock('../../shared/components/GitDiff', () => ({
  default: () => <div data-testid="git-diff-stub">git-diff</div>,
}))

vi.mock('../../shared/components/ui/dropdown-menu', () => ({
  DropdownMenu: ({ children }) => <div data-testid="dropdown-menu">{children}</div>,
  DropdownMenuTrigger: ({ children }) => <>{children}</>,
  DropdownMenuContent: ({ children }) => <div data-testid="dropdown-content">{children}</div>,
  DropdownMenuItem: ({ children, onSelect }) => (
    <button
      type="button"
      data-testid="mode-option"
      onClick={() => onSelect?.()}
    >
      {children}
    </button>
  ),
}))

vi.mock('../../shared/providers/data', () => ({
  useFileContent: () => ({
    data: 'export const foo = 1',
    isLoading: false,
    isFetching: false,
    isSuccess: true,
    error: null,
    refetch: vi.fn(async () => ({ data: 'export const foo = 1' })),
  }),
  useFileWrite: () => ({
    mutateAsync: vi.fn(async () => undefined),
  }),
  useGitDiff: () => ({
    data: 'diff --git a/foo.js b/foo.js',
    error: null,
    refetch: vi.fn(async () => ({ data: 'diff --git a/foo.js b/foo.js' })),
  }),
  useGitShow: () => ({
    data: 'const before = true',
    error: null,
    refetch: vi.fn(async () => ({ data: 'const before = true' })),
  }),
  useGitStatus: () => ({ data: mockGitStatus }),
}))

const renderPanel = (params = {}) =>
  render(
    <EditorPanel
      params={{
        path: 'src/utils/foo.js',
        initialContent: 'export const foo = 1',
        ...params,
      }}
    />,
  )

describe('EditorPanel smoke', () => {
  beforeEach(() => {
    mockGitStatus = { available: true, files: [] }
  })

  it('keeps the editor pane registry contract stable', () => {
    const config = getPane('editor')

    expect(config).toBeDefined()
    expect(config).toMatchObject({
      id: 'editor',
      essential: false,
      placement: 'center',
      requiresCapabilities: ['workspace.files'],
    })
  })

  it('keeps markdown file detection stable for md and mdx files', () => {
    expect(isMarkdownFile('README.md')).toBe(true)
    expect(isMarkdownFile('docs/post.mdx')).toBe(true)
    expect(isMarkdownFile('src/app.ts')).toBe(false)
  })

  it('shows exactly the two code-mode options with stable labels when git is available', () => {
    renderPanel()

    const options = screen.getAllByTestId('mode-option')
    expect(options).toHaveLength(2)
    expect(options[0]).toHaveTextContent('Code')
    expect(options[1]).toHaveTextContent('Patch')
  })

  it('falls back to rendered code mode when git is unavailable', async () => {
    mockGitStatus = { available: false, files: [] }
    renderPanel({ initialMode: 'git-diff' })

    await waitFor(() => {
      expect(screen.getByTestId('code-editor-stub')).toBeInTheDocument()
    })

    expect(screen.queryByTestId('git-diff-stub')).not.toBeInTheDocument()
    expect(screen.queryByTestId('dropdown-menu')).not.toBeInTheDocument()
  })

  it('renders folder-only breadcrumbs without repeating the filename', () => {
    const { container } = renderPanel({ path: 'src/utils/foo.js' })

    expect(container.querySelector('.editor-breadcrumbs')).toBeInTheDocument()
    expect(screen.getByText('src')).toBeInTheDocument()
    expect(screen.getByText('utils')).toBeInTheDocument()
    expect(container.querySelector('.editor-breadcrumbs')?.textContent).not.toContain('foo.js')
  })
})
