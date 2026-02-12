# Spike: sandbox-agent Middleware Extensibility

## Status: COMPLETED — Decision Made

**Bead**: bd-102t.1.4
**Timebox**: 1h (completed in ~30min)
**Date**: 2026-02-10

## Executive Summary

sandbox-agent is a **compiled Rust binary**, not a Python/Node service. It cannot
accept external middleware. However, it already has **built-in bearer token auth**
and **CORS support** via CLI flags, which are sufficient for Direct Connect.

**Decision: USE BUILT-IN TOKEN AUTH** — no fork, no patch, no wrapper needed.

## Investigation Findings

### 1. Architecture Discovery

| Aspect | Expected (per architecture doc) | Actual |
|--------|-------------------------------|--------|
| Language | Python (FastAPI/Starlette) | **Rust** (compiled ELF binary) |
| Framework | Web framework with middleware | Monolithic HTTP server |
| Extensibility | Middleware injection | **None** — fixed routes |
| Auth support | Need to add middleware | **Built-in** `--token` flag |
| CORS support | Need to add middleware | **Built-in** CLI flags |

### 2. Built-in Auth: `--token` Flag

sandbox-agent supports bearer token auth natively:

```bash
sandbox-agent server --token "my-secret-token" --port 2468
```

- Client sends: `Authorization: Bearer my-secret-token`
- Server validates: exact match against `--token` value
- Without `--token` or `--no-token`: auto-generates random 24-byte hex token
- With `--no-token`: disables auth entirely (current boring-ui behavior)

### 3. Built-in CORS: CLI Flags

```bash
sandbox-agent server \
  --cors-allow-origin "http://localhost:5173" \
  --cors-allow-method "GET" \
  --cors-allow-method "POST" \
  --cors-allow-method "PUT" \
  --cors-allow-method "DELETE" \
  --cors-allow-method "OPTIONS" \
  --cors-allow-header "Authorization" \
  --cors-allow-header "Content-Type"
```

All flags are repeatable for multiple values.

### 4. Binary Details

```
File: @sandbox-agent/cli-linux-x64/bin/sandbox-agent
Type: ELF 64-bit LSB pie executable, x86-64, static-pie linked, not stripped
Size: ~24 MB
Source: https://github.com/rivet-dev/sandbox-agent (open source Rust)
```

## Decision: USE BUILT-IN TOKEN AUTH

### How It Works

1. **boring-ui startup**: Generate random token (`os.urandom(24).hex()`)
2. **Start sandbox-agent**: Pass `--token <token>` + CORS flags
3. **Capabilities endpoint**: Return token to frontend
4. **Frontend**: Send `Authorization: Bearer <token>` on all requests

### Why Not JWT?

sandbox-agent performs **simple string comparison** against the `--token` value.
It does NOT parse JWT claims (expiry, service scope, etc.).

However, this is **acceptable** because:

| Concern | JWT mitigation | Built-in token mitigation |
|---------|---------------|---------------------------|
| Unauthorized access | JWT signature check | Random token comparison |
| Token theft | 1h expiry | Token only valid while process runs |
| Service scoping | `svc` claim | Each service gets unique token |
| Network exposure | N/A | Localhost binding (127.0.0.1) |
| Cross-origin | N/A | CORS `--cors-allow-origin` |

The main JWT advantage (token expiry) is unnecessary for a localhost service
that restarts with boring-ui (new token each startup).

### Comparison to Architecture Doc Plan

The DIRECT_CONNECT_ARCHITECTURE.md (Section 3.2) planned Python JWT middleware
for sandbox-agent. This is infeasible since sandbox-agent is Rust. The updated
approach:

| Phase 2 Task | Original Plan | Updated Plan |
|-------------|---------------|-------------|
| bd-102t.3.1 (sandbox auth middleware) | Write Python JWT middleware | **Use `--token` flag** (trivial) |
| bd-102t.3.2 (sandbox CORS middleware) | Write Python CORS middleware | **Use CORS CLI flags** (trivial) |
| bd-102t.3.3 (Companion auth middleware) | Write Hono/jose middleware | **Unchanged** (Companion IS JS) |
| bd-102t.3.4 (Companion CORS middleware) | Write Hono CORS middleware | **Unchanged** |

### Impact on Architecture

**ServiceTokenIssuer** (bd-102t.2.1) still creates JWTs, but for:
- **Companion**: Full JWT validation (Hono/jose middleware, as designed)
- **Frontend token**: JWT format, validated by ServiceTokenIssuer on refresh
- **sandbox-agent**: Receives a plain random token, NOT a JWT

**Capabilities endpoint** returns per-service tokens:
```json
{
  "services": {
    "sandbox": {
      "url": "http://127.0.0.1:2468",
      "token": "<random-hex-token>",  // Plain token, not JWT
      "protocol": "rest+sse"
    },
    "companion": {
      "url": "http://127.0.0.1:3456",
      "token": "eyJhbG...",  // JWT, validated by Companion
      "protocol": "rest+ws"
    }
  }
}
```

### Updated LocalProvider Changes Needed

```python
# In local.py create() method:
process = subprocess.Popen([
    "npx", "sandbox-agent", "server",
    "--token", self._service_token,      # Was: --no-token
    "--host", "127.0.0.1",               # Already fixed (bd-102t.1.1)
    "--port", str(self.port),
    "--cors-allow-origin", self._cors_origin,
    "--cors-allow-header", "Authorization",
    "--cors-allow-header", "Content-Type",
    "--cors-allow-method", "GET",
    "--cors-allow-method", "POST",
    "--cors-allow-method", "PUT",
    "--cors-allow-method", "DELETE",
    "--cors-allow-method", "OPTIONS",
], ...)
```

## Options Considered

### Option A: Fork sandbox-agent ❌
- Compile custom Rust binary with JWT middleware
- Very high effort, maintenance nightmare
- **Rejected**: Overkill for the security model

### Option B: Auth proxy wrapper ❌
- Thin Python/Node reverse proxy in front of sandbox-agent
- Validates JWT, forwards request with plain token
- **Rejected**: Reintroduces the proxy we're trying to remove

### Option C: Use built-in `--token` ✅
- Zero changes to sandbox-agent binary
- Leverages existing auth and CORS support
- Different auth mechanism per service (token vs JWT) but same security level
- **Accepted**: Simplest, most pragmatic, sufficient security

## Action Items

1. ~~Update DIRECT_CONNECT_ARCHITECTURE.md~~ — Corrected sandbox-agent description
2. Update bd-102t.3.1 scope — "Use `--token` flag" instead of "Add auth middleware"
3. Update bd-102t.3.2 scope — "Use CORS CLI flags" instead of "Add CORS middleware"
4. bd-102t.2.3 (Pass env vars to subprocess) — Now also passes `--token` + CORS flags
