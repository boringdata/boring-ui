# Two-Module Refactor Plan (`api` + `local-api`)

## 1. Objective

Reorganize backend architecture into exactly two conceptual modules:

1. `api` (control plane)
- User auth + permission enforcement
- Sandbox management (provider lifecycle)
- Frontend-facing proxy routes
- Capability/token issuance and service registry

2. `local-api` (workspace plane)
- File/Git/Exec endpoints bound to one workspace
- Deployed in local runs and in sprite sandbox runs
- Private service, not browser-facing

The primary invariant is:

- Hosted/Sprites: `front -> api (proxy) -> local-api`
- Local mode: `front -> api`, with `local-api` mounted in-process
- Sprites transport for hosted mode uses Sprites Proxy WebSocket API directly from backend (no browser direct calls, no `sprite proxy` CLI dependency in runtime path)


## 2. Current State Snapshot

Snapshot commit: `7fa41f9`

Current implementation already contains most primitives:

- Control plane app: `src/back/boring_ui/api/app.py`
- Private workspace API app: `src/back/boring_ui/api/internal_app.py`
- Workspace endpoints: `src/back/boring_ui/api/modules/sandbox/internal_*.py`
- Hosted proxy: `src/back/boring_ui/api/modules/sandbox/hosted_proxy.py` + `hosted_compat.py`
- Sandbox provider management: `src/back/boring_ui/api/modules/sandbox/manager.py` + providers

Main gap is organization and explicit contracts, not fundamental capability.


## 3. Target Module Layout

## 3.1 Control Plane (`api`)

Keep under `src/back/boring_ui/api/`:

- `app.py` (control plane app factory)
- `auth.py`, `auth_middleware.py`, `service_auth.py`, `sandbox_auth.py`
- `capabilities.py`, `capability_tokens.py`
- `modules/sandbox/manager.py`, `provider.py`, `providers/*`
- `modules/sandbox/hosted_client.py`
- `modules/sandbox/hosted_proxy.py`, `hosted_compat.py`
- `modules/sandbox/router.py` (lifecycle/status/log endpoints)

Role: all frontend-facing control and orchestration.

## 3.2 Workspace Plane (`local-api`)

Create package `src/back/boring_ui/api/local_api/`:

- `app.py` (`create_local_api_app`) to replace current `internal_app` role
- `router.py` (`create_local_api_router`) as composed workspace API
- `files.py` (from current `internal_files.py`)
- `git.py` (from current `internal_git.py`)
- `exec.py` (from current `internal_exec.py`)
- No local policy module. Reuse shared policy from `src/back/boring_ui/api/modules/sandbox/policy.py`
  so both proxy-side checks and local-api enforcement share one policy source.

Runtime role:

- One deployment unit that serves workspace endpoints to control plane only.
- In hosted/sprites, control plane targets this private service URL.
- In local mode, same handlers are mounted in-process behind control-plane routes.
- `local-api` has no direct browser contract.


## 4. API/Interface Contracts

## 4.1 Stable external HTTP surfaces (no breaking change)

Keep public paths unchanged:

- Frontend contract:
  - `/api/tree`, `/api/file`, `/api/search`
  - `/api/git/status`, `/api/git/diff`, `/api/git/show`
- Hosted proxy paths:
  - `/api/v1/sandbox/proxy/*`

## 4.2 Internal local-api contract

Keep existing internal contract (current behavior) stable:

- `/internal/health`, `/internal/info`
- `/internal/v1/files/*`
- `/internal/v1/git/*`
- `/internal/v1/exec/*`

Service discovery for control plane -> local-api:

- Hosted non-sprites control plane discovers target local-api via `INTERNAL_SANDBOX_URL`.
- Hosted sprites control plane resolves the target sprite and local-api port from hardcoded config for now.
- In local mode (single process), no discovery call is required because local-api is mounted in-process.
- Frontend never receives `INTERNAL_SANDBOX_URL` and never calls `local-api` directly.

Hardcoded now (move-fast phase):

- `SPRITES_TARGET_SPRITE` (single sprite name used by hosted control plane).
- `SPRITES_LOCAL_API_PORT` (port where local-api listens inside sprite).
- Later replacement: DB-backed `user/workspace -> sprite` resolution.

## 4.3 Sprites transport contract (precise)

For `SANDBOX_PROVIDER=sprites`, backend-to-sandbox transport is:

1. Open WebSocket:
- `wss://api.sprites.dev/v1/sprites/{sprite-name}/proxy`
- Reference: https://sprites.dev/api/sprites/proxy

2. Authenticate backend call:
- Header `Authorization: Bearer ${SPRITES_TOKEN}` (server-side only, never sent to browser).

3. Send initial JSON handshake frame:
- `{\"host\":\"localhost\",\"port\":<SPRITES_LOCAL_API_PORT>}`

4. After successful handshake, treat socket as raw TCP relay:
- Backend writes raw HTTP/1.1 request bytes for `local-api` path (`/internal/v1/*`).
- Backend reads raw HTTP response bytes and parses status/headers/body.

5. Error handling requirements:
- Handshake failure => map to `502` with provider-specific detail in server logs.
- Relay timeout => map to `504`.
- Non-2xx local-api response => preserve status/body mapping from parsed HTTP response.

## 4.4 Python module contracts

New exports:

- `boring_ui.api.local_api.create_local_api_app`
- `boring_ui.api.local_api.create_local_api_router`

Breaking Python import changes (intentional hard cut):

- Remove reliance on `boring_ui.api.internal_app.create_internal_app`.
- Remove reliance on `boring_ui.api.modules.sandbox.internal_api.create_internal_sandbox_router`.
- All call sites import directly from `boring_ui.api.local_api`.


## 5. Detailed Refactor Workstreams

## 5.1 WS-A: Create `local_api` package

1. Add folder `src/back/boring_ui/api/local_api/`.
2. Add `__init__.py` exporting app/router factories.
3. Move/copy current internal handlers:
- `modules/sandbox/internal_files.py` -> `local_api/files.py`
- `modules/sandbox/internal_git.py` -> `local_api/git.py`
- `modules/sandbox/internal_exec.py` -> `local_api/exec.py`
4. Add `local_api/router.py` to compose these into a single router.
5. Add `local_api/app.py` to build FastAPI app with:
- workspace binding
- no browser CORS surface by default (private service)
- optional service-to-service verification hooks only (no end-user auth logic)
- local-api listener port configurable and documented for sprites runtime (`SPRITES_LOCAL_API_PORT`)

## 5.2 WS-B: Rewire control plane to new package

1. Update all call sites to import directly from `local_api.app` and `local_api.router`.
2. Remove `api/internal_app.py`.
3. Remove `modules/sandbox/internal_api.py`.
4. Add transport abstraction in hosted client:
- `HTTPInternalTransport` for non-sprites (`INTERNAL_SANDBOX_URL` via `httpx`).
- `SpritesProxyTransport` for sprites (direct `wss://.../proxy` relay).
5. Wire transport selection off provider/config in `app.py`.
6. Ensure local mode mounts `local_api.router` directly and does not depend on removed modules.
7. Ensure capabilities payload in hosted mode exposes only control-plane routes, not direct sandbox/local-api URLs.
8. Ensure hosted sprites mode does not depend on `sprite proxy` CLI tunnel.

## 5.3 WS-C: Enforce two-module ownership in docs

1. Update `docs/DEPLOYMENT_MATRIX.md` with explicit ownership table:
- control-plane responsibility vs local-api responsibility.
2. Add section for local vs hosted/sprites traffic flow.
3. Add env var ownership matrix:
- control plane env
- local-api env
  - include `SPRITES_TARGET_SPRITE` and `SPRITES_LOCAL_API_PORT` with move-fast hardcoded defaults
4. Document explicit security rule: no direct browser-to-sandbox or browser-to-local-api calls.
5. Document that custom in-sandbox JWT/cookie reverse-proxy auth is out of scope for this phase.
6. Add source links section with Sprites API references (proxy endpoint as required, additional endpoints as used).

## 5.4 WS-Preview: Preview gateway strategy in `api`

1. Add a dedicated preview gateway section to docs and architecture notes.
2. Keep preview routing separate from `local-api` file/git/exec API.
3. Define provider adapter contract in `api`:
- resolve preview target (path/subdomain -> internal port/service)
- apply control-plane auth/session checks
- proxy response/stream
4. Do not assume one fixed public port model in core architecture; map provider constraints in adapter layer.
5. No custom in-sprite JWT proxy for v1.

## 5.5 WS-D: Cleanup track (repo mess)

Create a deterministic cleanup list:

A) Artifacts likely temporary:
- `.tmp_chat_probe.mjs`
- `.tmp_pw_verify.mjs`
- ad-hoc proof screenshots in `docs/*.png` if not part of release docs

B) Build/cache artifacts that should not be tracked:
- `__pycache__` files (if tracked by mistake)

C) Ambiguous docs/proof files:
- `rodney-proof-file.txt`
- `docs/HOSTED_UI_SHOWBOAT_RODNEY_PROOF.md`

Cleanup policy:

1. Keep only files referenced by docs index/README.
2. Remove unreferenced artifacts.
3. Add/verify `.gitignore` entries to prevent reintroduction.

## 5.6 Workstream order and dependencies

Execution order (required):

1. WS-A (`local_api` package) - foundational module split.
2. WS-B (rewire + delete old modules) - depends on WS-A completion.
3. WS-C (docs ownership + env matrix updates) - depends on WS-B final paths.
4. WS-Preview (preview gateway strategy docs/contracts) - depends on WS-C.
5. WS-D (cleanup) - may run in parallel after WS-B starts, but must finish before final commit.


## 6. Testing Plan

## 6.1 Local automated tests (required)

Run at minimum:

1. `pytest src/back/boring_ui/api/test_dualmode_integration_matrix.py -q`
2. `pytest src/back/boring_ui/api/test_integration_auth_capability.py -q`
3. `pytest src/back/boring_ui/api/test_sandbox_auth.py -q`
4. `pytest tests/integration/test_direct_connect_auth.py -q`
5. `pytest tests/integration/test_sprites_integration.py -q`

Pass criteria:

- No regression in hosted/local router composition
- Hosted mode never exposes direct local-api URLs to browser clients
- local-api remains private-only in hosted/sprites topology
- Hosted sprites path uses direct backend WebSocket proxy transport (no CLI tunnel)
- Sprites provider integration tests pass (stub-based suite)

## 6.2 Live sprite validation (required)

Using installed CLI (`sprite`):

1. Confirm selected sprite:
- `sprite use <sprite-name>`
- `sprite url`

2. Deploy/refresh local-api runtime in sprite workspace:
- run command via `sprite exec` to pull latest code and restart service process.

3. Validate local-api health inside sprite:
- `sprite exec curl -s http://127.0.0.1:<port>/internal/health`

4. Validate control plane to sprite path:
- From host, call control plane endpoints (`/api/tree`, `/api/git/status`) and verify successful proxy to sprite-backed local-api.
- Confirm requests succeed without running `sprite proxy` locally.

5. Boundary validation:
- Confirm browser-facing capabilities/config endpoints do not publish direct local-api URL.
- Confirm direct browser-style access path to local-api is unavailable in deployed topology.
- Confirm control-plane proxied requests succeed end-to-end.

## 6.3 Manual smoke (frontend)

1. Load UI.
2. Verify file tree displays sprite workspace content.
3. Edit/save file and verify it exists in sprite workspace via `sprite exec`.
4. Run git status from UI and from `sprite exec git status`; results must align.


## 7. Rollout Strategy

## 7.1 Phase 1 (hard cut)

- Introduce `local_api` package and move implementation immediately.
- Update all imports in one change set.
- Remove legacy modules in the same commit series (no wrappers).
- Keep endpoint behavior stable for frontend routes.

## 7.2 Phase 2 (stabilization)

- Run full test matrix.
- Validate live sprite deployment path.
- Fix regressions before adding new features.


## 8. Risk Register

1. Import-cycle regressions after moving internal handlers.
Mitigation: keep dependencies acyclic and run full test matrix.

2. Proxy breakage from path mismatch.
Mitigation: keep `/internal/v1/*` contract unchanged.

3. Sprite deployment drift (service not restarted, wrong port).
Mitigation: scripted `sprite exec` restart + explicit health checks.

4. Auth misconfiguration between control plane and local-api.
Mitigation: enforce private-network-only local-api access and verify boundary tests in live validation.

5. Sprites proxy protocol/framing errors in backend relay client.
Mitigation: strict handshake validation, HTTP parser tests for chunked + non-chunked responses, and timeout/error mapping tests.


## 9. Acceptance Criteria

Refactor accepted when all are true:

1. `local_api` package exists and is the canonical workspace endpoint implementation.
2. `api` remains canonical control plane (proxy + sandbox mgmt + user/auth).
3. Public HTTP routes are unchanged.
4. Local test matrix passes.
5. Live sprite smoke passes for read/write/git with private local-api boundary preserved.
6. Cleanup track removes agreed temporary artifacts and prevents recurrence.
7. Hosted sprites path works with direct WebSocket relay to Sprites Proxy API (no CLI forwarding process).


## 10. Execution Checklist

1. Create `local_api` package and move internal handlers.
2. Rewire imports across app/proxy modules to `local_api`.
3. Delete `api/internal_app.py` and `modules/sandbox/internal_api.py`.
4. Update docs (`DEPLOYMENT_MATRIX.md` + module ownership notes).
5. Add preview-gateway contract notes in `api` docs.
6. Run local tests.
7. Deploy to running sprite and execute live smoke.
8. Execute cleanup track and re-run sanity tests.
9. Commit in logical slices:
- refactor package split
- docs update
- cleanup artifacts


## 11. Out of Scope (this cycle)

1. New auth protocol design (Sprites already provides outer boundary).
2. Public endpoint renames.
3. Frontend architecture changes beyond verifying existing routes.
4. Provider feature expansion (modal, new provider types).
5. In-sandbox custom JWT/cookie reverse proxy for local-api access.

## 12. Source Links

- Sprites proxy API (authoritative for backend-to-sprite relay):
  https://sprites.dev/api/sprites/proxy
- Sprites API index (discover other endpoints used by provider):
  https://sprites.dev/api
