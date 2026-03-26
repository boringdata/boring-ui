import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { getWorkspacePersistence } from '../services/workspacePersistence.js'
import { testConfig } from './helpers.js'

describe('workspace persistence in local mode', () => {
  let workspaceRoot = ''

  beforeAll(async () => {
    workspaceRoot = await mkdtemp(join(tmpdir(), 'bui-local-persistence-'))
  })

  afterAll(async () => {
    if (workspaceRoot) {
      await rm(workspaceRoot, { recursive: true, force: true })
    }
  })

  it('reports new workspace runtime as ready immediately', async () => {
    const persistence = getWorkspacePersistence(testConfig({
      controlPlaneProvider: 'local',
      workspaceRoot,
    }) as any)

    const workspace = await persistence.createWorkspace('local-user', 'Local Workspace')

    await expect(persistence.getWorkspaceRuntime(workspace.id)).resolves.toMatchObject({
      workspace_id: workspace.id,
      state: 'ready',
      status: 'ready',
      retryable: false,
    })

    await expect(persistence.retryWorkspaceRuntime(workspace.id)).resolves.toMatchObject({
      workspace_id: workspace.id,
      state: 'ready',
      status: 'ready',
      retryable: false,
    })
  })
})
