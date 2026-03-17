# Plan: Server-Side PI Agent

## Goal

Run PI on the backend instead of in the browser, without changing the repo's authority model.

The important part:

- browser keeps the current integrated PI UI and becomes transport only
- PI service owns runtime/session state only
- `workspace-core` in `boring-ui` keeps file authority
- backend PI is only supported with the server-backed `pi-httpfs` profile

## Keep It Simple

This plan is intentionally narrow.

It does **not** try to do all of these at once:

- transport migration
- tool-surface redesign
- sandbox architecture redesign
- workspace plugin/command loading
- iframe/embed mode redesign

MVP first. Extras later.

## Rules

1. Do not bypass the control-plane workspace boundary.
2. Do not give PI direct filesystem authority.
3. Do not enable backend PI in `pi-lightningfs` or `pi-cheerpx`.
4. Do not add shell execution in the MVP.

## Current Starting Point

Already in repo:

- `src/pi_service/server.mjs` provides PI session + SSE endpoints
- `src/front/providers/pi/backendAdapter.jsx` can talk to a backend PI service
- `src/front/providers/pi/config.js` already supports backend mode detection
- the existing integrated PI UI already lives inside `src/front/panels/CompanionPanel.jsx`

Current mismatch:

- default core profile is `pi-lightningfs`
- current frontend PI routes are not yet aligned with the control-plane workspace boundary
- current native PI tools assume browser-side runtime composition
- current config still mixes integrated backend PI concerns with older direct-connect/iframe-style semantics

## MVP Architecture

```
Browser PI panel
  -> /w/{workspace_id}/api/v1/agent/pi/*
boring-ui control-plane boundary
  -> auth + membership + workspace scoping
  -> forward to internal PI service
PI service
  -> session/runtime/model logic
  -> delegates file operations back to boring-ui
workspace-core
  -> file authority
```

UI note:

- keep the current built-in PI panel UI
- do not use iframe mode for this plan
- do not replace the panel with a separate embedded app

## Route Model

Frontend entrypoint for backend PI:

- `/w/{workspace_id}/api/v1/agent/pi/sessions/create`
- `/w/{workspace_id}/api/v1/agent/pi/sessions`
- `/w/{workspace_id}/api/v1/agent/pi/sessions/{id}/history`
- `/w/{workspace_id}/api/v1/agent/pi/sessions/{id}/stream`
- `/w/{workspace_id}/api/v1/agent/pi/sessions/{id}/stop`

Notes:

- browser should not talk directly to the PI service port
- backend PI should ride the same workspace boundary as other scoped routes
- boring-ui should use a separate internal PI service upstream config

## Profile Rule

Backend PI is supported only when the frontend profile is:

- `VITE_UI_PROFILE=pi-httpfs`

Not supported:

- `pi-lightningfs`
- `pi-cheerpx`

Reason:

- those profiles use browser-local files/commands
- backend PI would see a different filesystem than the user

## Capability Rule

Keep capability logic simple:

- backend advertises integrated backend PI with a simple explicit flag
- frontend only uses backend PI when its local data backend is `http`

Do **not** try to make `/api/capabilities` infer the frontend profile.

Simple contract:

- integrated backend PI uses a new capability flag such as `services.pi.integrated_backend = true`
- frontend integrated mode does **not** depend on `services.pi.url`
- `PI_URL` / iframe-style config stays separate from this path

## UI Rule

Use the existing integrated PI UI.

That means:

- keep `CompanionPanel` when `provider === 'pi'`
- keep `PiBackendAdapter` as the transport adapter
- keep `PiSessionToolbar`
- change routing/transport only

Do **not** use:

- iframe mode
- a separate embedded PI web app
- a second PI panel implementation

## PI Service Responsibility

PI service owns:

- session lifecycle
- model/provider calls
- message history
- SSE streaming
- tool orchestration

PI service does **not** own:

- workspace filesystem access
- auth/session validation
- workspace membership checks
- direct sandbox ownership

Session rule:

- every PI session must be tagged with `workspace_id` and `user_id`
- `history`, `stream`, and `stop` must verify that scope before using the session

## MVP Tool Plan

Do not redesign PI tools in the MVP.

Use backend-safe versions of the existing typed tools:

- `read_file`
- `write_file`
- `list_dir`
- `search_files`

Exclude:

- browser-only bridge tools like `open_file` and `list_tabs`
- shell execution
- dynamic app command loading from workspace files
- git tools

## Delegation Rule

PI must call back into `boring-ui` for file/git work.

Use the existing delegated policy model:

- `X-Scope-Context`
- workspace id
- actor
- capability claims
- cwd/worktree
- session id when required

Do not invent a separate ad-hoc policy header.

## Multi-Workspace Reality

Keep this explicit:

- MVP assumes PI is deployed per workspace backend/runtime, not as one shared multi-workspace filesystem service

- current file APIs are rooted in backend workspace config

So MVP backend PI should target the same workspace-scoped deployment model already used by the control-plane boundary.

Do not claim generic multi-workspace file isolation beyond what the current file routing actually supports.

## Implementation Phases

### Phase 1: Backend PI Through Workspace Boundary

- keep PI service as the runtime
- expose backend PI to the browser through `/w/{workspace_id}/api/v1/agent/pi/*`
- make boring-ui proxy/forward those requests to the internal PI service
- attach workspace/user scope at the boundary
- update `PiBackendAdapter`, PI route helpers, and PI backend-mode detection to use workspace-scoped same-origin routes for integrated mode
- pass or derive `workspace_id` explicitly for those routes

Acceptance:

- browser no longer needs direct PI service URL
- PI session routes are workspace-scoped
- auth/membership checks happen before PI runtime access
- frontend integrated mode no longer depends on `services.pi.url`

### Phase 2: Backend Tool Parity

- add backend-safe typed tools in PI service
- file tools call back into boring-ui
- remove browser-only tool assumptions from backend mode

Acceptance:

- backend PI can read/write files through boring-ui
- no direct workspace mount in PI service

### Phase 3: Optional Command Execution

Only if still needed after Phase 2.

- add a small workspace-core command route
- one-shot command execution only
- timeout + cancellation + output cap required
- PI uses existing `exec_bash` naming or a thin equivalent

If isolation is needed later, the command route can switch from local execution to sandboxed execution internally.

That is an implementation detail behind `workspace-core`, not a PI-owned system.

## Config

Use as little new config as possible.

Required:

- `PI_SERVICE_INTERNAL_URL` for boring-ui -> PI service forwarding
- `VITE_UI_PROFILE=pi-httpfs` in deployments that enable backend PI

Optional:

- `PI_SERVICE_HOST`
- `PI_SERVICE_PORT`
- `PI_SERVICE_MODEL`
- `PI_SERVICE_MAX_SESSIONS`

Explicitly not part of this plan:

- `PI_URL` iframe/direct-connect behavior

If `PI_URL` stays in the codebase, treat it as legacy or separate-mode config, not the integrated backend PI path.

## Out of Scope

Not in this plan:

- universal `run(command="...")` tool
- persistent shell sessions
- workspace-loaded `.mjs` commands
- Modal-specific sandbox lifecycle design
- backend PI for LightningFS or CheerpX profiles
- iframe/direct-connect PI mode

## Definition of Done

- backend PI runs server-side in `pi-httpfs`
- existing integrated PI panel UI is reused
- browser accesses PI through the workspace boundary, not a direct service port
- PI runtime has no direct file authority
- backend PI tooling delegates to `boring-ui`
- no split-brain filesystem behavior
- shell execution remains out until a separate small command plan exists
- git remains out of MVP
