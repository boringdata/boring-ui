# Verification Report — bd-1adh Two-Module Architecture

**Date:** 2026-02-11
**Beads:** bd-1adh.8.1 (automated matrix), bd-1adh.8.2 (live E2E), bd-1adh.8.3 (proof report)

## Automated Test Matrix (bd-1adh.8.1) — PASS

All contract tests pass across LOCAL/HOSTED/Parity modes.

### Transport Contracts
| Test | LOCAL (default) | LOCAL (parity) | HOSTED | Result |
|------|----------------|----------------|--------|--------|
| /internal/v1 reachable | 200 (in-process) | 404 (not mounted) | 401 (OIDC blocks) | PASS |
| /health reachable | 200 | 200 | 200 | PASS |

### Auth Contracts
| Test | LOCAL | HOSTED | Result |
|------|-------|--------|--------|
| No OIDC required | Yes | No (401) | PASS |
| Capability context injected | Auto (wildcard) | Via middleware | PASS |
| Standalone local-api requires auth | 401 without context | N/A | PASS |
| Health exempt from OIDC | Yes | Yes | PASS |

### Path Isolation Contracts
| Attack Vector | Status | Result |
|---------------|--------|--------|
| `../../../etc/passwd` | 403 | PASS |
| `/etc/passwd` (absolute) | 403 | PASS |
| `subdir/../../../etc/shadow` | 403 | PASS |
| `..%2F..%2Fetc/passwd` (URL-encoded) | 403 | PASS |
| Valid workspace path | 200 | PASS |
| Subdirectory access | 200 | PASS |

### Error Semantics
| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| Hosted missing auth | 401 | 401 | PASS |
| File not found | 404 | 404 | PASS |
| Path traversal | 403 | 403 | PASS |
| Privileged router in hosted | ValueError | ValueError | PASS |

### Transport Error Codes
| Category | Codes Tested | Retryable | Result |
|----------|-------------|-----------|--------|
| Timeouts | SPRITES_HANDSHAKE_TIMEOUT, SPRITES_CONNECT_TIMEOUT | Yes | PASS |
| Gateway errors | HTTP_STATUS_502, 503, 504 | Yes | PASS |
| Client errors | HTTP_STATUS_400, 401, 403, 404 | No | PASS |
| Retry policy | 3 attempts, [100, 300, 900]ms backoff | N/A | PASS |

## Live Single-Sprite E2E (bd-1adh.8.2) — DEFERRED

Live sprite E2E requires:
1. Sprites.dev account with active org
2. `SPRITES_TOKEN` and `SPRITES_ORG` environment variables
3. Network access to Sprites.dev API

### Checklist (to be executed with live sprite):
- [ ] File tree reflects sprite filesystem (not host)
- [ ] Bidirectional file edits work (create, read, write, delete)
- [ ] Git parity holds (status, diff, log)
- [ ] Chat returns Claude responses via stream bridge

### How to run:
```bash
export SPRITES_TOKEN=$(vault kv get -field=api_key secret/agent/sprites)
export SPRITES_ORG="julien-hurault"
export BORING_UI_RUN_MODE=local
export SANDBOX_PROVIDER=sprites
python3 -m pytest tests/e2e/test_sprites_e2e.py -v
```

## Verdict Summary

| Dimension | Status | Tests | Notes |
|-----------|--------|-------|-------|
| Transport contracts | PASS | 4 | All 3 modes verified |
| Auth contracts | PASS | 5 | OIDC + capability auth |
| Path isolation | PASS | 6 | 4 attack vectors blocked |
| Error semantics | PASS | 4 | HTTP status codes correct |
| Error codes | PASS | 3 | Retryable classification |
| **Total automated** | **PASS** | **22** | |
| Live sprite E2E | DEFERRED | 0 | Requires live sprite |
