# V0 Local vs Sandbox Data-Flow and Failure-Path Diagrams

This document captures request and websocket behavior for V0 sandbox mode.

## Scope

- HTTP request flow in `local` mode and `sandbox` mode
- WebSocket flow for PTY/chat in `local` mode and `sandbox` mode
- Session token lifecycle for sandbox websocket attach/re-attach
- Failure normalization path from upstream errors to browser-safe responses

## 1) HTTP Data Flow: Local Mode

```mermaid
flowchart LR
    B[Browser] --> CP[Control Plane FastAPI]
    CP --> WG[WorkspaceGateway: Local]
    WG --> FS[Local FS/Git/Search/Session handlers]
    FS --> WG
    WG --> CP
    CP --> B
```

Notes:
- No proxy hop; handlers execute against local workspace root.
- Browser contract remains `/api/*`.

## 2) HTTP Data Flow: Sandbox Mode

```mermaid
flowchart LR
    B[Browser] --> CP[Control Plane FastAPI]
    CP --> WG[WorkspaceGateway: Sandbox]
    WG --> PX[SpritesProxyClient]
    PX --> WSVC[Workspace Service in Sprite]
    WSVC --> PX
    PX --> WG
    WG --> CP
    CP --> B
```

Notes:
- Control plane keeps route shapes stable while dispatching to sprite runtime.
- Guardrails and internal auth are applied before upstream delegation.

## 3) WebSocket Data Flow: PTY/Chat

```mermaid
flowchart TD
    subgraph Local
      B1[Browser WS] --> CP1[Control Plane WS Router]
      CP1 --> LPTY[Local PTY/Stream Session]
      LPTY --> CP1
      CP1 --> B1
    end

    subgraph Sandbox
      B2[Browser WS] --> CP2[Control Plane WS Router]
      CP2 --> TOK[Session token validate]
      TOK --> EX[SpritesExecClient attach/create]
      EX --> CP2
      CP2 --> B2
    end
```

Notes:
- In sandbox mode, browser sees opaque `session_id`; internal exec identity stays server-side.
- Re-attach behavior is bounded by lifecycle policy windows.

## 4) Sandbox Session Token Lifecycle

```mermaid
sequenceDiagram
    participant Browser
    participant CP as Control Plane
    participant TOK as Token Manager
    participant EX as Exec Runtime

    Browser->>CP: POST /api/sessions
    CP->>EX: create session
    EX-->>CP: exec_session_id
    CP->>TOK: mint opaque token(session_id, ttl, claims)
    TOK-->>CP: signed token
    CP-->>Browser: session_id(token)

    Browser->>CP: WS connect with session_id(token)
    CP->>TOK: validate token
    TOK-->>CP: claims or invalid
    CP->>EX: attach by claims
    EX-->>CP: attach ok / not found
    CP-->>Browser: stream frames / normalized close
```

## 5) Failure Normalization Path

```mermaid
flowchart TD
    U[Upstream failure] --> C{Classify error key}
    C -->|provider_unavailable| N1[normalize_http_error/normalize_ws_error]
    C -->|provider_timeout| N2[normalize_http_error/normalize_ws_error]
    C -->|session_not_found| N3[normalize_http_error/normalize_ws_error]
    C -->|validation| N4[normalize_http_error/normalize_ws_error]

    N1 --> R[Category + safe message + status/close code]
    N2 --> R
    N3 --> R
    N4 --> R

    R --> O[Structured log + timeline artifact]
    R --> B[Browser-safe response]
```

Notes:
- Internal details are not leaked to browser responses.
- Timelines/artifacts retain enough context for fault replay and debugging.

## 6) Failure-Path Matrix (Quick Reference)

| Failure class | HTTP status | WS close | Normalized category | Browser impact |
|---|---:|---:|---|---|
| Provider unavailable | 503 | 4006 | `provider_unavailable` | Retry/backoff path |
| Provider timeout | 504 | 4007 | `provider_timeout` | Timeout UX + retry |
| Session not found | 404 | 4001 | `not_found` | Reconnect fails deterministically |
| Session terminated | 410 | 4002 | `not_found` | New session required |
| Validation error | 400 | 4003/4004 | `validation` | Client-side correction |

## 7) Operator Use

Use these diagrams when:
- triaging parity regressions between local and sandbox mode
- explaining token and re-attach behavior during incidents
- validating whether failures were normalized at the control-plane boundary
