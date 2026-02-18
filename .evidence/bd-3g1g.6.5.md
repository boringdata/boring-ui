# bd-3g1g.6.5 Cross-Agent Delegated Policy Integration

*2026-02-18T10:24:42Z by Showboat 0.5.0*

Adds cross-agent integration coverage ensuring delegated boundary policy enforcement behaves consistently across agent-normal/agent-companion/agent-pi for owner services (workspace-core + pty-service) when X-Scope-Context is present.

Correction: enforcement is exercised when the X-Scope-Context header is present; direct UI calls omit the header and remain unchanged.

```bash
pytest -qq tests/integration/test_bd_3g1g_6_5_cross_agent_delegation.py
```

```output
............                                                             [100%]
```

```bash
pytest -qq tests/unit/test_bd_3g1g_6_4_boundary_policy_enforcement.py
```

```output
.......                                                                  [100%]
```

```bash
rg -n 'X-Scope-Context' -S src/back/boring_ui/api/policy.py tests/integration/test_bd_3g1g_6_5_cross_agent_delegation.py | LC_ALL=C sort
```

```output
src/back/boring_ui/api/policy.py:22:SCOPE_CONTEXT_HEADER = "X-Scope-Context"
src/back/boring_ui/api/policy.py:8:delegation envelope header (`X-Scope-Context`). Direct UI calls (no header) are
tests/integration/test_bd_3g1g_6_5_cross_agent_delegation.py:44:    return {"X-Scope-Context": json.dumps(payload)}
tests/integration/test_bd_3g1g_6_5_cross_agent_delegation.py:6:We treat the `X-Scope-Context` header as the cross-agent contract boundary:
```
