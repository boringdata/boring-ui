# Artifact Cleanup Policy (bd-1adh.9.3)

## Objective

Deterministic keep/delete criteria for bd-1adh artifacts. No subjective decisions — every artifact has a clear disposition.

## Keep (Permanent)

These artifacts are part of the codebase and must not be deleted:

| Category | Location | Rationale |
|----------|----------|-----------|
| Source modules | `src/back/boring_ui/api/local_api/` | Production code |
| Source modules | `src/back/boring_ui/api/target_resolver.py` | Production code |
| Source modules | `src/back/boring_ui/api/transport.py` | Production code |
| Source modules | `src/back/boring_ui/api/error_codes.py` | Production code |
| Source modules | `src/back/boring_ui/api/hosted_client.py` | Production code |
| Source modules | `src/back/boring_ui/api/sandbox_url_validator.py` | Production code |
| Source modules | `src/back/boring_ui/api/sandbox_auth.py` | Canonical capability auth module |
| Unit tests | `tests/unit/test_target_resolver.py` | Regression tests |
| Unit tests | `tests/unit/test_transport.py` | Regression tests |
| Unit tests | `tests/unit/test_error_codes.py` | Regression tests |
| Unit tests | `tests/unit/test_hosted_client.py` | Regression tests |
| Unit tests | `tests/unit/test_sandbox_url_validator.py` | Regression tests |
| Unit tests | `tests/unit/test_capability_decorator.py` | Regression tests for `sandbox_auth` decorator exports |
| Integration tests | `tests/unit/test_local_capability_middleware.py` | Regression tests |
| Security tests | `tests/unit/test_security_boundary.py` | Security regression |
| Matrix tests | `tests/unit/test_verification_matrix.py` | Cross-cutting verification |
| Parity tests | `tests/unit/test_local_parity_mode.py` | Mode regression |
| Config changes | `src/back/boring_ui/api/config.py` | Production config |
| App wiring | `src/back/boring_ui/api/app.py` | Production app factory |

## Keep (Reference)

These docs are reference material with ongoing value:

| Document | Location | Rationale |
|----------|----------|-----------|
| ADR: Local Mode Strategy | `docs/ADR_LOCAL_MODE_STRATEGY.md` | Architecture decision record |
| Runtime vs Test CLI | `docs/RUNTIME_VS_TEST_CLI.md` | Provider assumptions |
| Migration Choreography | `docs/MIGRATION_CHOREOGRAPHY.md` | Rollback reference |
| Verification Report | `docs/VERIFICATION_REPORT.md` | Proof of correctness |

## Delete (After Merge)

These artifacts can be deleted after bd-1adh is merged to main:

| Artifact | Location | When to Delete |
|----------|----------|----------------|
| Beads entries | `.beads/issues.jsonl` (bd-1adh.* entries) | After merge to main |
| Planning docs | `docs/TWO_MODULE_API_LOCAL_API_PLAN.md` | After merge (superseded by ADR) |

## Review Trigger

Re-evaluate this policy when:
- bd-1adh is merged to main
- A new architecture direction supersedes two-module split
- Test files grow beyond 50 tests per file (consider splitting)
