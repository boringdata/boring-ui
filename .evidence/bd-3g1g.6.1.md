# bd-3g1g.6.1 Evidence: agent-normal Delegation Cutover

## Summary

This bead migrates the **normal agent runtime** to canonical route families and ensures it stays runtime-only:

- Canonical HTTP session lifecycle: `GET/POST /api/v1/agent/normal/sessions`
- Canonical WS stream: `WS /ws/agent/normal/stream`
- PTY lifecycle metadata owned by pty-service: `GET/POST /api/v1/pty/sessions`
- Legacy families removed from the app surface:
  - `/api/sessions`
  - `/ws/claude-stream`

agent-normal lists PTY sessions via a pty-service helper (`boring_ui.api.modules.pty.lifecycle`) rather than reaching into PTY registry internals directly.

## Commits

- `8f90cab` agent-normal canonical routes + frontend + integration tests
- `1b74f1a` gate PTY summaries when PTY disabled; initial UUID validation work
- `f6efd44` normalize/validate session_id at PTY websocket boundary
- `c1b1bca` defense-in-depth UUID validation in PTY service
- `b16a939` canonicalize PTY session IDs + add unit coverage
- `797034e` expand PTY session_id unit coverage
- `ab9871f` clarify blank session_id behavior + cover empty-string case

## Verification

### Python

```bash
pytest -q \
  tests/unit/test_bd_3g1g_5_3_capabilities_metadata.py \
  tests/integration/test_create_app.py \
  tests/unit/test_bd_3g1g_6_1_agent_normal_delegation.py \
  tests/unit/test_bd_3g1g_6_1_pty_session_id_validation.py
```

Result: PASS.

### Frontend (Vitest)

The environment’s `node` resolves to Bun (`~/.bun/bin/node`), which breaks Vitest workers. Run with system Node:

```bash
PATH=/usr/bin:$PATH npm run -s test:run -- \
  src/front/utils/routes.test.js \
  src/front/utils/transport.test.js \
  src/front/utils/apiBase.test.js
```

Result: PASS.

### Review (roborev)

Cross-model reviewers (`claude-code`, `gemini`) were unavailable in this environment (claude usage limit; gemini missing API key).
Ran `roborev review` with `--agent codex` and addressed findings iteratively.

### UBS

`ubs --staged` is currently blocked by module checksum mismatch for `python` (environment issue).

