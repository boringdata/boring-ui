# bd-3g1g.6.3 Evidence: agent-pi Delegation Cutover

**

## Summary

Migrates PI runtime endpoints to the canonical agent-pi route family and ensures agent-pi remains runtime-only (no file/git/pty ownership):

- PI service routes moved from legacy `/api/sessions*` to:
  - `GET /api/v1/agent/pi/sessions`
  - `POST /api/v1/agent/pi/sessions/create`
  - `GET /api/v1/agent/pi/sessions/{id}/history`
  - `POST /api/v1/agent/pi/sessions/{id}/stream`
  - `POST /api/v1/agent/pi/sessions/{id}/stop`
- Frontend PI provider updated to build canonical URLs.
- PI service hardening:
  - Safe JSON parsing in stream handler.
  - Safe percent-decoding for path session IDs (400 on malformed encoding).
  - Generic 500 error bodies (details logged server-side).
  - Explicit promise rejection handling for the async request handler.

## Commits

- `7474a37` move PI provider + pi-service to `/api/v1/agent/pi/*`
- `287cb87` server hardening + decode safety + route semantics
- `2eb3266` ensure PI routes stay canonical even when unconfigured (isConfigured only indicates remote URL presence)
- `433ec05` extra PI route tests (null/whitespace inputs)
- `751925e` replace brittle PI runtime-only guard with a behavior-level HTTP probe
- `15062d8` move PI probe to `tests/integration/` + add startup retries + probe forbidden paths with GET+POST
- `8521caf` harden PI probe health parsing + ensure killed retries are waited + avoid proxy env nondeterminism
- `3bc55c7` tighten probe types + normalize proxy env cleanup (`NO_PROXY`/`no_proxy`, unset `ALL_PROXY`)

## Verification

### Frontend (Vitest)

Environment note: `node` resolves to Bun; run vitest with system Node via PATH.

```bash
PATH=/usr/bin:$PATH npm run -s test:run -- src/front/providers/pi/routes.test.js
```

Result: PASS.

### PI service syntax check

```bash
/usr/bin/node --check src/pi_service/server.mjs
```

Result: PASS.

### UBS (staged)

```bash
ubs --staged
```

Result: PASS (js scan) after refactoring request handler to avoid dangling-promise warnings.

### Python guard

```bash
pytest -q tests/integration/test_bd_3g1g_6_3_agent_pi_runtime_surface.py
```

Result: PASS.
