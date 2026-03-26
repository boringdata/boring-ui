import { beforeEach, describe, expect, it, vi } from 'vitest'

const {
  mockSelect,
  mockSql,
  mockCreateDbClient,
} = vi.hoisted(() => ({
  mockSelect: vi.fn(),
  mockSql: vi.fn(),
  mockCreateDbClient: vi.fn(),
}))

vi.mock('../db/index.js', () => ({
  createDbClient: mockCreateDbClient,
}))

import { getWorkspacePersistence } from '../services/workspacePersistence.js'
import { testConfig } from './helpers.js'

describe('hosted workspace persistence', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSelect.mockReturnValue({
      from: vi.fn().mockReturnValue({
        where: vi.fn().mockResolvedValue([{ workspaceId: '11111111-1111-1111-1111-111111111111' }]),
      }),
    })
    mockCreateDbClient.mockReturnValue({
      db: {
        select: mockSelect,
      },
      sql: mockSql.mockResolvedValue(undefined),
    })
  })

  it('returns the written settings values for hosted PUT parity', async () => {
    const persistence = getWorkspacePersistence(testConfig({
      controlPlaneProvider: 'neon',
      databaseUrl: 'postgres://test:test@localhost:5432/test',
      settingsKey: 'settings-key',
    }) as any)

    const updated = await persistence.putWorkspaceSettings(
      '11111111-1111-1111-1111-111111111111',
      { theme: 'dark', smoke_ts: '1774525741' },
    )

    expect(updated).toEqual({
      theme: 'dark',
      smoke_ts: '1774525741',
    })
    expect(mockSql).toHaveBeenCalledTimes(2)
  })
})
