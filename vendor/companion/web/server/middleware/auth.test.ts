/**
 * Tests for Companion JWT auth middleware.
 *
 * Covers: fail-closed behavior, token extraction (header + query param),
 * JWT validation, service claim check, auth-disabled bypass.
 */
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { Hono } from "hono";
import * as jose from "jose";
import {
  authMiddleware,
  verifyRequestToken,
  verifyToken,
  isAuthDisabled,
} from "./auth.js";

// Test signing key (256-bit, hex-encoded)
const TEST_SECRET_HEX =
  "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
const TEST_SECRET = new Uint8Array(
  TEST_SECRET_HEX.match(/.{1,2}/g)!.map((b) => parseInt(b, 16)),
);

/** Create a valid JWT for testing. */
async function createTestJWT(
  claims: Record<string, unknown> = {},
  expiresIn = "1h",
): Promise<string> {
  return new jose.SignJWT({ sub: "boring-ui", svc: "companion", ...claims })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime(expiresIn)
    .sign(TEST_SECRET);
}

/** Save and restore env vars around tests. */
let savedEnv: Record<string, string | undefined>;

beforeEach(() => {
  savedEnv = {
    SERVICE_AUTH_SECRET: process.env.SERVICE_AUTH_SECRET,
    AUTH_DISABLED: process.env.AUTH_DISABLED,
  };
});

afterEach(() => {
  // Restore env
  for (const [key, val] of Object.entries(savedEnv)) {
    if (val === undefined) {
      delete process.env[key];
    } else {
      process.env[key] = val;
    }
  }
});

// ── isAuthDisabled ────────────────────────────────────────────────────────

describe("isAuthDisabled", () => {
  it("returns false when AUTH_DISABLED is not set", () => {
    delete process.env.AUTH_DISABLED;
    expect(isAuthDisabled()).toBe(false);
  });

  it("returns false when AUTH_DISABLED is 'false'", () => {
    process.env.AUTH_DISABLED = "false";
    expect(isAuthDisabled()).toBe(false);
  });

  it("returns true when AUTH_DISABLED is 'true'", () => {
    process.env.AUTH_DISABLED = "true";
    expect(isAuthDisabled()).toBe(true);
  });
});

// ── verifyToken ───────────────────────────────────────────────────────────

describe("verifyToken", () => {
  it("returns payload for valid companion token", async () => {
    process.env.SERVICE_AUTH_SECRET = TEST_SECRET_HEX;
    const token = await createTestJWT();
    const payload = await verifyToken(token);
    expect(payload).not.toBeNull();
    expect(payload!.svc).toBe("companion");
    expect(payload!.sub).toBe("boring-ui");
  });

  it("returns null for wrong service claim", async () => {
    process.env.SERVICE_AUTH_SECRET = TEST_SECRET_HEX;
    const token = await createTestJWT({ svc: "sandbox" });
    const payload = await verifyToken(token);
    expect(payload).toBeNull();
  });

  it("returns null for expired token", async () => {
    process.env.SERVICE_AUTH_SECRET = TEST_SECRET_HEX;
    const token = await createTestJWT({}, "-1s");
    const payload = await verifyToken(token);
    expect(payload).toBeNull();
  });

  it("returns null for token signed with wrong key", async () => {
    process.env.SERVICE_AUTH_SECRET = TEST_SECRET_HEX;
    const wrongKey = new Uint8Array(32).fill(0xff);
    const token = await new jose.SignJWT({ sub: "boring-ui", svc: "companion" })
      .setProtectedHeader({ alg: "HS256" })
      .setIssuedAt()
      .setExpirationTime("1h")
      .sign(wrongKey);
    const payload = await verifyToken(token);
    expect(payload).toBeNull();
  });

  it("returns null when no secret configured", async () => {
    delete process.env.SERVICE_AUTH_SECRET;
    const token = await createTestJWT();
    const payload = await verifyToken(token);
    expect(payload).toBeNull();
  });

  it("returns null for garbage token", async () => {
    process.env.SERVICE_AUTH_SECRET = TEST_SECRET_HEX;
    const payload = await verifyToken("not-a-jwt");
    expect(payload).toBeNull();
  });
});

// ── verifyRequestToken ────────────────────────────────────────────────────

describe("verifyRequestToken", () => {
  it("extracts token from Authorization header", async () => {
    process.env.SERVICE_AUTH_SECRET = TEST_SECRET_HEX;
    const token = await createTestJWT();
    const req = new Request("http://localhost:3456/api/sessions", {
      headers: { Authorization: `Bearer ${token}` },
    });
    const result = await verifyRequestToken(req);
    expect(result.ok).toBe(true);
  });

  it("extracts token from ?token= query param", async () => {
    process.env.SERVICE_AUTH_SECRET = TEST_SECRET_HEX;
    const token = await createTestJWT();
    const req = new Request(
      `http://localhost:3456/ws/browser/abc123?token=${token}`,
    );
    const result = await verifyRequestToken(req);
    expect(result.ok).toBe(true);
  });

  it("prefers Authorization header over query param", async () => {
    process.env.SERVICE_AUTH_SECRET = TEST_SECRET_HEX;
    const goodToken = await createTestJWT();
    const req = new Request(
      `http://localhost:3456/api/sessions?token=bad-token`,
      {
        headers: { Authorization: `Bearer ${goodToken}` },
      },
    );
    const result = await verifyRequestToken(req);
    expect(result.ok).toBe(true);
  });

  it("returns 401 when no token provided", async () => {
    process.env.SERVICE_AUTH_SECRET = TEST_SECRET_HEX;
    const req = new Request("http://localhost:3456/api/sessions");
    const result = await verifyRequestToken(req);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.status).toBe(401);
      expect(result.body.error).toContain("Missing");
    }
  });

  it("returns 503 when no secret configured", async () => {
    delete process.env.SERVICE_AUTH_SECRET;
    const req = new Request("http://localhost:3456/api/sessions");
    const result = await verifyRequestToken(req);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.status).toBe(503);
    }
  });

  it("bypasses auth when AUTH_DISABLED=true", async () => {
    process.env.AUTH_DISABLED = "true";
    delete process.env.SERVICE_AUTH_SECRET;
    const req = new Request("http://localhost:3456/api/sessions");
    const result = await verifyRequestToken(req);
    expect(result.ok).toBe(true);
  });

  it("returns 401 for invalid token", async () => {
    process.env.SERVICE_AUTH_SECRET = TEST_SECRET_HEX;
    const req = new Request("http://localhost:3456/api/sessions", {
      headers: { Authorization: "Bearer invalid-jwt" },
    });
    const result = await verifyRequestToken(req);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.status).toBe(401);
    }
  });
});

// ── Hono middleware integration ───────────────────────────────────────────

describe("authMiddleware (Hono integration)", () => {
  it("allows request with valid token", async () => {
    process.env.SERVICE_AUTH_SECRET = TEST_SECRET_HEX;
    const token = await createTestJWT();

    const app = new Hono();
    app.use("/*", authMiddleware);
    app.get("/api/sessions", (c) => c.json({ ok: true }));

    const res = await app.request("/api/sessions", {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.ok).toBe(true);
  });

  it("rejects request without token (401)", async () => {
    process.env.SERVICE_AUTH_SECRET = TEST_SECRET_HEX;

    const app = new Hono();
    app.use("/*", authMiddleware);
    app.get("/api/sessions", (c) => c.json({ ok: true }));

    const res = await app.request("/api/sessions");
    expect(res.status).toBe(401);
  });

  it("returns 503 when no secret configured", async () => {
    delete process.env.SERVICE_AUTH_SECRET;
    delete process.env.AUTH_DISABLED;

    const app = new Hono();
    app.use("/*", authMiddleware);
    app.get("/api/sessions", (c) => c.json({ ok: true }));

    const res = await app.request("/api/sessions");
    expect(res.status).toBe(503);
  });

  it("passes through when AUTH_DISABLED=true", async () => {
    process.env.AUTH_DISABLED = "true";
    delete process.env.SERVICE_AUTH_SECRET;

    const app = new Hono();
    app.use("/*", authMiddleware);
    app.get("/api/sessions", (c) => c.json({ ok: true }));

    const res = await app.request("/api/sessions");
    expect(res.status).toBe(200);
  });

  it("rejects expired token (401)", async () => {
    process.env.SERVICE_AUTH_SECRET = TEST_SECRET_HEX;
    const token = await createTestJWT({}, "-1s");

    const app = new Hono();
    app.use("/*", authMiddleware);
    app.get("/api/sessions", (c) => c.json({ ok: true }));

    const res = await app.request("/api/sessions", {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.status).toBe(401);
  });

  it("rejects token with wrong service claim (401)", async () => {
    process.env.SERVICE_AUTH_SECRET = TEST_SECRET_HEX;
    const token = await createTestJWT({ svc: "sandbox" });

    const app = new Hono();
    app.use("/*", authMiddleware);
    app.get("/api/sessions", (c) => c.json({ ok: true }));

    const res = await app.request("/api/sessions", {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.status).toBe(401);
  });
});
