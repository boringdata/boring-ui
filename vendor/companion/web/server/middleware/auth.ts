/**
 * JWT auth middleware for Companion Hono server.
 *
 * FAIL-CLOSED design:
 *   1. AUTH_DISABLED=true  -> skip auth (dev/testing)
 *   2. No secret + auth on -> 503 (misconfiguration)
 *   3. Validate JWT (HS256) via jose, check svc=="companion"
 *
 * Token sources (checked in order):
 *   - Authorization: Bearer <jwt>
 *   - ?token=<jwt> query param (for WebSocket upgrade where headers unavailable)
 *
 * Exports:
 *   - authMiddleware: Hono middleware for /api/* routes
 *   - verifyRequestToken: standalone function for WS upgrade auth in Bun.serve fetch
 *   - isAuthDisabled: check if auth is disabled
 */
import { createMiddleware } from "hono/factory";
import * as jose from "jose";

const SERVICE_NAME = "companion";

/** Check if auth is disabled via env var. */
export function isAuthDisabled(): boolean {
  return process.env.AUTH_DISABLED === "true";
}

/**
 * Extract a bearer token from the request.
 * Checks Authorization header first, then ?token= query param.
 */
function extractToken(req: Request): string | null {
  const authHeader = req.headers.get("Authorization");
  if (authHeader?.startsWith("Bearer ")) {
    return authHeader.slice(7);
  }

  const url = new URL(req.url);
  return url.searchParams.get("token");
}

/**
 * Decode hex string to Uint8Array for jose.
 */
function hexToUint8Array(hex: string): Uint8Array {
  const bytes = hex.match(/.{1,2}/g);
  if (!bytes) throw new Error("Invalid hex string");
  return new Uint8Array(bytes.map((b) => parseInt(b, 16)));
}

/**
 * Verify a JWT token string and return the payload, or null on failure.
 * Does NOT check auth-disabled — caller should check isAuthDisabled() first.
 */
export async function verifyToken(
  token: string,
): Promise<jose.JWTPayload | null> {
  const secretHex = process.env.SERVICE_AUTH_SECRET;
  if (!secretHex) return null;

  try {
    const secret = hexToUint8Array(secretHex);
    const { payload } = await jose.jwtVerify(token, secret, {
      algorithms: ["HS256"],
    });

    if (payload.svc !== SERVICE_NAME) {
      return null;
    }

    return payload;
  } catch {
    return null;
  }
}

/**
 * Verify a request's token (from header or query param).
 *
 * Returns:
 *   - { ok: true, payload } on success
 *   - { ok: false, status, body } on failure (ready for Response construction)
 *
 * Handles auth-disabled and missing-secret cases.
 */
export async function verifyRequestToken(req: Request): Promise<
  | { ok: true; payload: jose.JWTPayload }
  | { ok: false; status: number; body: { error: string; detail?: string } }
> {
  if (isAuthDisabled()) {
    return { ok: true, payload: {} as jose.JWTPayload };
  }

  const secretHex = process.env.SERVICE_AUTH_SECRET;
  if (!secretHex) {
    return {
      ok: false,
      status: 503,
      body: { error: "Auth not configured", detail: "SERVICE_AUTH_SECRET not set" },
    };
  }

  const token = extractToken(req);
  if (!token) {
    return {
      ok: false,
      status: 401,
      body: { error: "Missing authentication token" },
    };
  }

  const payload = await verifyToken(token);
  if (!payload) {
    return {
      ok: false,
      status: 401,
      body: { error: "Invalid token" },
    };
  }

  return { ok: true, payload };
}

/**
 * Hono middleware for /api/* routes.
 * Use: app.use("/api/*", authMiddleware)
 */
export const authMiddleware = createMiddleware(async (c, next) => {
  const result = await verifyRequestToken(c.req.raw);

  if (!result.ok) {
    return c.json(result.body, result.status as 401 | 403 | 503);
  }

  c.set("jwtPayload", result.payload);
  return next();
});
