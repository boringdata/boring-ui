import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../../providers/data', async () => {
  const actual = await vi.importActual('../../providers/data')
  return {
    ...actual,
    getDataProvider: vi.fn(),
    createHttpProvider: vi.fn(),
  }
})

import { __claudeStreamChatTestUtils } from '../../components/chat/ClaudeStreamChat'
import { getDataProvider, createHttpProvider } from '../../providers/data'

describe('ClaudeStreamChat DataProvider integration', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('searchFiles uses active provider from getDataProvider', async () => {
    const provider = {
      files: {
        search: vi.fn(async () => [{ path: 'src/App.jsx', name: 'App.jsx' }]),
      },
    }
    getDataProvider.mockReturnValue(provider)

    const results = await __claudeStreamChatTestUtils.searchFiles('App', vi.fn())

    expect(provider.files.search).toHaveBeenCalledWith('App')
    expect(results).toEqual([
      {
        id: 'src/App.jsx',
        label: 'App.jsx',
        path: 'src/App.jsx',
        dir: 'src',
      },
    ])
  })

  it('fetchMentionDefaults falls back to createHttpProvider when no active provider exists', async () => {
    const fallbackProvider = {
      files: {
        list: vi.fn(async () => [
          { name: 'README.md', path: 'README.md', is_dir: false },
          { name: 'src', path: 'src', is_dir: true },
        ]),
      },
    }

    getDataProvider.mockReturnValue(null)
    createHttpProvider.mockReturnValue(fallbackProvider)

    const results = await __claudeStreamChatTestUtils.fetchMentionDefaults(vi.fn())

    expect(createHttpProvider).toHaveBeenCalled()
    expect(fallbackProvider.files.list).toHaveBeenCalledWith('.')
    expect(results).toEqual([
      {
        id: 'README.md',
        label: 'README.md',
        path: 'README.md',
        dir: '',
      },
    ])
  })
})
