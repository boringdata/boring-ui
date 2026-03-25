# Improvement Roadmap

## Status

Rewritten on 2026-03-25 around a narrower product definition and a stricter foundation goal.

This roadmap now assumes these hard product decisions:

- `pi` is the only supported agent framework
- the Claude terminal panel is removed
- the shell panel is removed
- PTY, Claude stream, and `agent_normal` runtime surfaces are removed rather than preserved
- no backward-compatibility aliases are required for removed runtime surfaces
- auth/session/bootstrap correctness is the highest-priority engineering track
- the runtime contract should express explicit placement/storage/provisioner policy, not vague `agent-lite` / `agent-frontend` / `agent-backend` modes
- the existing eval framework under `tests/eval/` must become a first-class validation tool in the roadmap

Recent work already landed that this roadmap builds on:

- truthful verification-email messaging
- explicit public-origin support for hosted auth callbacks
- user settings persistence moved to Neon DB
- stale backend-agent workspace provisioner secrets were cleaned up
- orphaned Fly workspace machines were cleaned up
- `package-lock.json` was regenerated to unblock Docker builds
- smoke email collisions were fixed with randomized suffixes
- the three deployed app variants were brought back to a smoke-passing state

Tracked beads that remain relevant after this rewrite:

- `bd-znpbo` Tooling: restore tracked lint/style gate and style-guideline enforcement
- `bd-3bs4j` Smoke: cover `AUTH_EMAIL_PROVIDER=none` and `BORING_UI_PUBLIC_ORIGIN` auth flows
- `bd-3mdry` Frontend: add `PanelErrorBoundary` and lazy panel wrapper tests
- `bd-il78w` Auth UI: move server-rendered auth page out of embedded Python string templates
- `bd-b2fof` Backend: decompose Neon auth flows into smaller contract-tested units
- `bd-om29` Frontend: break `App.jsx` workspace shell into focused state/hooks modules
- `bd-1mwn4` Foundation: remove Claude runtime and terminal/shell/PTy legacy surface
- `bd-waixe` Auth: freeze and harden auth/session/callback/bootstrap contract
- `bd-f21sg` Foundation: replace mode-centric config with placement/storage/provisioner policy
- `bd-wjlvl` Foundation: freeze PI-only runtime-config/capabilities/pane contract
- `bd-xle50` Testing: realign unit, smoke, and eval gates around the PI-only core
- `bd-x8boo` Foundation: split overloaded control_plane module and relocate API-root stragglers

Closed as obsolete under this direction:

- `bd-rm17p` Backend: split stream bridge/runtime paths into focused modules

---

## Executive Summary

The framework needs a smaller and more explicit core.

The new execution order is:

1. land operational hygiene first so the repo is trustworthy to change
2. harden auth/session/bootstrap
3. delete the Claude/terminal/shell/PTy legacy surface instead of refactoring it
4. run backend config work and frontend `App.jsx` decomposition in parallel
5. freeze the PI-only runtime contract and restructure backend modules around it
6. realign unit, smoke, and eval so each layer protects a clear slice of the new core

The old roadmap spent too much effort on shrinking hotspots that may no longer belong in the product. This rewrite moves the focus to contract clarity, scope reduction, auth correctness, and testable foundations.

---

## Product Decisions

These decisions are now part of the plan, not open questions:

1. One agent runtime only: `pi`
2. No Claude runtime surface in the core product
3. No terminal pane and no shell pane in the core product
4. No PTY transport in the core product unless a future roadmap explicitly reintroduces shell as a core feature
5. No backward-compatibility aliases for removed runtime families
6. Auth is a core guarantee, not an optional convenience
7. `local` is dev-only, not a first-class product/runtime contract
8. The reference production profile is:
   - `agent.placement = "server"`
   - `workspace.storage = "http"`
   - `workspace.provisioner = "fly"`
   - `auth.provider = "neon"`
9. Deployment presets may still exist in `deploy/`, but they are packaging shortcuts, not the architecture contract

---

## Goals

- make the framework core materially smaller and easier to reason about
- make auth/session/workspace bootstrap the most stable part of the app
- replace implicit runtime “modes” with explicit placement/storage/provisioner policy
- expose a PI-only logical contract instead of transport-era capability names
- use unit tests, smoke tests, and evals for distinct responsibilities with minimal overlap
- keep the framework composable for child apps without carrying legacy runtime surface area

## Non-Goals

- no second agent framework
- no terminal or shell UX work
- no broad provider abstraction for auth beyond what current Neon/local support actually needs
- no refactor of deleted subsystems for cleanliness alone
- no backward-compatibility shim layer for PTY/Claude-era routes or capability names
- no large `App.jsx` rewrite before the product surface is smaller

---

## Current Mismatch To Resolve

### Runtime Surface

The repo still carries an older multi-surface model that no longer matches the target product:

- `src/back/boring_ui/api/app.py` still mounts PTY and Claude stream paths through `include_pty` / `include_stream`
- `src/back/boring_ui/api/capabilities.py` still registers `pty`, `chat_claude_code`, and `stream`
- `src/back/boring_ui/runtime_config.py` still infers `claude_code` and encodes `frontend` / `backend` mode semantics
- `src/back/boring_ui/app_config_loader.py` still parses `[agents].mode = "frontend" | "backend"`
- `src/front/registry/panes.jsx` still declares `terminal` and `shell` panes
- `src/front/utils/routes.js` still exposes websocket routes for PTY and Claude stream

### Product Contract

The current contract is still transport-shaped rather than product-shaped:

- capabilities advertise router-era names instead of logical agent/workspace/auth shape
- pane requirements use `requiresRouters` for legacy runtime families
- deploy docs still center `agent-lite`, `agent-frontend`, and `agent-backend`
- `local` and `neon` still leak into route/module structure as larger parallel implementations than the product now needs

### Testing

The test suite still validates a broader product than the one we want to keep:

- integration tests assert `pty`, `chat_claude_code`, and `stream`
- capability smoke expects `terminal` and `shell` pane semantics
- eval profile contracts still carry `requires_frontend_shell`
- deploy docs and smoke docs still describe the old mode matrix

### Structure

The broad architecture is good, but the repo is growing unevenly:

- `src/back/boring_ui/api/modules/control_plane/` is acting as a junk drawer for auth, users, workspaces, collaboration, provider-specific persistence, and shared helpers
- `local` vs `neon` is still expressed as duplicated router files in too many places; that is acceptable short-term, but it should not be the steady-state architecture
- `src/back/boring_ui/api/modules/control_plane/auth_router_neon.py` is still the clearest oversized-file warning sign in the backend
- `src/back/boring_ui/api/` still has loose files that either belong under an existing module or should be deleted as part of the PI-only cut:
  - `approval.py`
  - `git_backend.py`
  - `subprocess_git.py`
  - `git_routes.py`
  - `storage.py`
  - `stream_bridge.py`
  - `workspace_plugins.py`
- `src/front/components/` is flatter than it needs to be, but that should be cleaned up only after the terminal/Claude removals so we do not reorganize deleted components
- `src/companion_service/` and `src/test/` need explicit treatment: either they remain part of the supported product, or they get removed as legacy/orphan surface

The target structure after the agreed cuts is closer to:

```text
src/back/boring_ui/api/
  app.py
  config.py
  capabilities.py
  observability.py
  policy.py
  agents/            # PI-only harness and registry
  workspace/         # context, resolver, paths, storage, provisioning, plugins
  modules/
    auth/
    users/
    workspaces/
    collaboration/
    files/
    git/
    approval/        # only if approval stays in core
    messaging/
    ui_state/
    github_auth/     # if this integration stays supported
```

Explicitly removed from that target shape:

- `modules/pty/`
- `modules/stream/`
- `modules/agent_normal/`

With one additional rule:

- domain routers and services should become provider-neutral
- `local` should survive only as a thin dev adapter behind those domain services
- the final steady state should not keep parallel `*_neon.py` / local router trees for every major domain

This structure work is real, but it should follow the product cuts. Do not reorganize deleted runtime families into nicer folders.

---

## Foundation Principles

1. Stable contracts beat more features.
2. Deleting non-core surface is better than refactoring it indefinitely.
3. The public contract must be logical and product-shaped, not transport-shaped.
4. Auth must fail closed on misconfiguration.
5. Optional features that are not durable or well-specified must be explicitly marked experimental.
6. Each test layer should answer a different question:
   - unit/contract: is the implementation correct in isolation?
   - smoke: does the deployed critical path work end-to-end?
   - eval: does the framework still satisfy the platform and child-app contract?

---

## Testing Strategy Review

### Current Layers

The repo already has four meaningful validation layers:

1. frontend unit tests via Vitest
2. backend unit/integration tests via pytest
3. deploy-shaped smoke tests under `tests/smoke/`
4. framework eval harness under `tests/eval/`

Playwright exists, but it should remain a targeted UI check, not the foundation gate.

### What Each Layer Should Own

#### Unit And Contract Tests

Use for fast, deterministic validation of:

- auth/session primitives
- callback URL validation and redirect allowlisting
- runtime config serialization
- app config parsing and startup validation
- capability payload shape
- pane registry requirements and gating logic
- child-app extension contracts where no live deploy is required
- thin local-dev adapters that are intentionally not part of the production contract

#### Smoke Tests

Use for deploy-shaped validation of the real critical path:

- sign-up / sign-in / callback / logout / session / identity bootstrap
- workspace lifecycle and boundary routing
- files and git on a deployed instance
- runtime-config and capabilities payloads on the deployed app
- explicit absence of removed legacy runtime routes and capability names

The default smoke reference path should be the reference production profile, not local mode.

#### Eval Framework

Use `tests/eval/` to validate platform-level and framework-level behavior:

- deploy/profile prerequisites
- child-app composability
- extensibility contract for custom panes/tools
- evidence capture and grading
- policy-level checks such as “legacy runtime surfaces are absent” and “the PI-only contract is present”

The eval framework should not replace smoke tests. It should enforce higher-level framework guarantees across environments and child-app scenarios.

The default eval reference path should also be the reference production profile. Local mode may have targeted harness tests, but it should not define the framework grade.

### Current Gaps

1. The contract between `/__bui/config`, `/api/capabilities`, and `src/front/registry/panes.jsx` is not locked together.
2. The current smoke and integration suites still assume `pty`, `chat_claude_code`, `stream`, `terminal`, and `shell`.
3. Auth has good smoke coverage already, but startup validation, redirect strictness, and deploy-misconfig behavior are still under-specified relative to its importance.
4. The eval framework is present and tested, but the roadmap does not currently use it to protect the actual framework contract.
5. Eval profile contracts still encode old assumptions like `requires_frontend_shell`.
6. There are not enough negative tests proving removed routes/capabilities are actually gone.
7. `bd-znpbo` is still open, which means lint/style enforcement is not yet an authoritative repo-level gate.
8. `local` still carries more architectural weight than it should for a dev-only path.
9. Operational reliability issues are too easy to rediscover late:
   - pre-existing unit test failures
   - poor auth endpoint logging on 500s
   - stale Fly workspace machines consuming the machine quota

### Required Testing Rework

The new plan must explicitly include:

- deleting or rewriting tests that assert PTY/Claude-era behavior
- adding negative tests for removed routes, panes, and capability names
- adding contract tests for the new PI-only runtime payloads
- using `tests/eval/` to validate the new runtime contract and the production reference profile
- making auth smoke and auth contract tests the first-class correctness gate for the app
- making the reference smoke/eval target the production profile (`server` placement + `http` storage + `fly` provisioner + Neon auth)
- keeping `local` coverage focused on dev-adapter unit tests and a small parity subset only

---

## Target Architecture Contract

### App Config

The runtime contract should stop using plural `agents` and vague `mode` values for the core architecture.

The target app-level config is:

```toml
[agent]
runtime = "pi"
placement = "browser"   # "browser" | "server" — where PI runs

[workspace]
storage = "http"        # "lightningfs" | "http" — matches existing data backend values
provisioner = "none"    # "none" | "fly" — whether workspaces get dedicated machines

[auth]
provider = "neon"
```

Notes:

- `agent.runtime` is fixed to `pi`
- `placement` is about where the agent runs
- `storage` matches the real frontend/backend data path vocabulary already used by the app
- `provisioner` is concrete and should map to real workspace machine provisioning behavior, not aspirational isolation vocabulary
- deploy presets may still map to these fields, but the fields above are the contract
- `auth.provider = "local"` is dev-only and should not define production contract behavior

Deploy presets remain as user-facing shorthand:

- `agent-lite`: `placement=browser`, `storage=http`, `provisioner=none`
- `agent-frontend`: `placement=browser`, `storage=http`, `provisioner=none`
- `agent-backend`: `placement=server`, `storage=http`, `provisioner=fly` when dedicated machines are enabled

Reference profiles:

1. Reference production profile
   - `agent.placement = "server"`
   - `workspace.storage = "http"`
   - `workspace.provisioner = "fly"`
   - `auth.provider = "neon"`

2. Supported lighter hosted profile
   - `agent.placement = "browser"`
   - `workspace.storage = "http"`
   - `workspace.provisioner = "none"`
   - `auth.provider = "neon"`

3. Local development profile
   - `agent.placement = "browser"`
   - `workspace.storage = "lightningfs"` or `"http"` for parity work
   - `workspace.provisioner = "none"`
   - `auth.provider = "local"`

Only the first two profiles are product commitments. The local profile exists to speed development and debugging.

### Runtime Payload

The target `/__bui/config` and `/api/capabilities` payloads should expose logical state, not transport history.

Target shape:

```json
{
  "agent": {
    "runtime": "pi",
    "placement": "browser",
    "available": true
  },
  "workspace": {
    "storage": "http",
    "provisioner": "fly"
  },
  "features": {
    "files": true,
    "git": true,
    "approval": false
  },
  "auth": {
    "provider": "neon",
    "verificationEmailEnabled": true
  }
}
```

Names that should disappear from the public contract:

- `pty`
- `chat_claude_code`
- `stream`
- `agents.mode = frontend|backend`

### Pane Contract

Pane requirements should be logical rather than router-era:

- `agent` pane requires `agent.runtime == "pi"` and `agent.available == true`
- file/editor panes require `features.files == true`
- git surfaces require `features.git == true`
- review/approval surfaces require `features.approval == true`

There is no core `terminal` pane and no core `shell` pane.

---

## Execution Order

### Phase 0: Operational Hygiene

Target:

- remove avoidable operational noise before deeper foundation work starts

Work:

1. confirm and fix any pre-existing unit test failures in `tests/unit/test_auth_session_routes.py`
2. add structured error logging to auth endpoints so 500s include actionable context
3. add a guard or cleanup path for orphaned Fly workspace machines so stale `ws_*` machines cannot silently exhaust machine limits
4. confirm `FLY_WORKSPACE_APP` and `FLY_IMAGE_REF` are absent from apps that should not provision dedicated workspace machines
5. remove obvious orphan/legacy paths after a quick dependency check:
   - `src/companion_service/`
   - `src/test/`

Done when:

- `python3 -m pytest tests/unit/ -v` shows 0 failures
- auth endpoints log request errors at warning/error level with useful detail
- workspace machine state is bounded and no longer silently accumulates

Why first:

- foundation work goes faster when the repo and deploys are not already lying to you

### Cross-Cutting: Observability

This is not a standalone phase. Each phase should leave the changed subsystem more observable than before.

Required observability improvements as work progresses:

- auth endpoints: log Neon/Auth proxy failures with enough response detail to debug them
- workspace creation/provisioning: log duration breakdown and failure reason
- config validation: log resolved config summary and rejected invalid combinations
- startup: log the effective product profile (`placement`, `storage`, `provisioner`, auth provider, enabled features)
- cold start/provisioned workspaces: capture time from machine boot to first healthy response where applicable

### Prerequisite: Land The Tracked Lint Gate Cleanly

Tracked bead:

- `bd-znpbo`

This is not the center of the roadmap anymore, but it still needs to be landed and enforced cleanly. The foundation plan assumes tracked lint/style commands are real and that contributor enforcement is defined in CI.

This prerequisite should not block Phase 1 auth work if the tracked gate is mostly working and the remaining gap is enforcement rather than correctness.

---

### Phase 1: Harden Auth And Bootstrap First

Target:

- make auth/session/workspace bootstrap the most stable subsystem in the repo

Tracked beads:

- `bd-waixe`
- `bd-3bs4j`
- `bd-il78w`
- `bd-b2fof`

Files likely involved:

- `src/back/boring_ui/api/modules/control_plane/auth_router_neon.py`
- `src/back/boring_ui/api/modules/control_plane/auth_session.py`
- `src/back/boring_ui/api/modules/control_plane/me_router_neon.py`
- `src/back/boring_ui/api/modules/control_plane/workspace_boundary_router_hosted.py`
- `tests/unit/test_auth_session_routes.py`
- `tests/smoke/smoke_neon_auth.py`
- `tests/smoke/smoke_workspace_lifecycle.py`
- `tests/smoke/smoke_capabilities.py`

Work:

- freeze the boring-ui auth contract around sign-in, sign-up, callback, logout, session, identity, and workspace redirect/bootstrap
- fail closed on missing hosted auth config instead of silently falling back
- tighten callback URL validation and redirect allowlisting
- add startup validation for required Neon auth settings in hosted mode
- keep `local` auth as a thin dev-only adapter behind the same domain service contract rather than a parallel product path
- keep auth HTML extraction early because it is low-risk and removes noise from the file
- extract auth URL helpers and crypto helpers before broader router thinning
- expand smoke coverage for `AUTH_EMAIL_PROVIDER=none` and `BORING_UI_PUBLIC_ORIGIN`
- add contract tests for misconfiguration, bad redirects, and callback completion invariants
- add actionable request/error logging to the changed auth endpoints
- do not broaden auth abstraction unless duplication still hurts after these concrete extractions

Done when:

- auth/session/bootstrap behavior is explicit and covered by unit + smoke tests
- hosted misconfiguration fails fast
- `local` auth behavior is clearly dev-only and does not define the production contract
- auth template extraction is landed
- `auth_router_neon.py` is materially smaller and easier to review
- the boring-ui auth contract is documented and treated as stable

Why first:

- auth is the core of the app and the highest-value correctness surface

---

### Phase 2: Remove Legacy Claude, Terminal, Shell, And PTY Surface

Target:

- delete non-core runtime surface rather than carrying it forward

Tracked bead:

- `bd-1mwn4`

Files likely involved:

- `src/back/boring_ui/api/app.py`
- `src/back/boring_ui/api/capabilities.py`
- `src/back/boring_ui/api/config.py`
- `src/back/boring_ui/runtime_config.py`
- `src/back/boring_ui/api/modules/stream/`
- `src/back/boring_ui/api/modules/agent_normal/`
- `src/back/boring_ui/api/modules/pty/`
- `src/front/registry/panes.jsx`
- `src/front/components/Terminal.jsx`
- `src/front/panels/TerminalPanel.jsx`
- `src/front/panels/ShellTerminalPanel.jsx`
- `src/front/utils/routes.js`
- affected docs and tests under `docs/`, `tests/unit/`, `tests/integration/`, and `tests/smoke/`

Work:

- triage `src/back/boring_ui/api/stream_bridge.py` before deletion; if PI imports no helpers from it, delete it entirely, otherwise extract only the surviving PI-relevant helpers into `api/agents/` first
- remove `terminal` and `shell` panes from the registry
- remove PTY websocket and lifecycle routes
- remove Claude stream and `agent_normal` routes
- remove Claude/PTy provider config and capability names
- remove websocket route helpers for deleted surfaces
- delete `src/back/boring_ui/api/git_routes.py` if it remains a dead stub
- remove docs that present the deleted runtime surface as part of the framework core
- remove tests that lock in deleted routes/capabilities, replacing them with absence tests where needed
- do not leave a compatibility alias layer behind

Done when:

- no core pane, route, capability, config, or deploy doc depends on PTY/Claude-era runtime families
- deleted routes return 404 or are absent from mounted route tables
- `/api/capabilities` and `/__bui/config` no longer mention deleted runtime families
- the test suite validates absence instead of preserving legacy behavior

Why second:

- it shrinks the architecture before we redesign the contract that remains

---

### Phase 3a: Make Config Explicit (Backend)

Target:

- replace the old `frontend/backend/lite` architecture language with explicit placement, storage, and provisioner policy

Tracked bead:

- `bd-f21sg`

Files likely involved:

- `src/back/boring_ui/app_config_loader.py`
- `src/back/boring_ui/runtime_config.py`
- `src/back/boring_ui/api/config.py`
- `deploy/shared/boring.app.toml`
- `deploy/fly-lite/boring.app.toml`
- `deploy/README.md`
- `docs/runbooks/MODES_AND_PROFILES.md`
- tests covering config loading and runtime payloads

Work:

- introduce singular `[agent]` config with `runtime` and `placement`
- introduce `[workspace]` config with `storage` and `provisioner`
- remove `agents.mode` from the core contract
- keep deploy presets only as packaging shortcuts mapped onto the new policy fields
- add startup validation for invalid combinations
- document the new policy with clear examples for local dev, hosted browser-agent, and hosted Fly-provisioned agent deployments
- declare the Fly-provisioned hosted profile as the reference production path for docs, smoke, and eval

Validation rules to enforce:

- `agent.runtime` must be `pi`
- `agent.placement = "server"` with `workspace.storage = "lightningfs"` is invalid
- `auth.provider = "local"` is invalid outside explicit local development contexts
- removed legacy keys should not silently reconfigure the app

Done when:

- runtime config and app config no longer depend on `frontend|backend` mode semantics
- deployment documentation explains architecture in terms of placement/storage/provisioner
- invalid combinations fail early and loudly

Why now:

- once the legacy surface is gone, the remaining core can be described more honestly and more simply

---

### Phase 3b: Split `App.jsx` (Frontend, Parallel With Phase 3a)

Target:

- reduce `src/front/App.jsx` to a thin shell while the backend config work happens in parallel

Tracked bead:

- `bd-om29`

Files likely involved:

- `src/front/App.jsx`
- extracted state modules/hooks/components under `src/front/`
- relevant frontend tests

Why here instead of last:

- the `App.jsx` problem does not disappear when terminal/shell/Claude panels are removed
- every later frontend change gets easier once stateful responsibilities are no longer all in one file
- the extraction work mostly touches frontend state, routing, and DockView orchestration, not the deleted runtime panels
- the backend config track and the frontend shell track touch different files and can run in parallel

Target structure:

```text
src/front/
  App.jsx                        # ~200 lines, shell + JSX only
  hooks/
    useWorkspaceAuth.js
    useWorkspaceRouter.js
    useDockLayout.js
    usePanelActions.js
    useApprovalPolling.js
    useFrontendStatePersist.js
    useDataProviderScope.js
```

Work:

- remove now-dead runtime branches and panel orchestration first
- extract pure state models/reducers/selectors before wrapping them in hooks
- then extract the remaining stateful seams into focused modules with clear ownership
- keep the shell composition thin and avoid inventing abstractions for deleted surfaces
- group remaining frontend components by surviving domains only after the terminal/Claude components are gone; do not reorganize deleted files

Concrete extraction plan after the scope cut:

1. `useApprovalPolling` (~100 lines)
2. `useDataProviderScope` (~100 lines)
3. `useFrontendStatePersist` (~120 lines)
4. `useWorkspaceAuth` (~150 lines)
5. `useWorkspaceRouter` (~200 lines)
6. `usePanelActions` (~400 lines)
7. `useDockLayout` (~500 lines)

Hook responsibilities:

- `useWorkspaceAuth`
  - user identity and workspace menu state
  - workspace list loading
  - switch/create workspace actions
  - user/workspace settings entry points
  - logout
- `useWorkspaceRouter`
  - route-derived workspace state
  - storage prefix / project root / layout version
  - settings/setup route detection
  - workspace path synchronization
- `useDockLayout`
  - DockView layout state
  - restore/migrate/persist layout
  - group resolution and docking rules
- `usePanelActions`
  - file-open actions
  - panel-open / close / focus flows
  - surviving panel orchestration after terminal/shell removal
- `useApprovalPolling`
  - approval fetch / poll / refresh if approval remains core
- `useFrontendStatePersist`
  - local persisted frontend state outside DockView itself
- `useDataProviderScope`
  - data-provider selection, cache scoping, and namespace derivation

Suggested shell shape:

```jsx
export default function App() {
  const workspaceAuth = useWorkspaceAuth(...)
  const workspaceRouter = useWorkspaceRouter(...)
  const dockLayout = useDockLayout(...)
  const panelActions = usePanelActions(...)
  const approvalPolling = useApprovalPolling(...)
  const frontendState = useFrontendStatePersist(...)
  const dataProvider = useDataProviderScope(...)

  return <WorkspaceShell ... />
}
```

Done when:

- `App.jsx` is primarily shell composition and JSX, not long-lived state orchestration
- extracted state logic is unit-testable without full DockView rendering
- the shell reflects the new core, not the old one spread across more files

---

### Phase 4: Freeze The PI-Only Runtime Contract

Target:

- make `/__bui/config`, `/api/capabilities`, and pane requirements agree on one stable PI-only contract while restructuring backend modules around the surviving product

Tracked bead:

- `bd-wjlvl`
- `bd-x8boo`

Files likely involved:

- `src/back/boring_ui/runtime_config.py`
- `src/back/boring_ui/api/capabilities.py`
- `src/front/registry/panes.jsx`
- `src/front/hooks/useCapabilities.js`
- `tests/unit/test_capabilities.py`
- `tests/unit/test_agent_app_config_loader.py`
- new contract-focused tests under `tests/unit/` and `tests/integration/`

Work:

- redesign capabilities around logical `agent`, `workspace`, `features`, and `auth` sections
- remove transport-era capability names from the public contract
- make pane requirements logical instead of router-name-driven wherever possible
- align the runtime payload served from `/__bui/config` with the same contract vocabulary
- define what is core and what is experimental
- explicitly classify approval as either durable core or experimental non-core before leaning on it further in the shell
- converge local and Neon behavior behind shared domain routers/services; provider-specific differences should live in small adapters, not duplicate router trees
- split the overloaded `control_plane/` area along real domain seams instead of keeping auth, users, workspaces, and collaboration in one bucket
- move surviving API-root stragglers into the right homes:
  - `git_backend.py` and `subprocess_git.py` into `modules/git/`
  - `approval.py` into `modules/approval/` if approval stays in core
  - `storage.py` and `workspace_plugins.py` into `api/workspace/` if they still belong after the surface cut
  - delete `git_routes.py` if it remains a dead stub
- classify or remove `src/companion_service/` and `src/test/` instead of leaving them as ambiguous legacy surface

Done when:

- frontend bootstrap, capability gating, and child-app extension points all speak the same contract language
- the contract is documented and locked by tests
- there is no ambiguity about the supported agent/runtime surface
- backend module boundaries match the supported product instead of the historical runtime sprawl
- `local` no longer adds major structural complexity relative to Neon because it is clearly reduced to a dev adapter

Why now:

- a stable framework depends on a stable contract more than on smaller files alone

---

### Phase 5: Realign Unit, Smoke, And Eval Around The New Core

Target:

- make the test strategy reflect the actual product and use the eval framework deliberately

Tracked beads:

- `bd-xle50`
- `bd-3mdry`

Files likely involved:

- `tests/unit/`
- `tests/integration/`
- `tests/smoke/`
- `tests/eval/`
- `docs/runbooks/SMOKE_TESTS.md`
- relevant CI or runner scripts

Work:

- review every test entrypoint that still encodes PTY/Claude-era assumptions and either remove it or rewrite it
- define a minimal foundation gate:
  - unit/contract tests for auth, runtime config, capabilities, and pane gating
  - smoke tests for auth, workspace lifecycle, files, git, and capabilities
  - eval runs for framework contract and child-app composability
- update `tests/eval/capabilities.py` profile contracts to reflect the PI-only foundation
- remove `requires_frontend_shell` and other legacy profile requirements that no longer describe the product
- add eval checks that prove deleted runtime surfaces stay deleted
- add eval checks that prove the new runtime contract is present and internally consistent
- keep `PanelErrorBoundary` coverage because lazy-panel crash isolation remains valuable even after the terminal/shell cuts
- document which changes require unit-only, smoke, eval, or combined validation

Specific gaps this phase must close:

- `tests/smoke/smoke_capabilities.py` still expects `terminal`, `shell`, `pty`, and `chat_claude_code`
- `tests/integration/test_create_app.py` still asserts PTY/Claude-era features and route tables
- eval profile contracts still describe a broader platform than the product now intends to ship
- there are not enough tests asserting that removed legacy routes are absent

Done when:

- every test layer has a crisp responsibility
- the test suite no longer preserves deleted runtime surface by accident
- eval is used to guard framework-level regressions instead of sitting beside the roadmap unused

Why now:

- once the contract is rewritten, the tests must become truthful immediately or they will fight the new foundation

---

## Risks And Mitigations

### Risk: Auth hardening broadens into a full provider framework prematurely

Mitigation:

- keep auth work concrete and Neon-focused unless duplication forces a higher-level service layer
- extract templates, URL helpers, crypto helpers, and client helpers first
- treat provider-neutralization as optional, not assumed

### Risk: Removing terminal/shell/Claude surface breaks docs and tests in many places

Mitigation:

- treat deletion as a full-surface cut, not just a UI change
- explicitly search docs/tests/routes/capabilities for old names and remove them in the same track
- add negative tests proving the old surface is gone

### Risk: New config language creates a second naming layer instead of replacing the old one

Mitigation:

- do not keep `mode` as a parallel core concept
- if deploy presets remain, document them as derived packaging shortcuts only
- fail on invalid legacy config instead of silently translating forever

### Risk: Eval remains disconnected from the actual contract work

Mitigation:

- update eval profile contracts as part of the contract rewrite, not later
- add explicit eval checks for legacy-surface absence and new contract presence
- require eval evidence for framework-contract changes

### Risk: Approval remains ambiguous and destabilizes the shell refactor

Mitigation:

- explicitly classify approval as durable core or experimental before extracting more approval state from `App.jsx`
- do not keep refining approval UX if the backend semantics are still restart-unsafe

---

## Success Criteria

The roadmap is succeeding if the repo reaches this state:

- auth/session/bootstrap is the most reliable subsystem and is protected by unit + smoke coverage
- no public route, capability, pane, or doc still depends on PTY/Claude-era runtime surface
- the core runtime contract is PI-only and logical, not transport-shaped
- app config is expressed in terms of agent placement, workspace storage, and workspace provisioner policy
- `/__bui/config`, `/api/capabilities`, and pane requirements all agree on one documented contract
- unit tests, smoke tests, and eval each protect a distinct layer of that contract
- the eval framework is actively used to validate framework and child-app contract behavior
- the reference production profile is the default path for smoke/eval and documentation
- `App.jsx` is smaller because the product surface is smaller and the remaining state has clearer ownership

---

## Recommended First Move

The next best execution sequence is:

1. land Phase 0 operational hygiene first so tests, logs, and workspace machine state are trustworthy
2. start `bd-waixe` and `bd-3bs4j` together so auth hardening and auth smoke move first
3. start `bd-1mwn4` immediately after the auth contract is stable enough to stop changing underfoot
4. run `bd-f21sg` and `bd-om29` in parallel as Phase 3a/3b
5. land `bd-wjlvl` and `bd-x8boo` together so the rewritten contract and the backend module boundaries converge at the same time
6. finish `bd-xle50` so the new contract and the new test strategy land together

That order keeps the work focused on foundations instead of polishing legacy branches that the framework no longer intends to keep.
