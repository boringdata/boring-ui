# Spike: sandbox-agent Middleware Extensibility

## Status: COMPLETE
## Decision: USE BUILT-IN TOKEN + CORS (Option A)

## Investigation Summary

sandbox-agent v0.1.11 is a **compiled Rust binary** built on Axum 0.7 (Tokio async runtime). It is NOT a Python or Node.js service. The binary is distributed pre-compiled via npm (`@sandbox-agent/cli-linux-x64`).

### Key Findings

| Question | Answer |
|----------|--------|
| Can sandbox-agent accept external middleware? | **No** - no plugin system, no hooks |
| Is the source forkable/patchable? | **Yes** - Apache 2.0 on GitHub (rivet-dev/sandbox-agent), but requires Rust toolchain |
| Does it use a framework with middleware injection? | **Axum 0.7** - supports Tower middleware, but only at compile time |
| Can we wrap it with auth? | **Not needed** - it HAS built-in token auth + CORS via CLI flags |

### Built-in Security Features (Already in sandbox-agent)

```bash
sandbox-agent server \
  --token <SECRET>               # Static bearer token auth
  --host 127.0.0.1              # Bind to localhost only
  --cors-allow-origin <ORIGIN>   # CORS allowlist (multiple ok)
  --cors-allow-method GET,POST   # CORS methods
  --cors-allow-header Authorization,Content-Type  # CORS headers
  --cors-allow-credentials       # CORS credentials flag
```

The `--token` flag enables an Axum middleware that validates `Authorization: Bearer <token>` on all `/v1/*` routes. Token comparison uses constant-time equality (via Rust's `subtle` crate in the Axum auth layer).

## Options Evaluated

### Option A: Use Built-in Token + CORS (RECOMMENDED)

**How it works:**
1. boring-ui generates a random session token at startup (`os.urandom(16).hex()`)
2. Starts sandbox-agent with `--token <token> --cors-allow-origin http://localhost:5173 --host 127.0.0.1`
3. Frontend gets token from `GET /api/capabilities` → `services.sandbox.token`
4. Browser sends `Authorization: Bearer <token>` directly to `http://localhost:2468`

**Pros:**
- Zero proxy code needed (achieves Direct Connect goal)
- Uses sandbox-agent's own auth — no custom middleware
- CORS handled natively by sandbox-agent
- Session-scoped: new token each boring-ui restart
- Simple to implement (~20 lines changed in LocalProvider)

**Cons:**
- Static token, not time-limited (no TTL/expiry)
- Not a standard JWT (opaque string)
- Same token for all requests in a session

**Risk mitigation for static token:**
- Token rotates on every boring-ui restart (same as JWT signing key)
- Services bind to 127.0.0.1 — token only useful from localhost
- In production, reverse proxy adds TLS (token never sent in cleartext over network)

### Option B: Thin JWT Validation Proxy

Run a small Node.js/Python server in front of sandbox-agent that validates JWTs and forwards with the static token.

**Rejected because:** Adds a network hop, partially defeats Direct Connect goal. If we're proxying for auth, we might as well keep the existing proxy. Over-engineering for a local-only service.

### Option C: Fork sandbox-agent

Add JWT validation to the Rust source code.

**Rejected because:** High maintenance burden, requires Rust toolchain, breaks npm package contract, must track upstream releases.

## Architecture Revision

The Direct Connect architecture doc assumed sandbox-agent needed custom Python JWT middleware. Since sandbox-agent is Rust with built-in auth, the revised approach is simpler:

```
ORIGINAL PLAN (auth.py added to sandbox-agent):
  Browser → sandbox-agent (with custom JWT middleware)

REVISED PLAN (use built-in --token):
  Browser → sandbox-agent (with built-in Bearer token auth)
```

### Token Lifecycle (Revised)

```
boring-ui starts
  ├── generates session_token = os.urandom(16).hex()
  ├── starts sandbox-agent with --token <session_token> --cors-allow-origin <origin>
  └── GET /api/capabilities returns:
      {
        "services": {
          "sandbox": {
            "url": "http://localhost:2468",
            "token": "<session_token>",      // Bearer token for REST
            "protocol": "rest+sse"
          }
        }
      }

Browser reads capabilities, connects directly:
  fetch("http://localhost:2468/v1/agents", {
    headers: { "Authorization": "Bearer <session_token>" }
  })

  EventSource: use token as query param:
  new EventSource("http://localhost:2468/v1/events/sse?token=<session_token>")
```

**Note:** sandbox-agent's `--token` flag also supports `?token=<value>` in query params for SSE/WebSocket, matching the Direct Connect architecture's qp-token pattern.

### Impact on Phase 2 Beads

| Bead | Original Plan | Revised Plan |
|------|--------------|--------------|
| bd-102t.3.1 (auth middleware for sandbox) | Add Python JWT middleware | Pass `--token` and `--cors-allow-origin` CLI flags in LocalProvider |
| bd-102t.3.2 (CORS middleware for sandbox) | Custom CORS middleware | Pass `--cors-allow-origin` CLI flag (already supported) |
| bd-102t.2.3 (pass signing key to subprocess) | Pass JWT signing key via env | Pass static token via `--token` CLI flag |

### Impact on Companion (bd-8ftj)

Companion uses **Hono (TypeScript/Bun)** which DOES support middleware injection. The original plan for `jose` JWT middleware on Companion remains valid — Companion is TypeScript, not Rust. The `jose` npm dependency added in bd-102t.1.3 is still needed for Companion auth.

## Files to Change (Phase 2 Sandbox Auth)

```python
# src/back/boring_ui/api/modules/sandbox/providers/local.py
# Change ~5 lines in create():

import secrets

class LocalProvider(SandboxProvider):
    def __init__(self, port=2468, workspace=None, cors_origin=None):
        ...
        self._auth_token = secrets.token_hex(16)
        self._cors_origin = cors_origin or "http://localhost:5173"

    async def create(self, sandbox_id, config):
        process = subprocess.Popen([
            "npx", "sandbox-agent", "server",
            "--token", self._auth_token,      # was: --no-token
            "--host", "127.0.0.1",
            "--port", str(self.port),
            "--cors-allow-origin", self._cors_origin,
            "--cors-allow-header", "Authorization,Content-Type",
        ], ...)
```

## Conclusion

sandbox-agent's built-in auth is sufficient for Direct Connect. No custom middleware, no fork, no wrapper proxy needed. The `jose` dependency is still needed for Companion (TypeScript), but not for sandbox-agent (Rust with built-in auth).

---
*Completed: 2026-02-10*
*Bead: bd-102t.1.4*
