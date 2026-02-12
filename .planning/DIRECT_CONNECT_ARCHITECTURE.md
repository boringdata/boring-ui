# Direct Connect Architecture: Chat Provider Services

## Status: APPROVED — Codex-Reviewed, Fixes Applied

## 1. Problem Statement

boring-ui hosts multiple chat provider services (sandbox-agent, Companion, future others) as subprocesses. The current architecture proxies ALL traffic through boring-ui's FastAPI backend:

```
Browser → boring-ui:8000/api/sandbox/* → httpx proxy → sandbox-agent:2468
```

This worked for sandbox-agent (REST + SSE) but breaks down for Companion (REST + WebSocket):
- WebSocket proxying in Python/FastAPI is non-trivial (bidirectional relay, error handling, keepalives)
- Adds latency to every streamed token (extra hop)
- Proxy code is ~210 lines of complex HTTP forwarding per service
- Each new service multiplies proxy maintenance burden

## 2. Proposed Architecture: Direct Connect

**Core idea**: The browser connects directly to each chat service. boring-ui backend is the **control plane** (lifecycle, auth tokens), not the **data plane** (chat traffic).

### 2.1 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    boring-ui Backend (FastAPI :8000)          │
│                         CONTROL PLANE                        │
│                                                              │
│  Responsibilities:                                           │
│  • Subprocess lifecycle (start/stop/health)                  │
│  • Auth token issuance (signed JWT or HMAC)                  │
│  • Serve frontend (Vite dev or static build)                 │
│  • Project operations (files, git, PTY, approvals)           │
│  • Capabilities discovery (service URLs + tokens)            │
│                                                              │
│  NOT responsible for:                                        │
│  • Proxying chat traffic                                     │
│  • SSE/WebSocket relay                                       │
│  • Chat message routing                                      │
└──────────┬──────────────────────┬────────────────────────────┘
           │                      │
    token issuance          lifecycle mgmt
           │                      │
           ▼                      ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  sandbox-agent   │  │   Companion      │  │   Future Svc     │
│    :2468         │  │    :3456         │  │    :NNNN         │
│                  │  │                  │  │                  │
│  Auth middleware  │  │  Auth middleware  │  │  Auth middleware  │
│  CORS headers    │  │  CORS headers    │  │  CORS headers    │
│                  │  │                  │  │                  │
│  REST + SSE      │  │  REST + WS       │  │  Any protocol    │
└──────────────────┘  └──────────────────┘  └──────────────────┘
         ▲                     ▲                     ▲
         │                     │                     │
         └─────────────────────┴─────────────────────┘
                           │
                    DIRECT connections
                    (token in header/query)
                           │
                    ┌──────┴──────┐
                    │   Browser    │
                    │ (boring-ui   │
                    │  frontend)   │
                    └─────────────┘
```

### 2.2 Connection Flow

```
1. Browser loads boring-ui frontend
2. Frontend calls GET /api/capabilities
3. Backend returns:
   {
     "features": { "sandbox": true, "companion": true },
     "services": {
       "sandbox": {
         "url": "http://localhost:2468",
         "token": "eyJhbGciOiJIUzI1NiJ9...",
         "protocol": "rest+sse"
       },
       "companion": {
         "url": "http://localhost:3456",
         "token": "eyJhbGciOiJIUzI1NiJ9...",
         "protocol": "rest+ws"
       }
     }
   }
4. Frontend adapter reads service URL + token
5. Adapter connects DIRECTLY to service:
   - REST: fetch("http://localhost:2468/v1/agents", { headers: { Authorization: "Bearer <token>" } })
   - SSE:  new EventSource("http://localhost:2468/v1/events/sse?token=<token>")
   - WS:   new WebSocket("ws://localhost:3456/ws/browser/123?token=<token>")
6. All chat traffic flows directly, bypassing boring-ui backend
```

### 2.3 Token Lifecycle

**Standard JWT (PyJWT + jose)** — no custom HMAC format. Uses industry-standard HS256 JWTs.

```
boring-ui backend starts
  │
  ├── generates JWT signing key (os.urandom(32), in-memory, per-session)
  │
  ├── starts sandbox-agent subprocess
  │     env: SERVICE_AUTH_SECRET=<signing_key_hex>
  │          CORS_ORIGIN=http://localhost:5173
  │          AUTH_DISABLED=  (empty = auth ENABLED, fail-closed)
  │
  ├── starts companion subprocess
  │     env: SERVICE_AUTH_SECRET=<signing_key_hex>
  │          CORS_ORIGIN=http://localhost:5173
  │          AUTH_DISABLED=
  │
  └── on GET /api/capabilities:
        issues TWO tokens per service:

        Header token (Authorization: Bearer ...):
          { "sub": "boring-ui", "svc": "sandbox", "iat": ..., "exp": +3600s }
          Used for REST API calls. 1-hour TTL.

        Query-param token (for SSE/WS):
          { "sub": "boring-ui", "svc": "sandbox", "use": "qp", "iat": ..., "exp": +120s }
          Short-lived (2 min). Mitigates log-leak risk.
          Frontend fetches fresh qp-token just before SSE/WS connect.

Each service validates (FAIL-CLOSED):
  1. If AUTH_DISABLED=true → skip validation (explicit dev opt-out only)
  2. If SERVICE_AUTH_SECRET not set → REJECT (fail-closed, no silent bypass)
  3. JWT signature (HS256 via shared secret)
  4. Token expiry (reject if expired)
  5. Service claim matches (sandbox token can't access companion)
  6. Constant-time comparison (hmac.compare_digest / crypto.timingSafeEqual)

Token refresh:
  - Frontend calls GET /api/capabilities periodically (or on 401)
  - Gets fresh tokens (both header + qp variants)
  - No explicit refresh endpoint needed
```

## 3. What Changes

### 3.1 Backend Changes

#### Capabilities Endpoint (modify)

**File**: `src/back/boring_ui/api/capabilities.py`

Current: Returns feature flags and router list.
New: Also returns service connection info with auth tokens.

```python
# New fields in capabilities response
"services": {
    service_name: {
        "url": service.base_url,
        "token": generate_service_token(service_name, signing_key),
        "protocol": service.protocol,  # "rest+sse" | "rest+ws"
    }
    for service_name, service in active_services.items()
}
```

#### Sandbox Router (simplify)

**File**: `src/back/boring_ui/api/modules/sandbox/router.py`

Current: 210 lines — lifecycle endpoints + HTTP/SSE proxy.
New: ~40 lines — lifecycle endpoints only.

**Remove**: `proxy_to_sandbox()` (lines 101-210), the entire HTTP proxy.
**Keep**: `get_status()`, `start_sandbox()`, `stop_sandbox()`, `health_check()`, log endpoints.

#### Companion Router (create, minimal)

**File**: `src/back/boring_ui/api/modules/companion/router.py`

Only lifecycle management — no proxy at all:

```python
def create_companion_router(manager: CompanionManager) -> APIRouter:
    router = APIRouter(tags=["companion"])

    @router.get("/companion/status")
    async def get_status():
        info = await manager.get_info()
        return {"status": info.status if info else "not_running", ...}

    @router.post("/companion/start")
    async def start():
        info = await manager.ensure_running()
        return {"status": info.status, "url": info.base_url}

    @router.post("/companion/stop")
    async def stop():
        await manager.shutdown()
        return {"status": "stopped"}

    @router.get("/companion/health")
    async def health():
        return {"healthy": await manager.health_check()}

    return router
```

That's it. ~30 lines. No proxy.

#### Token Generation (create)

**File**: `src/back/boring_ui/api/auth.py` (new)

Uses **standard JWT** via PyJWT — no custom HMAC format. Tokens are standard `eyJ...` JWTs
that any JWT library can validate.

```python
import os
import time
import jwt  # PyJWT

class ServiceTokenIssuer:
    def __init__(self):
        # Random signing key, lives in memory only
        self._signing_key = os.urandom(32)

    @property
    def signing_key_hex(self) -> str:
        """Hex-encoded key to pass to subprocesses via env var."""
        return self._signing_key.hex()

    def issue_token(self, service: str, ttl_seconds: int = 3600) -> str:
        """Issue a standard HS256 JWT for a service."""
        now = int(time.time())
        payload = {
            "sub": "boring-ui",
            "svc": service,
            "iat": now,
            "exp": now + ttl_seconds,
        }
        return jwt.encode(payload, self._signing_key, algorithm="HS256")

    def issue_query_param_token(self, service: str) -> str:
        """Short-lived token (120s) safe for query params (SSE/WS)."""
        return self.issue_token(service, ttl_seconds=120)

    @staticmethod
    def verify_token(token: str, signing_key_hex: str, expected_service: str) -> dict | None:
        """Verify JWT and return payload, or None on failure.

        FAIL-CLOSED: If signing_key_hex is empty/None, returns None (reject).
        Use AUTH_DISABLED=true env var for explicit dev bypass.
        """
        if not signing_key_hex:
            return None  # fail-closed
        try:
            signing_key = bytes.fromhex(signing_key_hex)
            payload = jwt.decode(token, signing_key, algorithms=["HS256"])
            if payload.get("svc") != expected_service:
                return None
            return payload
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None
```

**Dependency**: `pip install PyJWT` (backend), `npm install jose` (services with TS)

#### Subprocess Startup (modify)

**File**: `src/back/boring_ui/api/modules/sandbox/providers/local.py` (and companion equivalent)

Pass signing key to subprocess via environment variable:

```python
env = {
    **os.environ,
    "SERVICE_AUTH_SECRET": self._token_issuer.signing_key_hex,
    "PORT": str(self.port),
}
process = await asyncio.create_subprocess_exec(*cmd, env=env)
```

### 3.2 Service-Side Auth Middleware

Each chat service needs a thin auth middleware that validates tokens. This is the ONLY modification to upstream service code.

**Design principle**: FAIL-CLOSED. Auth is always on unless explicitly disabled via `AUTH_DISABLED=true` env var. If `SERVICE_AUTH_SECRET` is not set and `AUTH_DISABLED` is not `true`, the service rejects ALL requests.

#### sandbox-agent Auth Middleware (Python)

sandbox-agent is a Python service. Add middleware using standard PyJWT:

```python
# middleware/auth.py (added to sandbox-agent)
import os
import jwt  # PyJWT

AUTH_DISABLED = os.environ.get("AUTH_DISABLED", "").lower() == "true"
AUTH_SECRET_HEX = os.environ.get("SERVICE_AUTH_SECRET", "")

def validate_token(token: str) -> bool:
    """FAIL-CLOSED: rejects unless AUTH_DISABLED=true or valid token."""
    if AUTH_DISABLED:
        return True  # Explicit dev opt-out

    if not AUTH_SECRET_HEX:
        return False  # No secret + auth enabled = reject all (fail-closed)

    try:
        signing_key = bytes.fromhex(AUTH_SECRET_HEX)
        payload = jwt.decode(token, signing_key, algorithms=["HS256"])
        return payload.get("svc") == "sandbox"
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return False
```

#### Companion Auth Middleware (Hono/TypeScript)

Companion uses Hono (TypeScript/Bun). Uses `jose` for JWT + `crypto.timingSafeEqual()`:

```typescript
// middleware/auth.ts (added to companion server)
import { createMiddleware } from 'hono/factory'
import * as jose from 'jose'

const AUTH_DISABLED = process.env.AUTH_DISABLED === 'true'
const AUTH_SECRET_HEX = process.env.SERVICE_AUTH_SECRET || ''

export const authMiddleware = createMiddleware(async (c, next) => {
  // Explicit dev opt-out only
  if (AUTH_DISABLED) return next()

  // Fail-closed: no secret + auth enabled = reject all
  if (!AUTH_SECRET_HEX) {
    return c.json({ error: 'Auth not configured' }, 503)
  }

  // Get token from header or query param (WS upgrade, SSE)
  const token = c.req.header('Authorization')?.replace('Bearer ', '')
    || c.req.query('token')

  if (!token) {
    return c.json({ error: 'Unauthorized' }, 401)
  }

  try {
    const secret = new Uint8Array(
      AUTH_SECRET_HEX.match(/.{2}/g)!.map(b => parseInt(b, 16))
    )
    const { payload } = await jose.jwtVerify(token, secret, {
      algorithms: ['HS256'],
    })
    if (payload.svc !== 'companion') {
      return c.json({ error: 'Wrong service scope' }, 403)
    }
  } catch {
    return c.json({ error: 'Invalid token' }, 401)
  }

  return next()
})
```

**Note**: `jose` library uses `crypto.subtle` / constant-time comparison internally.
No need for manual `timingSafeEqual` — the JWT library handles it.

### 3.3 Frontend Changes

#### Capabilities Hook (modify)

**File**: `src/front/hooks/useCapabilities.js` (or wherever capabilities are fetched)

Extend to expose service connection info. **Note**: capabilities now contains tokens,
so treat the response as security-sensitive (don't log, don't cache in localStorage).

```javascript
const capabilities = await fetch('/api/capabilities').then(r => r.json())

// New: service connection details
const services = capabilities.services || {}
// {
//   sandbox: { url, token, qpToken, protocol },
//   companion: { url, token, qpToken, protocol }
// }
// token = long-lived (1h) for REST headers
// qpToken = short-lived (2min) for SSE/WS query params
```

#### SandboxChat.jsx Refactoring (prerequisite)

**File**: `src/front/components/chat/SandboxChat.jsx`

Current: Has 6 hardcoded relative URLs (`/api/sandbox/v1/agents`, etc.).
Must refactor to accept `baseUrl` + `authToken` props.

```jsx
// Before (hardcoded):
const res = await fetch('/api/sandbox/v1/agents')
const sse = new EventSource('/api/sandbox/v1/events/sse')

// After (configurable):
const res = await fetch(`${baseUrl}/v1/agents`, {
  headers: { 'Authorization': `Bearer ${authToken}` }
})
// SSE: use fetch()-based ReadableStream instead of EventSource (no header auth)
const res = await fetch(`${baseUrl}/v1/events/sse`, {
  headers: { 'Authorization': `Bearer ${authToken}` }
})
const reader = res.body.getReader()
// ... process SSE stream
```

**SSE alternative**: If EventSource is preferred, use short-lived qpToken:
```javascript
const sse = new EventSource(`${baseUrl}/v1/events/sse?token=${qpToken}`)
```

#### Provider Adapters (modify)

Each adapter reads its service URL + token from capabilities instead of using relative URLs.

**Sandbox adapter** (`src/front/providers/sandbox/adapter.jsx`):

```jsx
const { services } = useCapabilities()
const sandbox = services?.sandbox

<SandboxChat
  baseUrl={sandbox?.url || '/api/sandbox'}  // fallback for backward compat
  authToken={sandbox?.token}
  qpToken={sandbox?.qpToken}  // short-lived token for SSE/WS
/>
```

**Companion adapter** (`src/front/providers/companion/adapter.jsx`):

```jsx
const { services } = useCapabilities()
const companion = services?.companion

<CompanionApp
  apiUrl={companion?.url}
  wsUrl={companion?.url.replace('http', 'ws')}
  authToken={companion?.token}
  qpToken={companion?.qpToken}  // short-lived for WS upgrade
/>
```

**Inspector adapter** — Inspector's upstream `App.tsx` has its own connection management
(ConnectScreen, session handling). The adapter wraps it and injects connection config
via props/context rather than modifying upstream code. Inspector reads sandbox service
URL + token from the same capabilities response.

#### CORS Handling

Each service must accept requests from boring-ui's origin. Added via middleware:

```
Access-Control-Allow-Origin: http://localhost:5173  (dev)
Access-Control-Allow-Origin: https://your-domain.com  (prod)
Access-Control-Allow-Headers: Authorization, Content-Type
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS
```

The allowed origin is passed to services via env var: `CORS_ORIGIN=http://localhost:5173`.

### 3.4 Service Configuration via Environment

Each subprocess receives these environment variables from boring-ui:

| Variable | Purpose | Example |
|----------|---------|---------|
| `SERVICE_AUTH_SECRET` | JWT signing key (hex) | `a1b2c3d4...` |
| `AUTH_DISABLED` | Explicit auth bypass | `true` (only for dev) |
| `CORS_ORIGIN` | Allowed browser origin (dynamic) | `http://localhost:5173` |
| `PORT` | Service port | `2468` / `3456` |
| `HOST` | Bind address | `127.0.0.1` (NEVER 0.0.0.0) |
| `DEFAULT_CWD` | Working directory | `/home/ubuntu/projects/foo` |

**FAIL-CLOSED**: If `SERVICE_AUTH_SECRET` is not set AND `AUTH_DISABLED` is not `true`,
the service rejects all requests. There is no silent bypass.

**Bind address**: Services MUST bind to `127.0.0.1`, not `0.0.0.0`.
Binding to 0.0.0.0 exposes the service to the network without auth in dev mode.
boring-ui passes `HOST=127.0.0.1` explicitly.

**CORS_ORIGIN**: Must be dynamic, not hardcoded. boring-ui detects its own origin
(Vite dev server URL or production domain) and passes it to services.

## 4. Migration Path

### 4.0 Phase 0: Prerequisites (non-breaking fixes)

1. Fix sandbox-agent bind address: `0.0.0.0` → `127.0.0.1` (security fix, do first)
2. Refactor `SandboxChat.jsx` to accept `baseUrl` + `authToken` props (replace 6 hardcoded URLs)
3. Add `PyJWT` to backend dependencies, `jose` to frontend/service dependencies
4. **No behavior change** — these are internal refactors

### 4.1 Phase 1: Token infrastructure (non-breaking, additive)

1. Create `src/back/boring_ui/api/auth.py` — ServiceTokenIssuer using PyJWT
2. Extend `/api/capabilities` to include `services` section with URLs + tokens (both header and qp variants)
3. Pass signing key + CORS origin + HOST to sandbox-agent subprocess on startup
4. **No behavior change** — existing proxy still works, new fields are additive

### 4.2 Phase 2: Auth + CORS middleware on services

1. Add auth middleware to sandbox-agent (Python, PyJWT, fail-closed)
2. Add auth middleware to Companion server (Hono, jose, fail-closed)
3. Add CORS middleware to both services (dynamic origin from env var)
4. Test: direct `fetch()` from browser to service with token works
5. **Both old (proxy) and new (direct) paths work simultaneously**

### 4.3 Phase 3: Frontend switches to direct connections

1. Update sandbox adapter to read service URL + token from capabilities
2. Update inspector adapter to read service URL + token from capabilities
3. Create companion adapter using direct connection (WS with qpToken)
4. Replace EventSource with fetch()-based SSE (or use qpToken for EventSource)
5. Auto-refresh tokens on 401 response
6. **Frontend switches to direct connections**

### 4.4 Phase 4: Remove proxy code + port Companion

1. Remove `proxy_to_sandbox()` from sandbox router (~150 lines deleted)
2. Companion router is lifecycle-only from the start (never had proxy)
3. Simplify sandbox router to lifecycle-only endpoints
4. Complete Companion UI port (upstream files, adapter, theme bridge)
5. **Proxy code eliminated, all providers operational**

## 5. Security Considerations

### 5.1 Token Security

- **Standard JWT**: HS256 via PyJWT (Python) / jose (TypeScript). No custom token format.
- **Signing key**: Random 256-bit key, generated fresh each boring-ui startup, never persisted to disk
- **Token lifetime**: Two tiers:
  - **Header tokens**: 1-hour TTL for REST API calls (Authorization header)
  - **Query-param tokens**: 2-minute TTL for SSE/WS (mitigates log-leak risk)
- **Token scope**: Each token is scoped to a specific service (`svc` claim). A sandbox token can't access companion.
- **Token validation**: Standard JWT verification via library (handles signature, expiry, constant-time comparison internally)
- **No secret in frontend**: Frontend receives opaque JWTs, never sees the signing key

### 5.2 CORS

- Services accept requests only from boring-ui's origin (dynamic, passed via `CORS_ORIGIN` env var)
- Origin detected at startup: Vite dev server URL or production domain
- `Access-Control-Allow-Credentials: false` (no cookies — token-based auth only)
- Preflight `OPTIONS` handled by CORS middleware
- **Never use wildcard origin** — even in dev, use specific origin to catch issues early

### 5.3 Network Exposure

- **Bind address**: Services ALWAYS bind to `127.0.0.1`, passed explicitly via `HOST` env var
- **CRITICAL**: sandbox-agent currently binds `0.0.0.0` — must fix to `127.0.0.1`
- **Cloud/production**: Services bind to `127.0.0.1`, exposed via reverse proxy (nginx/caddy) with TLS
- **Multi-tenant**: Each user's services run with unique signing keys, tokens are non-transferable

### 5.4 Auth Design: FAIL-CLOSED

- **If `AUTH_DISABLED=true`** → auth middleware skips validation (explicit dev opt-out only)
- **If `SERVICE_AUTH_SECRET` not set + `AUTH_DISABLED` not true** → REJECT ALL (fail-closed)
- **If service is unreachable** → capabilities reports `{ enabled: false }` for that service
- **If token expires** → frontend gets 401, re-fetches capabilities, retries with new token

### 5.5 Capabilities Endpoint Security

- `/api/capabilities` now returns auth tokens — treat as security-sensitive
- Do NOT cache tokens in localStorage or log them
- In multi-tenant, capabilities must be scoped per-user session
- Rate limiting recommended for production deployments

## 6. Deployment Considerations

### 6.1 Local Development (current)

```
localhost:8000  — boring-ui (FastAPI)
localhost:5173  — Vite dev server
localhost:2468  — sandbox-agent
localhost:3456  — companion
```

Browser on localhost:5173 connects directly to all ports. CORS allows `http://localhost:5173`.

### 6.2 Cloud / Production

```
https://app.example.com          — reverse proxy (nginx/caddy)
  ├── /                           → boring-ui frontend (static)
  ├── /api/*                      → boring-ui backend :8000
  ├── /svc/sandbox/*              → sandbox-agent :2468
  └── /svc/companion/*            → companion :3456
      (including WebSocket upgrade)
```

The reverse proxy handles TLS termination and path-based routing. Services still bind to localhost. Service URLs in capabilities become relative paths (`/svc/sandbox`) instead of `http://localhost:2468`.

### 6.3 Container / Multi-tenant

Each user gets isolated service instances with unique ports and signing keys. boring-ui orchestrates container lifecycle instead of subprocess lifecycle. Token-based auth ensures service isolation.

## 7. Files Changed Summary

### New Files
| File | Purpose | Lines (est.) |
|------|---------|-------------|
| `src/back/boring_ui/api/auth.py` | ServiceTokenIssuer (PyJWT) | ~50 |
| `src/back/boring_ui/api/modules/companion/router.py` | Lifecycle-only router | ~30 |
| `src/back/boring_ui/api/modules/companion/provider.py` | Subprocess manager | ~80 |
| `src/back/boring_ui/api/modules/companion/manager.py` | Lifecycle orchestrator | ~40 |
| `vendor/companion/web/server/middleware/auth.ts` | Companion auth middleware (jose) | ~40 |

### Modified Files
| File | Change | Impact |
|------|--------|--------|
| `src/back/boring_ui/api/capabilities.py` | Add services section with tokens | Medium (security-sensitive) |
| `src/back/boring_ui/api/modules/sandbox/router.py` | Remove proxy (~150 lines) | Medium |
| `src/back/boring_ui/api/modules/sandbox/providers/local.py` | Pass signing key + HOST + CORS env vars | Low |
| `src/front/components/chat/SandboxChat.jsx` | Refactor 6 hardcoded URLs → baseUrl + token props | Medium |
| `src/front/providers/sandbox/adapter.jsx` | Use direct URL + token from capabilities | Low |
| `src/front/providers/inspector/adapter.jsx` | Use direct URL + token from capabilities | Low |
| `src/front/providers/companion/adapter.jsx` | Use direct URL + token | Low (new file) |
| `pyproject.toml` | Add PyJWT dependency | Low |
| `package.json` | Add jose dependency | Low |

### Deleted Code
| File | Lines Removed |
|------|--------------|
| `sandbox/router.py` proxy_to_sandbox() | ~150 lines |

### New Dependencies
| Package | Where | Purpose |
|---------|-------|---------|
| `PyJWT` | Backend (pip) | Standard JWT issuance + validation |
| `jose` | Companion server (npm) | Standard JWT validation in TS |

**Net change**: ~240 lines added, ~150 lines removed. Net +90 lines, but significantly simpler.

## 8. Comparison: Proxy vs Direct Connect

| Aspect | Proxy (current) | Direct Connect (proposed) |
|--------|-----------------|---------------------------|
| Chat latency | +1 hop per message | Direct, minimal latency |
| WebSocket support | Complex relay needed | Native, no relay |
| SSE support | StreamingResponse proxy | Native, no proxy |
| Auth | Implicit (same-origin) | Explicit (token-based) |
| Lines of proxy code | ~210 per service | 0 |
| New service effort | Write full proxy router | Add auth middleware only |
| CORS complexity | None (same-origin) | Must configure per service |
| Security boundary | boring-ui backend | Token validation per service |
| Cloud deployment | Simple (single port) | Reverse proxy needed |
| Local dev | Just works | Need CORS config |
| Debugging | Opaque (traffic hidden in proxy) | Transparent (browser devtools see all) |
| Protocol agnostic | No (must handle each protocol) | Yes (services speak native protocol) |

## 9. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| CORS misconfiguration blocks requests | Medium | High | Test early in dev, document config |
| Token expiry causes intermittent failures | Low | Medium | Auto-refresh on 401, generous TTL |
| Service port conflicts | Low | Low | Configurable ports, document defaults |
| Signing key lost on restart | Expected | Low | Generate fresh tokens, services restart too |
| Browser mixed content (HTTPS page → HTTP service) | Medium (prod) | High | Reverse proxy with TLS for all paths |

## 10. Resolved Questions (from Codex Review)

1. **Custom HMAC vs standard JWT?** → **RESOLVED: Standard JWT.**
   PyJWT (Python) + jose (TypeScript). Industry standard, any library can validate.

2. **Fail-open or fail-closed auth?** → **RESOLVED: Fail-closed.**
   `AUTH_DISABLED=true` for explicit dev bypass. No secret + no flag = reject all.

3. **Token in query string leaks to logs** → **RESOLVED: Short TTL (2min) qp-tokens.**
   Plus recommend fetch()-based SSE (headers) over EventSource (query params) where possible.

4. **sandbox-agent binds 0.0.0.0** → **RESOLVED: Fix to 127.0.0.1.**
   Pass `HOST=127.0.0.1` explicitly via env var. Phase 0 prerequisite.

5. **String comparison for signature** → **RESOLVED: Use library.**
   PyJWT and jose handle constant-time comparison internally. No manual timingSafeEqual needed.

## 11. Open Questions (Remaining)

1. **Should the sandbox proxy be removed immediately or kept as fallback?**
   Decision: Keep both paths during migration, remove in Phase 4.

2. **Should tokens be per-session or per-service?**
   Decision: Per-service for simplicity.

3. **How does Inspector's own connection management interact?**
   Inspector's `App.tsx` has `ConnectScreen` + session handling. Adapter injects connection
   config via props/context — upstream code stays unmodified.

4. **How does this interact with the existing `chat_claude_code` WebSocket?**
   The Claude Code chat (`/ws/claude-stream`) stays in boring-ui backend — it's a native
   feature, not a subprocess. No change needed.
