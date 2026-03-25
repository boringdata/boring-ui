# Improvement Roadmap

## Status

Revised execution plan based on the March 25, 2026 repo review plus current worktree verification.

This plan assumes the recent Neon auth fixes are already landed:

- truthful verification-email messaging
- explicit public-origin support for hosted auth callbacks

Those fixes reduced immediate auth correctness risk. The remaining work should focus on deploy confidence, crash isolation, and shrinking the largest frontend/backend hotspots in the order that minimizes regression risk.

Phase 0 is complete in the current worktree as of 2026-03-25: `.stylelintrc.json` exists and `npm run lint` now passes cleanly across all five tracked subcommands. The remaining tooling gap is enforcement, not correctness: this checkout still has no active `.git/hooks/pre-commit`, so `npm run lint` is authoritative but not automatically run by Git in this clone.

Related beads:

- `bd-znpbo` Tooling: restore tracked lint/style gate and style-guideline enforcement
- `bd-3bs4j` Smoke: cover `AUTH_EMAIL_PROVIDER=none` and `BORING_UI_PUBLIC_ORIGIN` auth flows
- `bd-3mdry` Frontend: add `PanelErrorBoundary` and lazy panel wrapper tests
- `bd-om29` Frontend: break `App.jsx` workspace shell into focused state/hooks modules
- `bd-il78w` Auth UI: move server-rendered auth page out of embedded Python string templates
- `bd-b2fof` Backend: decompose Neon/stream auth flows into smaller contract-tested units
- `bd-rm17p` Backend: split stream bridge/runtime paths into focused modules

---

## Executive Summary

The highest-leverage remaining improvements are:

1. add deploy-shaped smoke coverage for hosted auth edge cases
2. add crash-isolation tests for `PanelErrorBoundary` and lazy panel wrappers
3. extract embedded auth HTML templates before deeper backend refactors
4. continue shrinking `src/front/App.jsx` by extracting the largest remaining stateful seams
5. split `stream_bridge.py` starting with the zero-coupling permission persistence and argument builder blocks

The order matters. The repo now has a working lint gate in the current worktree. The next priority is protecting behavior with tests, then reducing file size where the safest mechanical extractions exist.

---

## Goals

- reduce regression risk in hosted auth flows
- protect crash isolation for lazy-loaded panels
- reduce maintenance cost of oversized frontend/backend files
- make deploy-time failures easier to catch before production
- improve code ownership boundaries without broad rewrites

## Non-Goals

- no rewrite of the full frontend shell in one pass
- no new auth provider or major auth architecture change
- no broad UI redesign
- no large platform migration unrelated to the identified hotspots

---

## Current Constraints

### Frontend

- `src/front/App.jsx` is still 4452 lines in the current worktree, even after recent utility/component extraction work
- the remaining complexity is concentrated in stateful blocks: sidebar state, identity/workspace boot, approvals, layout restoration, and panel positioning
- `PanelErrorBoundary` and the `withSuspense` wrapper exist but currently have no direct test coverage

### Backend

- `src/back/boring_ui/api/modules/control_plane/auth_router_neon.py` is 2286 lines
- the embedded auth templates start at lines 851 and 1526; the login template alone is 673 lines, and the callback template adds another 107 lines before the render helpers
- `src/back/boring_ui/api/stream_bridge.py` is 1513 lines and still mixes permission persistence, process argument construction, websocket/session orchestration, and message dispatch

### Tooling

- `.stylelintrc.json` is now present and `npm run lint` passes in the current worktree
- there is no active `.git/hooks/pre-commit` in this checkout; only stock sample hooks are present
- smoke coverage still does not protect the new `AUTH_EMAIL_PROVIDER=none` and `BORING_UI_PUBLIC_ORIGIN` paths

---

## Execution Order

### Phase 0: Restore Reliable Quality Gates

Status:

- **Complete in the current worktree** (2026-03-25)

Tracked bead:

- `bd-znpbo`

Completed work:

- added `.stylelintrc.json` with Tailwind-compatible allowances for the current CSS stack
- fixed a real CSS issue in `src/front/components/chat/styles.css` by removing a dead duplicate `width: 100%` declaration
- removed unused imports from `src/front/components/chat/ClaudeStreamChat.jsx`
- removed the unused `screen` import from `src/front/__tests__/components/toolRenderers.test.jsx`
- fixed the flaky `FileTree` retry test in `src/front/__tests__/components/FileTree.test.tsx` by aligning timeouts with the real `refetchInterval`
- verified `npm run lint` passes cleanly across all tracked subcommands: `eslint`, `lint:css`, `lint:tokens`, `lint:shadcn`, `lint:phase1`

Remaining gap:

- no active pre-commit hook runs `npm run lint` automatically in this checkout
- keep `bd-znpbo` open until the lint/style work is fully landed and contributor enforcement is explicitly decided
- preferred resolution: either add a tracked hook mechanism or document the expected contributor/CI enforcement path clearly

Why this matters:

- the repo now has a trustworthy tracked lint command; the remaining question is how strictly to enforce it for every contributor

---

### Phase 1: Add Deploy And Crash-Isolation Test Coverage

Target:

- protect the recently fixed hosted auth behaviors with smoke coverage
- protect the new lazy-panel crash isolation behavior with targeted frontend tests

Tracked beads:

- `bd-3bs4j`
- `bd-3mdry`

Files likely involved:

- `tests/smoke/smoke_neon_auth.py`
- `tests/smoke/smoke_capabilities.py`
- `tests/smoke/smoke_lib/auth.py`
- `tests/smoke/smoke_lib/resend.py`
- `src/front/components/PanelErrorBoundary.jsx`
- `src/front/registry/panes.jsx`
- new frontend unit tests under `src/front/__tests__/`

Work:

- add a smoke scenario for `AUTH_EMAIL_PROVIDER=none`
- assert the app does not falsely promise verification email delivery when disabled
- assert capabilities expose `auth.verificationEmailEnabled`
- add a smoke scenario for `BORING_UI_PUBLIC_ORIGIN`
- assert delivered verification callbacks point back to the configured public app origin
- add a unit test proving `PanelErrorBoundary` renders recovery UI when a child throws
- add a unit test proving `withSuspense` wraps lazy panels with both `Suspense` and `PanelErrorBoundary`

Done when:

- auth smoke tests fail on the old behavior and pass on the new one
- a throwing lazy panel renders fallback UI instead of taking down the panel tree
- the lazy panel registration path has explicit regression coverage

Why now:

- this is the fastest way to lock in two recent behavioral improvements before deeper code motion starts

---

### Phase 2: Split the Frontend Workspace Shell

Target:

- reduce `src/front/App.jsx` to a composition layer by extracting the largest remaining stateful seams

Status:

- **Partially complete** (2026-03-25)

Tracked bead:

- `bd-om29`

Completed work:

- extracted shared utilities into `src/front/utils/debounce.js`, `src/front/utils/dockHelpers.js`, `src/front/utils/frontendState.js`, and `src/front/utils/panelConfig.js`
- extracted shared dock tab rendering into `src/front/components/DockTab.jsx`
- added `src/front/components/PanelErrorBoundary.jsx` and wrapped lazy-loaded panels in `src/front/registry/panes.jsx`
- deduplicated `UNKNOWN_CAPABILITIES` into `src/front/hooks/useCapabilities.js`
- reduced `src/front/App.jsx` from 4823 lines at `HEAD` to 4452 lines in the current worktree

Remaining work should target the stateful blocks that still dominate the file.

Recommended extraction sequence:

1. `useSidebarLayout` — sidebar collapse/expand state machine, section collapse toggling, panel constraints, and persisted sidebar sizing
2. `useCenterPanelPositioning` — center-group resolution, fallback anchors, and file-open placement rules
3. `useApprovalSync` — approval polling, review panel lifecycle, decision submission, and stale-panel cleanup
4. `useFrontendCommandPoller` — server command polling and UI dispatch
5. `useUserIdentity` — identity resolution, workspace list loading, auth status, and storage-prefix scoping
6. `useDataProviderScope` — LightningFS namespace, query cache scoping, and data-provider resolution

Suggested target shape:

```jsx
export default function App() {
  const config = useConfig()
  const identity = useUserIdentity(config)
  const sidebar = useSidebarLayout(config)
  const center = useCenterPanelPositioning(dockApi)
  const approvals = useApprovalSync(capabilities)
  const commands = useFrontendCommandPoller(dockApi)
  const dataProvider = useDataProviderScope(config, identity)

  return (
    <WorkspaceShell
      identity={identity}
      sidebar={sidebar}
      center={center}
      approvals={approvals}
      commands={commands}
      dataProvider={dataProvider}
    />
  )
}
```

Work rules:

- do not rewrite behavior while extracting ownership boundaries
- land this in small commits, not one broad refactor
- preserve the current auth/capabilities contract while moving code
- extract the stateful seams above before inventing new abstraction layers

Done when:

- `src/front/App.jsx` is below 2500 lines
- each extracted hook has clear inputs/outputs and focused tests
- auth, workspace boot, and layout behavior remain unchanged

Why this is high leverage:

- the remaining complexity is no longer “miscellaneous utility code”; it is concentrated in a few large stateful blocks with clearer seams than the original hook list suggested

---

### Phase 3: Extract Auth HTML Templates, Then Decompose Backend

Target:

- move the embedded auth HTML/CSS/JS out of `auth_router_neon.py`
- then decompose the remaining Python auth logic into smaller contract-tested units

Tracked beads:

- `bd-il78w`
- `bd-b2fof`

Files likely involved:

- `src/back/boring_ui/api/modules/control_plane/auth_router_neon.py`
- new template files under `src/back/boring_ui/api/modules/control_plane/templates/`
- new support modules under `src/back/boring_ui/api/modules/control_plane/`

Step 1: HTML extraction (low-risk, mechanical)

- move `_NEON_LOGIN_HTML_TEMPLATE` out of Python into `templates/login.html`
- move `_NEON_CALLBACK_HTML` out of Python into `templates/callback.html`
- keep Python-side rendering thin: load file contents, replace the existing `/*AUTH_CONFIG_JSON*/` placeholder, and return HTML
- add a render test that proves the generated HTML still injects the same auth config payload

This step alone removes the largest non-Python block from the file and makes the remaining logic much easier to review.

Step 2: Extract well-isolated helpers (medium-risk)

- `auth_urls.py` — `_public_origin()`, `_build_callback_url()`, `_normalize_origin()`, `_safe_redirect_path()`
- `auth_crypto.py` — `_pending_login_fernet()`, `_encode_pending_login()`, `_decode_pending_login()`
- `neon_client.py` — HTTP calls to Neon auth endpoints for sign-up, sign-in, token exchange, verification email, and password reset

Suggested `neon_client.py` interface:

```python
class NeonAuthClient:
    def __init__(self, base_url: str, http_client: httpx.AsyncClient): ...
    async def sign_up_email(self, *, email: str, password: str, name: str) -> dict: ...
    async def sign_in_email(self, *, email: str, password: str) -> dict: ...
    async def fetch_jwt(self, *, cookies: dict) -> str: ...
    async def send_verification_email(self, *, email: str, callback_url: str) -> dict: ...
    async def request_password_reset(self, *, email: str, redirect_url: str) -> dict: ...
    async def reset_password(self, *, new_password: str, token: str) -> dict: ...
```

Step 3: Thin the router (higher-risk, last)

- keep `create_auth_session_router_neon()` as a wiring layer
- reduce each route handler to a thin request/response coordinator that delegates to extracted helpers or client methods

Done when:

- auth HTML no longer lives in Python string blobs
- `auth_router_neon.py` is below 800 lines
- URL helpers, crypto helpers, and the Neon client have focused tests
- route handlers read as composition rather than implementation details

Why this order is better:

- the HTML extraction is mechanical and low-risk
- removing 700+ lines of embedded template content first makes every later backend refactor cheaper and easier to review

---

### Phase 4: Decompose Stream Runtime Paths

Target:

- split `src/back/boring_ui/api/stream_bridge.py` by starting with the lowest-coupling blocks first

Tracked bead:

- `bd-rm17p`

Files likely involved:

- `src/back/boring_ui/api/stream_bridge.py`
- new stream support modules under `src/back/boring_ui/api/`

Recommended extraction sequence:

1. `permission_settings.py` — extract `_persist_permission_suggestions()` and its helper functions from the block that starts at line 43; this is pure settings file I/O and has no websocket/session coupling
2. `stream_args.py` — extract `build_stream_args()` from the block that starts at line 693; argument construction is pure logic and easy to test independently
3. split `handle_stream_websocket()` from the block that starts at line 843 into focused message handlers for user messages, control messages, control responses, and restart flows
4. split `StreamSession.start_read_loop()` from the block that starts at line 489 into smaller stdout/stderr and message-dispatch helpers

Done when:

- `stream_bridge.py` is below 800 lines
- permission persistence and argument construction have independent tests
- websocket/session orchestration is no longer interleaved with every helper concern

Why later:

- auth still has more immediate correctness/deploy impact than stream cleanup, but the first two stream extractions are low-risk and should lead the work once this phase starts

---

## Success Criteria

The roadmap is succeeding if the repo reaches this state:

- `npm run lint` remains a real tracked gate and the contributor enforcement path is explicit
- hosted-auth smoke tests protect the new deploy-sensitive paths
- `PanelErrorBoundary` and lazy panel wrappers have direct regression coverage
- `src/front/App.jsx` is below 2500 lines and its extracted hooks are independently testable
- `src/back/boring_ui/api/modules/control_plane/auth_router_neon.py` is below 800 lines with HTML in separate template files
- `src/back/boring_ui/api/stream_bridge.py` is below 800 lines with permission persistence and argument building extracted
- hosted auth and stream logic are broken into smaller contract-tested modules

---

## Risks And Mitigations

### Risk: HTML template extraction changes rendering behavior

Mitigation:

- keep the existing `/*AUTH_CONFIG_JSON*/` placeholder contract
- use simple file loading plus `.replace()` rather than introducing a full template engine during the first extraction
- add a render test that compares known config injection output against expected HTML

### Risk: frontend refactor creates subtle boot regressions

Mitigation:

- extract one stateful seam at a time
- keep tests green after each extraction
- avoid behavioral changes during mechanical moves

### Risk: backend auth decomposition expands scope

Mitigation:

- split by concrete flows and helper boundaries, not abstract architecture
- extract HTML and pure helpers first, then thin the router last

### Risk: smoke coverage becomes too environment-specific

Mitigation:

- keep assertions focused on contract behavior
- avoid coupling tests to one deploy provider beyond what the app contract actually exposes

---

## Recommended First Move

Phase 0 is complete in the current worktree. The next best sequence is:

1. land `bd-3bs4j` for hosted-auth smoke coverage
2. land `bd-3mdry` for `PanelErrorBoundary` and lazy wrapper tests
3. start `bd-il78w` by extracting the auth HTML templates out of `auth_router_neon.py`
4. continue `bd-om29` with `useSidebarLayout`, which is the cleanest next stateful seam to pull out of `App.jsx`

This sequence adds safety nets first, then reduces the two largest files using the least risky extractions available.
