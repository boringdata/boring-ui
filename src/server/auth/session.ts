/**
 * Session cookie: signed JWT issuance and parsing.
 *
 * The `boring_session` cookie contains an HS256-signed JWT with user identity.
 * This implementation MUST produce tokens identical to the Python PyJWT version
 * so that cookies are interoperable during dual-stack migration.
 *
 * JWT payload fields:
 *   sub     — user_id (string)
 *   email   — lowercase email
 *   iat     — issued-at (unix timestamp)
 *   exp     — expiration (unix timestamp)
 *   app_id  — optional app scope
 */
import * as jose from 'jose'

export const COOKIE_NAME = 'boring_session'
const ALGORITHM = 'HS256'
const CLOCK_SKEW_LEEWAY_SECONDS = 30
const APP_ID_RE = /^[A-Za-z0-9_-]+$/

export class SessionError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'SessionError'
  }
}

export class SessionExpiredError extends SessionError {
  constructor(message = 'Session has expired') {
    super(message)
    this.name = 'SessionExpiredError'
  }
}

export class SessionInvalidError extends SessionError {
  constructor(message = 'Invalid session token') {
    super(message)
    this.name = 'SessionInvalidError'
  }
}

export interface SessionPayload {
  user_id: string
  email: string
  exp: number
  app_id?: string
}

/**
 * Return the app-scoped session cookie name.
 */
export function appCookieName(appId?: string): string {
  if (appId) {
    if (!APP_ID_RE.test(appId)) {
      throw new Error(`Invalid app_id for cookie name: ${appId}`)
    }
    return `${COOKIE_NAME}_${appId}`
  }
  return COOKIE_NAME
}

/**
 * Create a signed HS256 JWT for the session cookie.
 * Produces tokens compatible with Python PyJWT.
 */
export async function createSessionCookie(
  userId: string,
  email: string,
  secret: string,
  options: { ttlSeconds?: number; appId?: string } = {},
): Promise<string> {
  const { ttlSeconds = 86400, appId } = options
  const now = Math.floor(Date.now() / 1000)

  const secretKey = new TextEncoder().encode(secret)

  const builder = new jose.SignJWT({
    sub: String(userId),
    email: String(email).trim().toLowerCase(),
    app_id: appId || undefined,
  })
    .setProtectedHeader({ alg: ALGORITHM, typ: 'JWT' })
    .setIssuedAt(now)
    .setExpirationTime(now + ttlSeconds)

  return builder.sign(secretKey)
}

/**
 * Decode and validate a session cookie JWT.
 *
 * @throws SessionExpiredError if the token has expired
 * @throws SessionInvalidError if the token is malformed or signature is bad
 */
export async function parseSessionCookie(
  token: string,
  secret: string,
): Promise<SessionPayload> {
  if (!token) {
    throw new SessionInvalidError('Empty session token')
  }

  const secretKey = new TextEncoder().encode(secret)

  try {
    const { payload } = await jose.jwtVerify(token, secretKey, {
      algorithms: [ALGORITHM],
      clockTolerance: CLOCK_SKEW_LEEWAY_SECONDS,
      requiredClaims: ['sub', 'email', 'exp'],
    })

    return {
      user_id: payload.sub as string,
      email: payload.email as string,
      exp: payload.exp as number,
      app_id: (payload.app_id as string) || undefined,
    }
  } catch (err) {
    if (err instanceof jose.errors.JWTExpired) {
      throw new SessionExpiredError('Session has expired')
    }
    throw new SessionInvalidError(
      `Invalid session token: ${err instanceof Error ? err.message : String(err)}`,
    )
  }
}
