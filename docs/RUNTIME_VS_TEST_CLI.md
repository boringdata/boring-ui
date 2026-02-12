# Runtime vs Test CLI Distinction (bd-1adh.9.1)

## Core Rule

**Runtime code has no Sprites CLI dependency.** The `sprite` CLI is allowed only for manual validation and E2E test scripts.

## Runtime Path

The runtime code path uses:

| Component | Module | Transport |
|-----------|--------|-----------|
| Target resolution | `target_resolver.py` | Environment variables |
| Sprites proxy | `transport.py` | WebSocket (aiohttp) |
| HTTP internal | `transport.py` | HTTP (httpx/aiohttp) |
| Retry/backoff | `hosted_client.py` | Wraps transport |
| Error mapping | `error_codes.py` | In-process |

No subprocess calls to `sprite` CLI. No `shutil.which("sprite")`. No `subprocess.run(["sprite", ...])`.

## Test Path

E2E and integration tests MAY use the `sprite` CLI for:

- Provisioning test sprites (`sprite create`)
- Port forwarding (`sprite proxy`)
- Cleanup (`sprite delete`)
- Verification scripts

## Provider Assumptions

### Sprites Provider (HOSTED mode)
- Requires: `SPRITES_TARGET_SPRITE`, `SPRITES_LOCAL_API_PORT`
- Transport: WebSocket proxy via Sprites.dev API
- Auth: Sprites API token (`SPRITES_TOKEN`)

### Non-Sprites Hosted (HOSTED mode)
- Requires: `INTERNAL_SANDBOX_URL`
- Transport: Direct HTTP to internal sandbox service
- Auth: Capability tokens (RS256 JWT)
- Assumption: URL points to co-located service on private network

### Local Provider (LOCAL mode, default)
- Requires: `WORKSPACE_ROOT`
- Transport: In-process (no HTTP)
- Auth: Full-access capability context auto-injected

### Local Provider (LOCAL mode, parity)
- Requires: `WORKSPACE_ROOT`, `LOCAL_PARITY_MODE=http`, `LOCAL_PARITY_PORT`
- Transport: HTTP to co-located local-api server
- Auth: Same as hosted (capability tokens)
