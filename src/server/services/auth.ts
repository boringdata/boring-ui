/**
 * Auth service — transport-independent authentication logic.
 * Mirrors Python's control_plane auth_session.py + auth_router_neon.py.
  *
 * @deprecated Interface only — factory removed. Routes import *Impl directly.
 */
import type { SessionPayload } from '../../shared/types.js'

export interface AuthServiceDeps {
  sessionSecret: string
  neonAuthBaseUrl?: string
  controlPlaneProvider: 'local' | 'neon'
}

export interface AuthService {
  createSessionCookie(
    userId: string,
    email: string,
    options?: { ttlSeconds?: number; appId?: string },
  ): Promise<string>
  parseSessionCookie(token: string): Promise<SessionPayload>
  cookieName(appId?: string): string
}


// Session cookie constants
export const COOKIE_NAME = 'boring_session'
export const SESSION_ALGORITHM = 'HS256'
export const CLOCK_SKEW_LEEWAY_SECONDS = 30
