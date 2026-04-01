import React from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'

import EditorPanel from '../../shared/panels/EditorPanel'

let mockFileContent
let mockFileWrite
let mockGitStatus
let mockGitDiff
let mockGitShow

vi.mock('../../shared/components/Editor', () => ({
  default: ({ content, onChange, onAutoSave }) => (
    <div data-testid="editor-stub">
      <div data-testid="editor-content">{content}</div>
      <button type="button" onClick={() => onChange?.('next markdown')}>
        Change markdown
      </button>
      <button type="button" onClick={() => onAutoSave?.('next markdown')}>
        Save markdown
      </button>
    </div>
  ),
}))

vi.mock('../../shared/components/CodeEditor', () => ({
  default: ({ content, onChange, onAutoSave }) => (
    <div data-testid="code-editor-stub">
      <div data-testid="code-editor-content">{content}</div>
      <button type="button" onClick={() => onChange?.('next code')}>
        Change code
      </button>
      <button type="button" onClick={() => onAutoSave?.('next code')}>
        Save code
      </button>
    </div>
  ),
}))

vi.mock('../../shared/components/GitDiff', () => ({
  default: ({ diff }) => <div data-testid="git-diff-stub">{diff}</div>,
}))

vi.mock('../../shared/components/ui/dropdown-menu', () => ({
  DropdownMenu: ({ children }) => <div data-testid="dropdown-menu">{children}</div>,
  DropdownMenuTrigger: ({ children }) => <>{children}</>,
  DropdownMenuContent: ({ children }) => <div data-testid="dropdown-content">{children}</div>,
  DropdownMenuItem: ({ children, onSelect, className }) => (
    <button
      type="button"
      className={className}
      onClick={() => onSelect?.()}
    >
      {children}
    </button>
  ),
}))

vi.mock('../../shared/providers/data', () => ({
  useFileContent: () => mockFileContent,
  useFileWrite: () => mockFileWrite,
  useGitDiff: () => mockGitDiff,
  useGitShow: () => mockGitShow,
  useGitStatus: () => ({ data: mockGitStatus }),
}))

const createApiStub = () => {
  let handler = null
  return {
    onDidParametersChange: vi.fn((nextHandler) => {
      handler = nextHandler
      return { dispose: vi.fn() }
    }),
    emitParametersChange: (params) => {
      if (handler) handler({ params })
    },
  }
}

const makeParams = (overrides = {}) => ({
  path: 'README.md',
  initialContent: '# Hello',
  contentVersion: 1,
  onContentChange: vi.fn(),
  onDirtyChange: vi.fn(),
  initialMode: undefined,
  ...overrides,
})

const renderPanel = (paramsOverrides = {}, options = {}) => {
  const api = options.api ?? undefined
  return {
    ...render(<EditorPanel params={makeParams(paramsOverrides)} api={api} />),
    api,
  }
}

describe('EditorPanel', () => {
  beforeEach(() => {
    mockFileContent = {
      data: '# Hello',
      isLoading: false,
      isFetching: false,
      isSuccess: true,
      error: null,
      refetch: vi.fn(async () => ({ data: '# Hello' })),
    }
    mockFileWrite = {
      mutateAsync: vi.fn(async () => undefined),
    }
    mockGitStatus = {
      available: true,
      files: [],
    }
    mockGitDiff = {
      data: 'diff --git a/foo.js b/foo.js',
      error: null,
      refetch: vi.fn(async () => ({ data: 'diff --git a/foo.js b/foo.js' })),
    }
    mockGitShow = {
      data: 'const before = true',
      error: null,
      refetch: vi.fn(async () => ({ data: 'const before = true' })),
    }
  })

  it('renders the markdown editor shell', () => {
    const { container } = renderPanel({
      path: 'README.md',
      initialContent: '# Hello',
    })

    expect(container.querySelector('.panel-content.editor-panel-content')).toBeInTheDocument()
    expect(screen.getByTestId('editor-stub')).toBeInTheDocument()
    expect(screen.queryByTestId('code-editor-stub')).not.toBeInTheDocument()
  })

  it('renders the code editor and folder-only breadcrumbs for non-markdown files', () => {
    const { container } = renderPanel({
      path: 'src/utils/foo.js',
      initialContent: 'export const foo = 1',
    })

    expect(screen.getByTestId('code-editor-stub')).toBeInTheDocument()
    expect(screen.queryByTestId('editor-stub')).not.toBeInTheDocument()
    expect(container.querySelector('.editor-breadcrumbs')).toBeInTheDocument()
    expect(screen.getByText('src')).toBeInTheDocument()
    expect(screen.getByText('utils')).toBeInTheDocument()
    expect(container.querySelector('.editor-breadcrumbs')?.textContent).not.toContain('foo.js')
  })

  it('omits breadcrumbs when there is no path', () => {
    const { container } = renderPanel({
      path: '',
      initialContent: '',
    })

    expect(container.querySelector('.editor-breadcrumbs')).not.toBeInTheDocument()
  })

  it('shows the loading skeleton while file content is loading', () => {
    mockFileContent = {
      data: undefined,
      isLoading: true,
      isFetching: true,
      isSuccess: false,
      error: null,
      refetch: vi.fn(),
    }

    const { container } = renderPanel({
      path: 'README.md',
      initialContent: '',
    })

    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(container.querySelector('.editor-loading-state')).toBeInTheDocument()
    expect(container.querySelectorAll('.editor-loading-line')).toHaveLength(5)
  })

  it('shows an error state and retries the file query when disk load fails', () => {
    const refetch = vi.fn()
    mockFileContent = {
      data: undefined,
      isLoading: false,
      isFetching: false,
      isSuccess: false,
      error: new Error('disk exploded'),
      refetch,
    }

    renderPanel({
      path: 'README.md',
      initialContent: '',
    })

    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(screen.getByText('Could not load file')).toBeInTheDocument()
    expect(screen.getByText('disk exploded')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(refetch).toHaveBeenCalledTimes(1)
  })

  it('hides the code mode dropdown when git is unavailable', () => {
    mockGitStatus = {
      available: false,
      files: [],
    }

    const { container } = renderPanel({
      path: 'src/utils/foo.js',
      initialContent: 'export const foo = 1',
    })

    expect(container.querySelector('.code-viewer-toolbar')).not.toBeInTheDocument()
    expect(screen.queryByText('Patch')).not.toBeInTheDocument()
  })

  it('shows code and patch modes when git is available and can switch to patch view', () => {
    const { container } = renderPanel({
      path: 'src/utils/foo.js',
      initialContent: 'export const foo = 1',
    })

    expect(container.querySelector('.code-viewer-toolbar')).toBeInTheDocument()
    expect(screen.getByTitle('Edit code')).toBeInTheDocument()
    expect(screen.getByText('Patch')).toBeInTheDocument()
    expect(screen.getByTestId('code-editor-stub')).toBeInTheDocument()

    fireEvent.click(screen.getByText('Patch'))

    expect(screen.getByTestId('git-diff-stub')).toBeInTheDocument()
    expect(screen.queryByTestId('code-editor-stub')).not.toBeInTheDocument()
  })

  it('applies DockView parameter updates to internal panel state', () => {
    const api = createApiStub()
    const { container } = renderPanel(
      {
        path: 'README.md',
        initialContent: '# Hello',
      },
      { api },
    )

    expect(api.onDidParametersChange).toHaveBeenCalledTimes(1)
    expect(screen.getByTestId('editor-stub')).toBeInTheDocument()

    act(() => {
      api.emitParametersChange({
        path: 'src/utils/foo.js',
        initialContent: 'export const foo = 1',
      })
    })

    expect(screen.getByTestId('code-editor-stub')).toBeInTheDocument()
    expect(screen.queryByTestId('editor-stub')).not.toBeInTheDocument()
    expect(container.querySelector('.editor-breadcrumbs')).toBeInTheDocument()
    expect(container.querySelector('.editor-breadcrumbs')?.textContent).toContain('src')
    expect(container.querySelector('.editor-breadcrumbs')?.textContent).toContain('utils')
  })
})
