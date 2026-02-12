# ADR: Local Mode Strategy — Fast In-Process Default with Optional HTTP Parity Mode

**Status:** Accepted
**Date:** 2026-02-11
**Bead:** bd-1adh.7.1

## Context

boring-ui runs in two modes:

- **LOCAL mode**: Developer workstation. Control plane (api) and data plane (local-api) are in the same process.
- **HOSTED mode**: Remote deployment. Control plane proxies operations to a separate sandbox service via HTTP/WebSocket transport.

The key question: should LOCAL mode route workspace operations through the same HTTP transport layer used in HOSTED mode, or should it use fast in-process function calls?

## Decision

**Local mode uses in-process mounting by default.** The `local_api` router is mounted directly into the FastAPI app at `/internal/v1/*`, with no HTTP transport overhead.

An **optional HTTP parity mode** is available for integration testing, activated by setting `LOCAL_PARITY_MODE=http`. This routes local operations through `HTTPInternalTransport` to a co-located local-api HTTP server, exercising the same code path as hosted mode.

## Architecture

```
DEFAULT (in-process):
  Browser → app.py → local_api router (same process)
  Middleware injects full-access CapabilityAuthContext
  No token round-trips needed

PARITY MODE (http):
  Browser → app.py → HTTPInternalTransport → local-api HTTP server
  Full capability token validation (same as hosted)
  Exercises transport, retry, error mapping code paths
```

## Rationale

### Why in-process by default

1. **Speed**: No HTTP overhead for local development. File operations, git status, etc. are synchronous function calls.
2. **Simplicity**: No need to start a second service. Single `python -m boring_ui` starts everything.
3. **Reliability**: No port conflicts, no connection timeouts, no process management for the second service.

### Why optional parity mode

1. **Confidence**: Before deploying hosted mode, developers can verify that the HTTP transport layer works correctly with the same local-api handlers.
2. **Regression detection**: Transport-layer bugs (timeouts, error mapping, retry logic) are caught locally before hitting hosted infrastructure.
3. **Auth verification**: Parity mode uses real capability tokens and validates them, catching auth misconfiguration early.

### Why NOT HTTP-by-default locally

1. **Unnecessary complexity**: Local mode has no security boundary to enforce. The control plane and data plane trust each other implicitly (same process, same user).
2. **Developer friction**: Requiring two services to run locally adds startup time, debugging complexity, and failure modes.
3. **Semantic mismatch**: In local mode, the "internal" routes are not actually internal to a different service — they're internal to the same process.

## Security Invariants Preserved

Both modes maintain the same security properties:

| Property | LOCAL (default) | LOCAL (parity) | HOSTED |
|----------|----------------|----------------|--------|
| Path traversal blocked | validate_path() | validate_path() | validate_path() |
| Capability decorators present | Yes (bypassed) | Yes (enforced) | Yes (enforced) |
| Internal URLs hidden from browser | N/A (same process) | Yes | Yes |
| OIDC auth required | No | No | Yes |

## Consequences

- Local development remains fast and simple (single process).
- Integration tests can opt into HTTP parity for pre-deployment confidence.
- The `@require_capability` decorators serve as documentation and enforcement in parity/hosted modes, while being automatically satisfied in default local mode.
- No code duplication: the same `local_api` handlers are used in all modes.
