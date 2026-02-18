# bd-3g1g Migration Closeout Summary (Phase 5)

This document is the final maintainer-oriented summary for the `bd-3g1g` epic:
Service Split + Control-Plane Decoupling + Legacy Cutover.

Goal: make the post-migration topology, boundaries, and verification workflow
understandable without re-reading historical threads.

## What Changed (High Level)

1. **Control-plane decoupling**
   - The backend acts as a control plane (capabilities, auth/menu flows, routing decisions).
   - Workspace operations are exercised via explicit service boundaries rather than implicit legacy fallbacks.

2. **Service split**
   - Workspace/PTY/chat interactions are structured around service-specific call paths and runtime identities.
   - Delegated actions can be performed by multiple agent services with a consistent policy model.

3. **Legacy cutover**
   - Remaining fallback logic for deprecated/legacy routes was removed.
   - Canonical transport expectations are enforced by tests.

## Final Topology (Mental Model)

### Frontend

- React frontend (Dockview-based) is under `src/front/`.
- The UI talks to the control plane using canonical endpoints and follows canonical navigation paths.

Key areas:
- Transport + base URLs: `src/front/utils/apiBase.js`, `src/front/utils/transport.js`
- Route utilities and canonical paths: `src/front/utils/routes*`, `src/front/utils/controlPlane*`
- User menu flows (switch/create/logout): `src/front/App.jsx`

### Backend

- FastAPI backend lives under `src/back/boring_ui/`.
- The runtime composes modular routers and exposes canonical control-plane endpoints.

Key areas:
- App composition: `src/back/boring_ui/api/app.py`
- Capability surface: `src/back/boring_ui/api/capabilities.py`
- Policy enforcement (delegation context header): `src/back/boring_ui/api/policy.py`
- Module routers: `src/back/boring_ui/api/modules/*`

### Delegated Execution + Policy

Delegated actions are represented with an explicit scope context header:

- `X-Scope-Context`: conveys delegated actor context (service identity, workspace scope, etc.).
- Enforcement is deny-by-default when the header is present; legacy behavior is unaffected when absent.
- WebSocket denies use close code `4004` with a `policy:<code>` reason prefix.

## Canonical Routes (Source Of Truth)

Canonical route documentation and callsite inventory were produced during the epic:

- `docs/ROUTE_CALLSITE_INVENTORY_bd-3g1g.1.1.md`
- `docs/bd-3g1g.2.4-contract-pack-v1.md`

Legacy route families should not be used by active code paths after this cutover.

## How To Verify (Re-run The Matrix)

The verification matrix runner is the primary re-verification entrypoint:

```bash
python3 scripts/bd_3g1g_verify.py --help
python3 scripts/bd_3g1g_verify.py --skip-ubs
```

Typical targeted runs:

```bash
# E2E only
python3 scripts/bd_3g1g_verify.py --skip-ubs --only playwright_e2e

# Static + unit + integration only
python3 scripts/bd_3g1g_verify.py --skip-ubs --skip-vitest --skip-e2e --only static_forbidden_routes,pytest_unit,pytest_integration
```

Notes:
- UBS is best-effort in this environment; matrix runs may use `--skip-ubs`.
- Playwright stability is improved by running with a single worker and owned webServer lifecycle
  (the matrix runner sets `PW_E2E_WORKERS=1` and `PW_E2E_REUSE_SERVER=0` for e2e).

## Evidence Pointers

Phase 5 evidence lives under `.evidence/` and `.verify/`:

- `bd-3g1g.7.1`: legacy fallback removal evidence
- `bd-3g1g.7.2`: full verification matrix evidence (unit/integration/vitest/e2e logs)
- `bd-2fxd`, `bd-mc55`, `bd-3iw8`: Playwright/matrix stabilization blockers

## Ownership Model (Who Owns What Now)

Operationally:

- Control plane: `src/back/boring_ui/api/*` and frontend control-plane flows.
- Service boundaries + delegated policy: `src/back/boring_ui/api/policy.py` and per-module routers.
- Test/verification: `tests/`, `src/front/__tests__/`, and `scripts/bd_3g1g_verify.py`.

## Follow-Ups / Known Friction

1. **UBS module checksum mismatches**
   - UBS python/rust modules can fail to download/verify due to checksum mismatches.
   - Matrix runs treat UBS as best-effort; if UBS is required in CI, investigate module cache and checksum source.

2. **Prompt-based UX in user menu**
   - Workspace switch/create currently uses `window.prompt` flows. Tests may stub prompt for stability.
   - Consider replacing prompts with a first-class dialog UX if product direction allows.

