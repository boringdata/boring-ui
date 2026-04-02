import { describe, expect, it, vi } from 'vitest'
import { syncWorkspaceRuntimeAndSettings } from './workspaceNavigation'

describe('syncWorkspaceRuntimeAndSettings', () => {
  it('uses root-scoped control-plane requests for runtime and settings', async () => {
    const apiFetchJson = vi.fn()
      .mockResolvedValueOnce({
        response: { ok: true, status: 200 },
        data: { runtime: { state: 'ready' } },
      })
      .mockResolvedValueOnce({
        response: { ok: true, status: 200 },
        data: { settings: { theme: 'dark' } },
      })
    const apiFetch = vi.fn()

    await syncWorkspaceRuntimeAndSettings({
      workspaceId: 'ws-test',
      apiFetchJson,
      apiFetch,
    })

    expect(apiFetchJson).toHaveBeenNthCalledWith(
      1,
      '/api/v1/workspaces/ws-test/runtime',
      expect.objectContaining({ rootScoped: true }),
    )
    expect(apiFetchJson).toHaveBeenNthCalledWith(
      2,
      '/api/v1/workspaces/ws-test/settings',
      expect.objectContaining({ rootScoped: true }),
    )
    expect(apiFetch).not.toHaveBeenCalled()
  })

  it('keeps retry and settings write calls root-scoped', async () => {
    const apiFetchJson = vi.fn()
      .mockResolvedValueOnce({
        response: { ok: true, status: 200 },
        data: { runtime: { state: 'error', retryable: true }, retryable: true },
      })
      .mockResolvedValueOnce({
        response: { ok: true, status: 200 },
        data: { runtime: { state: 'ready' } },
      })
      .mockResolvedValueOnce({
        response: { ok: true, status: 200 },
        data: { settings: { sync_interval_ms: 10000 } },
      })
    const apiFetch = vi.fn().mockResolvedValue({ ok: true })

    await syncWorkspaceRuntimeAndSettings({
      workspaceId: 'ws-test',
      writeSettings: true,
      apiFetchJson,
      apiFetch,
    })

    expect(apiFetch).toHaveBeenNthCalledWith(
      1,
      '/api/v1/workspaces/ws-test/runtime/retry',
      expect.objectContaining({ rootScoped: true, method: 'POST' }),
    )
    expect(apiFetch).toHaveBeenNthCalledWith(
      2,
      '/api/v1/workspaces/ws-test/settings',
      expect.objectContaining({ rootScoped: true, method: 'PUT' }),
    )
  })
})
