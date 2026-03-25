/**
 * Shared test helpers for server tests.
 */
import { createApp, type CreateAppOptions } from '../app.js'
import { createSessionCookie } from '../auth/session.js'
import { loadConfig } from '../config.js'

export const TEST_SECRET = 'test-secret-must-be-at-least-32-characters-long-for-hs256'
export const TEST_USER_ID = 'test-user-00000000-0000-0000-0000-000000000001'
export const TEST_EMAIL = 'testuser@example.com'

export function testConfig(overrides: Record<string, unknown> = {}) {
  return { ...loadConfig(), sessionSecret: TEST_SECRET, ...overrides }
}

export function createTestApp(overrides: Record<string, unknown> = {}) {
  return createApp({
    config: testConfig(overrides) as any,
    skipValidation: true,
  })
}

export async function testSessionCookie(): Promise<string> {
  return createSessionCookie(TEST_USER_ID, TEST_EMAIL, TEST_SECRET, {
    ttlSeconds: 3600,
  })
}

/** Inject options with auth cookie pre-set */
export async function authedInject(method: string, url: string, extra: Record<string, unknown> = {}) {
  const token = await testSessionCookie()
  return {
    method,
    url,
    cookies: { boring_session: token },
    ...extra,
  }
}
