# Sprites.dev Authentication Architecture

## Overview

When running boring-ui API and sandbox-agent on a Sprites.dev VM, authentication ensures secure communication between:

1. **Browser → Boring-UI Backend** (Direct Connect)
2. **Browser → Sandbox-Agent** (Direct Connect)
3. **Boring-UI Backend ↔ Sandbox-Agent** (Internal)

## Token System

### Two Token Types

**1. JWT Tokens (HS256)**
- Used by services that can validate JWT claims (Companion, Hono frameworks)
- Format: `eyJ...` (standard JWT)
- Payload includes:
  - `sub`: "boring-ui" (issuer)
  - `svc`: service name ("companion", etc.)
  - `iat`: issued at timestamp
  - `exp`: expiration timestamp
- Default TTL: 1 hour
- Query param tokens: 120 seconds (shorter due to log-leak risk)

**2. Bearer Tokens (Plain)**
- Used by services with built-in auth (sandbox-agent)
- Format: Hex-encoded random bytes (e.g., `a1b2c3d4...`)
- No claims, no expiry
- Valid until process restart
- Generated via: `os.urandom(24).hex()` = 48-character hex string

### Signing Key Management

```python
# Each boring-ui startup generates a NEW signing key
signing_key = os.urandom(32)  # 256-bit random key

# Converted to hex for passing to subprocesses
signing_key_hex = signing_key.hex()  # 64-char hex string

# Passed via environment variable to:
# - Companion server: COMPANION_SIGNING_KEY
# - Sandbox-agent: via HTTP header or query param
```

**Important**: Signing key is **in-memory only**, regenerated each startup.
- Services must receive the key via environment variable
- No persistent key file needed
- Tokens become invalid on service restart (by design)

## Sprites.dev Deployment Flow

### 1. Backend Startup (Boring-UI API on Sprites.dev)

```bash
#!/bin/bash
# On Sprites.dev VM

export WORKSPACE_ROOT=/home/sprite/workspace
export ANTHROPIC_API_KEY=$(get-from-vault)
export EXTERNAL_HOST=sprites-vm.internal  # or IP address

# Backend starts and:
# 1. Generates random signing_key (256-bit)
# 2. Creates ServiceTokenIssuer with signing_key
# 3. Starts listening on 0.0.0.0:8000
# 4. Services can be queried at /api/capabilities

python3 -c "
from boring_ui.api.app import create_app
import uvicorn

app = create_app(
    include_sandbox=True,      # Enable sandbox-agent management
    include_companion=False,   # Or True if using Companion
)
uvicorn.run(app, host='0.0.0.0', port=8000)
"
```

### 2. Sandbox-Agent Startup (On same Sprites.dev VM)

```bash
#!/bin/bash
# On Sprites.dev VM

# Backend provides sandbox token via env var during startup
export SANDBOX_TOKEN=a1b2c3d4...  # 48-char hex bearer token
export SANDBOX_WORKSPACE=/home/sprite/workspace

# Sandbox-agent starts
sandbox-agent \
  --port 2468 \
  --token $SANDBOX_TOKEN \
  --workspace $SANDBOX_WORKSPACE
```

### 3. Browser Requests Service Info

```javascript
// Browser fetches capabilities from backend
const response = await fetch('http://sprites-vm:8000/api/capabilities');
const capabilities = await response.json();

// Response includes service registry:
{
  "services": {
    "sandbox": {
      "url": "http://sprites-vm:2468",
      "token": "a1b2c3d4...",        // Bearer token for direct connection
      "qpToken": "a1b2c3d4...",      // Same token for query params
      "protocol": "rest+sse"
    }
  }
}
```

### 4. Browser Connects Directly to Services

```javascript
// Frontend connects directly to sandbox-agent with token
const url = new URL('http://sprites-vm:2468/api/...');
const token = capabilities.services.sandbox.token;

// Include token in request headers
const response = await fetch(url, {
  headers: {
    'Authorization': `Bearer ${token}`
  }
});
```

## Security Model

### Local Network (Sprites.dev VM)

When both services run on the same Sprites.dev VM:

```
Browser (on same network or SSH tunnel)
    ↓
    ├→ Boring-UI Backend (8000)
    │  ├─ File API: /api/files/*
    │  ├─ Git API: /api/git/*
    │  ├─ Capabilities: /api/capabilities (token distribution)
    │  └─ Direct Connect: Issues tokens to services
    │
    └→ Sandbox-Agent (2468)
       ├─ Chat API: /api/v1/*
       └─ Authenticated with bearer token
```

### Token Validation in Sandbox-Agent

Sandbox-agent validates bearer tokens:

```bash
# Token from capabilities endpoint
request_token = "a1b2c3d4..."

# Configured token on agent startup
agent_token = "a1b2c3d4..."

# Simple comparison
if request_token == agent_token:
    authorize request
else:
    reject with 401
```

### Token Validation in Backend (if needed)

If backend needs to validate tokens from Companion or other JWT-based services:

```python
from boring_ui.api.auth import ServiceTokenIssuer

# Service receives signing key via env var
signing_key_hex = os.environ.get('COMPANION_SIGNING_KEY')

# Validate incoming JWT
payload = ServiceTokenIssuer.verify_token(
    token=request_token,
    signing_key_hex=signing_key_hex,
    expected_service='companion'
)

if payload is None:
    # Token invalid or expired
    return 401
```

## Implementation Details

### ServiceTokenIssuer API

```python
from boring_ui.api.auth import ServiceTokenIssuer

issuer = ServiceTokenIssuer()

# Issue JWT (HS256)
token = issuer.issue_token(
    service='sandbox',
    ttl_seconds=3600
)

# Issue short-lived JWT for query params
short_token = issuer.issue_query_param_token(service='sandbox')  # 120s

# Generate bearer token
bearer = issuer.generate_service_token()  # Random hex

# Verify JWT
payload = ServiceTokenIssuer.verify_token(
    token=token,
    signing_key_hex=issuer.signing_key_hex,
    expected_service='sandbox'
)
```

### Token Flow in app.py

```python
def create_app(...):
    # Create token issuer (in-memory signing key)
    token_issuer = ServiceTokenIssuer()

    # Generate bearer token for sandbox
    sandbox_auth_token = secrets.token_hex(16)  # 32-char hex

    # Pass signing key to Companion (if included)
    companion_config = {
        'COMPANION_SIGNING_KEY': token_issuer.signing_key_hex,
        ...
    }

    # Build service registry with tokens
    service_registry = {
        'sandbox': ServiceConnectionInfo(
            url='http://sprites-vm:2468',
            token=sandbox_auth_token,      # Bearer token
            qp_token=sandbox_auth_token,   # Same for query params
            protocol='rest+sse'
        )
    }

    # Return via capabilities endpoint
    return create_capabilities_router(
        service_registry=service_registry,
        token_issuer=token_issuer,
        ...
    )
```

## Network Topology

### Configuration 1: Local Network Access

```
┌─────────────────────────────────────┐
│       Sprites.dev VM                 │
│  (e.g., 10.0.1.50)                   │
│                                      │
│  ┌────────────────────────────────┐ │
│  │  Boring-UI API (8000)          │ │
│  │  ├─ File API                   │ │
│  │  ├─ Git API                    │ │
│  │  ├─ Capabilities (tokens)      │ │
│  │  └─ Workspace: /home/sprite    │ │
│  └────────────────────────────────┘ │
│                                      │
│  ┌────────────────────────────────┐ │
│  │  Sandbox-Agent (2468)          │ │
│  │  ├─ Chat API                   │ │
│  │  ├─ Auth: Bearer token         │ │
│  │  └─ Workspace: /home/sprite    │ │
│  └────────────────────────────────┘ │
│                                      │
└─────────────────────────────────────┘
         ↑         ↑
    Browser requests (same subnet)
```

**Pros**:
- Zero network latency for file operations
- Both services access `/home/sprite/workspace` locally
- Simple bearer token auth (no JWT overhead)

**Setup**:
```bash
# Browser on same subnet or via SSH tunnel
ssh -L 8000:sprites-vm:8000 -L 2468:sprites-vm:2468 user@sprites-vm

# Then access locally
# http://localhost:8000/api/capabilities
# http://localhost:2468/api/v1/...
```

### Configuration 2: Remote Access with SSH Tunnel

```bash
# From your local machine
ssh -L 8000:127.0.0.1:8000 -L 2468:127.0.0.1:2468 user@sprites-vm

# Browser accesses via localhost (actually tunneled to Sprites.dev)
# No changes to authentication code needed
# Token mechanism works transparently over tunnel
```

## Token Lifecycle

### Bearer Token (Sandbox-Agent)

```
┌─────────────────────────────────────────────────┐
│  Boring-UI Startup                              │
│                                                  │
│  1. Generate random bearer token                │
│     sandbox_token = os.urandom(24).hex()        │
│                                                  │
│  2. Start sandbox-agent subprocess with token   │
│     subprocess.run([                            │
│       'sandbox-agent',                          │
│       '--token', sandbox_token                  │
│     ])                                          │
│                                                  │
│  3. Build capabilities response                 │
│     {                                           │
│       "services": {                             │
│         "sandbox": {                            │
│           "token": sandbox_token  ← SAME TOKEN  │
│         }                                       │
│       }                                         │
│     }                                           │
└─────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────┐
│  Browser Connection                             │
│                                                  │
│  1. Fetch /api/capabilities                     │
│  2. Extract token from response                 │
│  3. Use token in all sandbox-agent requests     │
│     fetch(url, {                                │
│       headers: {                                │
│         'Authorization': `Bearer ${token}`      │
│       }                                         │
│     })                                          │
│                                                  │
│  4. Sandbox-agent validates:                    │
│     if (request_token == agent_token)           │
│       authorize()                               │
│     else                                        │
│       return 401                                │
└─────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────┐
│  Token Validity Period                          │
│                                                  │
│  ✓ Valid: From browser until agent restart     │
│  ✓ Scope: Bearer token for all requests        │
│  ✗ No expiry: Valid until process restarts     │
│                                                  │
│  If agent restarts:                            │
│    - Old tokens become invalid                 │
│    - Browser fetches new token from /api/cap  │
│    - New sandbox-agent has different token    │
└─────────────────────────────────────────────────┘
```

### JWT Token (Companion, if used)

```
┌─────────────────────────────────────────────────┐
│  Boring-UI Startup                              │
│                                                  │
│  1. Generate signing key (256-bit random)       │
│     signing_key = os.urandom(32)                │
│                                                  │
│  2. Create issuer                               │
│     issuer = ServiceTokenIssuer()               │
│                                                  │
│  3. Start Companion with signing key            │
│     subprocess.run([                            │
│       'companion',                              │
│       '--signing-key', issuer.signing_key_hex  │
│     ])                                          │
│                                                  │
│  4. Issue JWT on request                        │
│     token = issuer.issue_token('companion')    │
│     Payload: {                                  │
│       "sub": "boring-ui",                       │
│       "svc": "companion",                       │
│       "iat": 1704067200,                        │
│       "exp": 1704070800  ← 1 hour later        │
│     }                                           │
└─────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────┐
│  Browser Connection                             │
│                                                  │
│  1. Fetch /api/capabilities                     │
│  2. Extract JWT from response                   │
│  3. Use JWT in Companion requests               │
│                                                  │
│  4. Companion validates:                        │
│     a. Verify signature using signing_key      │
│     b. Check exp claim (not expired)            │
│     c. Check svc claim == "companion"           │
│     d. If all valid → authorize                 │
└─────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────┐
│  Token Validity Period                          │
│                                                  │
│  ✓ Valid: 1 hour from issuance                 │
│  ✓ Scope: Companion service only               │
│  ✗ Expires: After 1 hour                       │
│                                                  │
│  When expired:                                 │
│    - Browser gets 401 from Companion           │
│    - Browser re-fetches /api/capabilities      │
│    - New JWT issued with new exp time          │
│    - Retry request with new token              │
└─────────────────────────────────────────────────┘
```

## Frontend Implementation

### Getting Tokens from Backend

```javascript
// In useServiceConnection hook
async function fetchCapabilities() {
  const response = await fetch('/api/capabilities');
  const capabilities = await response.json();

  // Extract tokens
  const sandboxService = capabilities.services?.sandbox;
  if (sandboxService) {
    return {
      url: sandboxService.url,
      token: sandboxService.token,
      qpToken: sandboxService.qpToken,  // For query params
      protocol: sandboxService.protocol
    };
  }
}
```

### Using Tokens in Requests

```javascript
// For Authorization header (ideal)
const headers = {
  'Authorization': `Bearer ${token}`
};

// For query params (SSE endpoints)
const url = new URL(serviceUrl);
url.searchParams.set('token', qpToken);

// For WebSocket (as query param)
const ws = new WebSocket(`wss://...?token=${qpToken}`);
```

### Handling Token Expiry

```javascript
async function request(url, options = {}) {
  let response = await fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      'Authorization': `Bearer ${token}`
    }
  });

  if (response.status === 401) {
    // Token expired or invalid
    // Re-fetch capabilities to get new token
    capabilities = await fetchCapabilities();
    token = capabilities.token;

    // Retry request
    response = await fetch(url, {
      ...options,
      headers: {
        ...options.headers,
        'Authorization': `Bearer ${token}`
      }
    });
  }

  return response;
}
```

## Sprites.dev Integration Checklist

- [ ] **Backend Setup**
  - [ ] Export `WORKSPACE_ROOT=/home/sprite/workspace`
  - [ ] Export `ANTHROPIC_API_KEY` from Vault
  - [ ] Export `EXTERNAL_HOST=sprites-vm` (or IP)
  - [ ] Start boring-ui backend on port 8000
  - [ ] Verify `/api/capabilities` returns service registry

- [ ] **Sandbox-Agent Setup**
  - [ ] Ensure sandbox-agent binary is available on Sprites.dev
  - [ ] Backend auto-starts sandbox-agent via SandboxManager
  - [ ] Verify `/api/capabilities` includes sandbox service with token

- [ ] **Network Access**
  - [ ] Browser can reach `http://sprites-vm:8000`
  - [ ] Browser can reach `http://sprites-vm:2468`
  - [ ] Or use SSH tunnel: `ssh -L 8000:... -L 2468:...`

- [ ] **Token Testing**
  - [ ] Fetch `/api/capabilities` and extract tokens
  - [ ] Make authenticated request to sandbox-agent with token
  - [ ] Verify request succeeds with 200
  - [ ] Verify request fails with 401 if token omitted

- [ ] **End-to-End Test**
  - [ ] Browser loads app via tunnel
  - [ ] FileTree shows `/home/sprite/workspace` contents
  - [ ] Send message in chat
  - [ ] Verify agent responds
  - [ ] Check request headers contain `Authorization: Bearer <token>`

## Troubleshooting

### "401 Unauthorized" from Sandbox-Agent

```bash
# Problem: Token mismatch
# Solution: Verify token is passed correctly

# 1. Check capabilities endpoint
curl http://sprites-vm:8000/api/capabilities | jq .services.sandbox.token

# 2. Test with exact token
TOKEN=$(curl -s http://sprites-vm:8000/api/capabilities | jq -r .services.sandbox.token)
curl -H "Authorization: Bearer $TOKEN" http://sprites-vm:2468/api/v1/health

# 3. If different tokens, sandbox-agent wasn't started with correct token
# Restart backend to regenerate and restart sandbox-agent
```

### "Connection refused" to Sandbox-Agent

```bash
# Problem: Agent not running or wrong port
# Solution: Check if agent is running

# 1. Verify agent is listening
netstat -tlnp | grep 2468

# 2. Check if started by backend
ps aux | grep sandbox-agent

# 3. Check backend logs for startup errors
# Look for "SandboxManager" in output

# 4. If not running, manually start with:
SANDBOX_TOKEN=$(curl -s http://localhost:8000/api/capabilities | jq -r .services.sandbox.token)
sandbox-agent --port 2468 --token $SANDBOX_TOKEN --workspace /home/sprite/workspace
```

### Browser Shows Blank Terminal

```bash
# Problem: Frontend can't connect to services
# Solution: Check network path and tokens

# 1. In browser console, check capabilities
await fetch('/api/capabilities').then(r => r.json())

# 2. Verify URLs are correct (should be external host)
# Should see: "url": "http://sprites-vm:2468" (not localhost)

# 3. If localhost is shown, EXTERNAL_HOST env var not set
# Restart backend with: export EXTERNAL_HOST=sprites-vm

# 4. Test direct connection from browser
fetch('http://sprites-vm:2468/api/v1/health').then(r => console.log(r.status))
```

## Summary

**Key Authentication Points for Sprites.dev Deployment**:

1. **Token Generation**: ServiceTokenIssuer creates tokens on backend startup
2. **Token Distribution**: Capabilities endpoint shares tokens with browser
3. **Direct Connection**: Browser connects directly to sandbox-agent with token
4. **Token Validation**: Sandbox-agent validates bearer token via simple comparison
5. **No Proxy**: Backend is control plane only (lifecycle + auth)
6. **Local Acceleration**: File operations hit local filesystem (zero network latency)

**Token Types Summary**:
- **Bearer**: For sandbox-agent (simple, no JWT overhead)
- **JWT**: For Companion/Hono services (claims-based, with expiry)

**Network Layout**:
- Both services on same Sprites.dev VM
- Browser connects directly via SSH tunnel or local network
- All file operations are local (no network I/O)
