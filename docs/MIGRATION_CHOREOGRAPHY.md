# Migration Dependency Graph and Commit Choreography (bd-1adh.9.2)

## Dependency Graph

```
bd-1adh.1 (Contract Freeze)
  ├── bd-1adh.2 (local-api Package) ──────────────┐
  ├── bd-1adh.3 (Config/Target Resolution) ───────┤
  └── bd-1adh.5 (Bind Address Fix) ───────────────┤
                                                   ▼
bd-1adh.4 (Sprites Transport) ──────────► bd-1adh.6 (Security Boundary)
                                                   │
                                                   ▼
                                          bd-1adh.7 (Local Mode Strategy)
                                                   │
                                                   ▼
                                          bd-1adh.8 (Verification)
                                                   │
                                                   ▼
                                          bd-1adh.9 (Docs/Rollout)
```

## Commit Sequence (Actual)

| # | Commit | Feature | Gate |
|---|--------|---------|------|
| 1 | local_api package (files, git, exec) | bd-1adh.2.1 | Import test |
| 2 | Router composition, /internal/v1 prefix | bd-1adh.2.2 | Route test |
| 3 | Hard-cut: remove legacy internal_api | bd-1adh.2.3 | Full import graph |
| 4 | APIConfig validation matrix | bd-1adh.3.1 | Startup test |
| 5 | StaticTargetResolver | bd-1adh.3.2 | 16 unit tests |
| 6 | SpritesProxyTransport + handshake | bd-1adh.4.1 | 16 unit tests |
| 7 | Error codes + parser safeguards | bd-1adh.4.2 | 22 unit tests |
| 8 | RetryPolicy + HostedClient | bd-1adh.4.3 | 12 unit tests |
| 9 | Bind address fix (companion + sandbox) | bd-1adh.5.1-5.2 | Topology log |
| 10 | Startup diagnostics | bd-1adh.5.3 | Log verification |
| 11 | INTERNAL_SANDBOX_URL validator | bd-1adh.3.3 | 19 unit tests |
| 12 | @require_capability decorator | bd-1adh.6.2 | 8 unit tests |
| 13 | Capability auth wiring in app.py | bd-1adh.6.2 | 6 integration tests |
| 14 | Security boundary tests | bd-1adh.6.3 | 12 boundary tests |
| 15 | Local mode ADR + parity mode | bd-1adh.7 | 11 parity tests |
| 16 | Verification matrix | bd-1adh.8.1 | 22 matrix tests |

## Rollback Gates

Each commit is independently revertable. Critical gates:

1. **After bd-1adh.2.3 (hard-cut)**: If import failures detected, revert commits 1-3 and restore legacy modules. Validation: `python3 -c "from boring_ui.api.app import create_app"`.

2. **After bd-1adh.4 (transport)**: Transport layer is additive — no existing code modified. Revert only if test failures appear. Validation: `pytest tests/unit/test_transport.py`.

3. **After bd-1adh.6 (security)**: Capability middleware is additive. If LOCAL mode breaks, remove the middleware from app.py. Validation: `pytest tests/unit/test_local_capability_middleware.py`.

## Migration Status

All commits have been applied. Total test coverage: 595+ unit tests.
No rollbacks needed.
