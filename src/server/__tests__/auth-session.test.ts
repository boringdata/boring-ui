import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  createSessionCookie,
  parseSessionCookie,
  appCookieName,
  COOKIE_NAME,
  SessionExpiredError,
  SessionInvalidError,
} from '../auth/session.js'

const TEST_SECRET = 'test-secret-must-be-at-least-32-characters-long-for-hs256'

describe('auth/session', () => {
  describe('COOKIE_NAME', () => {
    it('is boring_session', () => {
      expect(COOKIE_NAME).toBe('boring_session')
    })
  })

  describe('appCookieName', () => {
    it('returns base name when no appId', () => {
      expect(appCookieName()).toBe('boring_session')
      expect(appCookieName(undefined)).toBe('boring_session')
    })

    it('returns scoped name with appId', () => {
      expect(appCookieName('my-app')).toBe('boring_session_my-app')
    })

    it('throws on invalid appId characters', () => {
      expect(() => appCookieName('../evil')).toThrow()
    })
  })

  describe('createSessionCookie', () => {
    it('creates a valid JWT', async () => {
      const token = await createSessionCookie('user-123', 'test@example.com', TEST_SECRET, {
        ttlSeconds: 3600,
      })

      // JWT format: header.payload.signature
      expect(token.split('.').length).toBe(3)
    })

    it('includes required claims', async () => {
      const token = await createSessionCookie('user-123', 'test@example.com', TEST_SECRET, {
        ttlSeconds: 3600,
      })

      // Decode payload (no verification)
      const payload = JSON.parse(
        Buffer.from(token.split('.')[1], 'base64url').toString('utf-8'),
      )
      expect(payload.sub).toBe('user-123')
      expect(payload.email).toBe('test@example.com')
      expect(payload.iat).toBeTypeOf('number')
      expect(payload.exp).toBeTypeOf('number')
      expect(payload.exp - payload.iat).toBe(3600)
    })

    it('lowercases email', async () => {
      const token = await createSessionCookie('user-123', 'Test@EXAMPLE.com', TEST_SECRET, {
        ttlSeconds: 3600,
      })

      const payload = JSON.parse(
        Buffer.from(token.split('.')[1], 'base64url').toString('utf-8'),
      )
      expect(payload.email).toBe('test@example.com')
    })

    it('includes app_id when provided', async () => {
      const token = await createSessionCookie('user-123', 'test@example.com', TEST_SECRET, {
        ttlSeconds: 3600,
        appId: 'my-app',
      })

      const payload = JSON.parse(
        Buffer.from(token.split('.')[1], 'base64url').toString('utf-8'),
      )
      expect(payload.app_id).toBe('my-app')
    })

    it('omits app_id when not provided', async () => {
      const token = await createSessionCookie('user-123', 'test@example.com', TEST_SECRET, {
        ttlSeconds: 3600,
      })

      const payload = JSON.parse(
        Buffer.from(token.split('.')[1], 'base64url').toString('utf-8'),
      )
      expect(payload.app_id).toBeUndefined()
    })
  })

  describe('parseSessionCookie', () => {
    it('parses a valid token', async () => {
      const token = await createSessionCookie('user-123', 'test@example.com', TEST_SECRET, {
        ttlSeconds: 3600,
      })

      const session = await parseSessionCookie(token, TEST_SECRET)
      expect(session.user_id).toBe('user-123')
      expect(session.email).toBe('test@example.com')
      expect(session.exp).toBeTypeOf('number')
    })

    it('returns app_id when present', async () => {
      const token = await createSessionCookie('user-123', 'test@example.com', TEST_SECRET, {
        ttlSeconds: 3600,
        appId: 'boring-ui',
      })

      const session = await parseSessionCookie(token, TEST_SECRET)
      expect(session.app_id).toBe('boring-ui')
    })

    it('throws SessionExpiredError for expired tokens', async () => {
      const token = await createSessionCookie('user-123', 'test@example.com', TEST_SECRET, {
        ttlSeconds: -100, // Already expired
      })

      await expect(parseSessionCookie(token, TEST_SECRET)).rejects.toThrow(
        SessionExpiredError,
      )
    })

    it('throws SessionInvalidError for wrong secret', async () => {
      const token = await createSessionCookie('user-123', 'test@example.com', TEST_SECRET, {
        ttlSeconds: 3600,
      })

      await expect(
        parseSessionCookie(token, 'wrong-secret-that-is-also-long-enough'),
      ).rejects.toThrow(SessionInvalidError)
    })

    it('throws SessionInvalidError for empty token', async () => {
      await expect(parseSessionCookie('', TEST_SECRET)).rejects.toThrow(
        SessionInvalidError,
      )
    })

    it('throws SessionInvalidError for malformed token', async () => {
      await expect(
        parseSessionCookie('not.a.valid.jwt', TEST_SECRET),
      ).rejects.toThrow(SessionInvalidError)
    })

    it('roundtrips correctly', async () => {
      const token = await createSessionCookie('user-456', 'alice@example.com', TEST_SECRET, {
        ttlSeconds: 86400,
        appId: 'boring-macro',
      })

      const session = await parseSessionCookie(token, TEST_SECRET)
      expect(session.user_id).toBe('user-456')
      expect(session.email).toBe('alice@example.com')
      expect(session.app_id).toBe('boring-macro')
    })
  })
})
