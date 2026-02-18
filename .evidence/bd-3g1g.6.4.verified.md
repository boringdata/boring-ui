# bd-3g1g.6.4 Evidence: Boundary Policy Enforcement (workspace-core + pty-service)

**

## Summary

Implements deny-by-default delegated policy enforcement for owner services when a delegated claim envelope is present:

- Adds `X-Scope-Context` parsing + validation and minimal enforcement helper (`src/back/boring_ui/api/policy.py`).
- Wires enforcement into:
  - `workspace-core` file endpoints (`/api/v1/files/*`)
  - `workspace-core` git endpoints (`/api/v1/git/*`)
  - `pty-service` HTTP lifecycle endpoints (`/api/v1/pty/sessions*`)
  - `pty-service` WS endpoint (`/ws/pty`)
- Enforcement is **gated on header presence**: if `X-Scope-Context` is absent, existing local UI/dev flows are unchanged.
- Deny outcomes:
  - HTTP: canonical error envelope with `code` in `{invalid_scope_context, capability_denied, session_mismatch}`
  - WS: close code `4004` with stable reason prefix `policy:<code>`

## Commits

- `96beaeb` initial policy helper + wiring + denial tests
- `671b8a9` review fixes (exception string, lifecycle typing, add delegated happy-path test)
- `499bb0e` fix WS header empty-value handling (empty header is invalid, not bypass)

## Verification

### Unit tests (policy enforcement)

```bash
pytest -q tests/unit/test_bd_3g1g_6_4_boundary_policy_enforcement.py
```

Result: PASS.

### Regression tests (existing route/ownership contracts)

```bash
pytest -q tests/unit/test_bd_3g1g_5_4_workspace_core_pty_contracts.py
pytest -q tests/unit/test_file_routes.py tests/unit/test_git_routes.py tests/unit/test_bd_3g1g_5_2_pty_ownership.py
```

Result: PASS.

### Review (roborev)

```bash
roborev review HEAD --agent claude
roborev show 438
```

Result: PASS (no issues found).

### UBS (staged)

```bash
ubs --staged
```

Result: BLOCKED (UBS module checksum mismatch for `python` in this environment; also reproduced via `ubs doctor --fix`).
