# Plan: Post-Signup Hosted Fixes Execution Plan

## Status

Draft, grounded to the current repo state on 2026-03-20.

This is intentionally a second plan file. `docs/plans/post-signup-fixes/PLAN.md` already exists, but parts of its root-cause analysis no longer match the current code. This file is the execution plan tied to the tree as it exists today.

## Locked Observations

- `src/back/boring_ui/api/modules/control_plane/auth_router_neon.py` currently awaits `_eager_workspace_provision()` during `/auth/token-exchange`. The duplicate-workspace bug is still real, but the main race is frontend auto-create vs the first workspace-list load, not a fire-and-forget backend task.
- `src/front/App.jsx` fetches capabilities with `useCapabilities({ rootScoped: true })`, and `src/front/pages/WorkspaceSetupPage.jsx` blocks on that root-scoped state even while the browser is already inside `/w/{workspace_id}/setup`.
- `src/back/boring_ui/api/agents/pi_harness.py` already forwards `x-boring-workspace-root`, but `src/pi_service/tools.mjs` ignores that header and falls back to `process.cwd()` / `BORING_UI_WORKSPACE_ROOT`.
- `src/front/providers/pi/backendAdapter.jsx` intentionally flattens messages down to plain text. The richer tool rendering logic already exists in `src/front/components/chat/ClaudeStreamChat.jsx` and the renderer components under `src/front/components/chat/`.

## Goals

- Eliminate the post-signup duplicate-workspace and setup-page deadlock path in hosted mode.
- Make backend PI and the file API operate on the same workspace root.
- Show PI tool calls and tool output in chat by reusing the existing tool renderers.

## Non-Goals

- No redesign of the auth UI beyond what is required to fix the broken hosted flow.
- No new PI tool surface. This work should preserve the current `exec_bash`-first model.
- No second chat rendering system. The backend PI path should reuse the existing chat tool-card vocabulary.

## Workstream 1: Fix The Post-Signup State Machine

### Current Broken Flow

1. `AuthCallbackPage` in `src/front/pages/AuthPage.jsx` posts `/auth/token-exchange` and then redirects to `payload.redirect_uri || redirectUri || "/"`.
2. `auth_token_exchange()` in `src/back/boring_ui/api/modules/control_plane/auth_router_neon.py` issues the session cookie and eagerly ensures the default workspace exists.
3. The browser lands on `/`.
4. `src/front/App.jsx` sees `needsWorkspaceRedirect === true` and immediately treats the initial empty `workspaceOptions` array as authoritative.
5. If the first `/api/v1/workspaces` fetch has not finished yet, `handleCreateWorkspaceSubmit("My Workspace")` runs and creates a second workspace.
6. If the user reaches `/w/{workspace_id}/setup`, `WorkspaceSetupPage` waits for runtime readiness and then waits again for root-scoped capabilities to become non-pending.
7. The result is the current hosted failure mode: duplicate workspaces, redirect churn, and a setup page that can sit forever on "Loading workspace capabilities..." until the user refreshes.

### Implementation

#### 1. Make Workspace Auto-Create Wait For The First List Fetch

Primary file:

- `src/front/App.jsx`

Required changes:

- Add an explicit first-load state for workspace discovery, for example `workspaceListLoaded` or `workspaceListStatus`.
- Update `fetchWorkspaceList()` to mark success and failure separately from the `workspaceOptions` array itself.
- Change the root redirect effect so it does nothing until the first workspace-list request has completed.
- Never treat `[]` as "the user definitely has zero workspaces" before that first request resolves.
- Do not auto-create if the list request failed; surface the existing retry/error path instead.

Acceptance:

- Hosted login/signup reaches exactly one default workspace for a new user.
- Refresh timing no longer changes whether a duplicate workspace is created.

#### 2. Return The Eager-Provisioned Workspace From Token Exchange

Primary files:

- `src/back/boring_ui/api/modules/control_plane/auth_router_neon.py`
- `src/front/pages/AuthPage.jsx`

Required changes:

- Extend the `/auth/token-exchange` response payload to include the workspace id selected or created during eager provisioning.
- Prefer a direct post-callback navigation target such as `/w/{workspace_id}/setup` instead of bouncing through `/`.
- Preserve the existing `redirect_uri` contract for callers that still need it, but let the hosted flow consume the explicit workspace id when present.

Acceptance:

- The verify-email callback no longer needs the `/` redirect dance to discover the target workspace.
- The callback path is deterministic for both first-login and returning-login flows.

#### 3. Decouple Setup Readiness From Root-Scoped Capabilities

Primary files:

- `src/front/pages/WorkspaceSetupPage.jsx`
- `src/front/hooks/useCapabilities.js`
- `src/front/App.jsx`

Required changes:

- Stop using the root-scoped `capabilitiesPending` prop as the only gate for leaving the setup page.
- Add a workspace-scoped capabilities check inside `WorkspaceSetupPage` that runs after runtime becomes ready.
- The setup-page capabilities probe should use the current `/w/{workspace_id}/...` pathing so it resolves through the workspace boundary rather than the root-scoped app boot path.
- Add a bounded retry loop and a real error/retry state instead of an infinite spinner if capabilities still do not materialize after runtime is ready.
- Keep `useCapabilities({ rootScoped: true })` for shell boot where needed, but do not make the hosted setup page depend on that global fetch completing first.

Acceptance:

- `/w/{workspace_id}/setup` exits automatically once the runtime is ready and workspace-scoped capabilities are available.
- Manual browser refresh is no longer required to enter the workspace after hosted signup.

### Suggested Validation

- Extend `src/front/__tests__/AuthPage.test.jsx` with a token-exchange callback case that prefers a returned `workspace_id`.
- Add frontend coverage for the root redirect decision in a focused test, likely a new file alongside existing frontend tests.
- Add setup-page coverage for the runtime-ready plus delayed-capabilities case.
- Extend `tests/unit/test_auth_session_routes.py` for the hosted token-exchange payload shape.
- Extend `tests/smoke/smoke_neon_auth.py` so the hosted signup flow asserts direct workspace landing and no duplicate default workspace.

## Workstream 2: Make PI And Files Use The Same Workspace Root

### Current Broken Flow

1. `PiHarness._spawn_process()` in `src/back/boring_ui/api/agents/pi_harness.py` starts the Node sidecar with `cwd` set to the repo root.
2. `_proxy_headers()` correctly forwards `x-boring-workspace-root: str(ctx.root_path)`.
3. `resolveSessionContext()` in `src/pi_service/tools.mjs` reads workspace id, token, and backend URL, but it does not read `x-boring-workspace-root`.
4. `createWorkspaceTools()` and `buildSessionSystemPrompt()` use the module-level `WORKSPACE_ROOT`, which falls back to `process.cwd()`.
5. The file API is rooted at the actual workspace directory while `exec_bash` is rooted at the repo checkout, so the file tree and PI see different filesystems.

### Implementation

Primary files:

- `src/pi_service/tools.mjs`
- `src/pi_service/server.mjs`
- `src/back/boring_ui/api/agents/pi_harness.py`

Required changes:

- Add `workspaceRoot` to the PI session context contract.
- Teach `resolveSessionContext()` to read `workspace_root`, `workspaceRoot`, and the forwarded `x-boring-workspace-root` header.
- Persist `workspaceRoot` on the session in `server.mjs` and reapply it on `create`, `context`, and `stream`.
- Change `buildSessionSystemPrompt()` and `createWorkspaceTools()` to prefer `context.workspaceRoot` and use the env-level root only as a fallback.
- Keep the header forwarding in `PiHarness`; that part is already present and should remain the canonical bridge from backend workspace context into the Node sidecar.

Acceptance:

- `exec_bash` defaults to the same directory root that `files/router.py` and `git/router.py` use for the workspace.
- A file created by PI appears in the file tree without path mismatch.
- A file created or edited through the file API is visible to PI from the same relative path.

### Suggested Validation

- Extend `src/pi_service/tools.test.mjs` to cover `workspaceRoot` resolution from headers and payloads.
- Extend `tests/unit/test_pi_harness.py` to assert that the harness forwards `x-boring-workspace-root`.
- Extend `tests/unit/test_workspace_boundary_router_hosted.py` for local-workspace and workspace-scoped PI calls.
- Extend `tests/integration/test_bd_3g1g_6_3_agent_pi_runtime_surface.py` with a same-root file visibility regression case.

## Workstream 3: Show PI Tool Usage In Chat

### Current Broken Flow

1. `textFromMessage()` in `src/pi_service/server.mjs` strips assistant messages down to text blocks only.
2. `toUiMessages()` also flattens history into `{ role, text }`.
3. `handleStream()` sends SSE `delta` and `done` events containing only text.
4. `src/front/providers/pi/backendAdapter.jsx` stores the stream as `streamText` plus plain `messages[]`.
5. The existing tool renderers under `src/front/components/chat/` are never reached on the backend PI path.

### Implementation

#### 1. Preserve Structured Assistant Content In PI History And Streaming

Primary files:

- `src/pi_service/server.mjs`

Required changes:

- Keep plain-text extraction as a fallback, but stop treating it as the primary PI chat transport shape.
- Update the history endpoint so assistant messages can carry structured content blocks.
- Update the SSE stream to emit structured assistant content, including tool calls and tool results, rather than only a joined text string.
- Normalize the PI sidecar payload so frontend consumers can render a stable `tool_use` style structure.

#### 2. Reuse The Existing Tool Renderer Mapping Instead Of Rebuilding It

Primary files:

- `src/front/components/chat/ClaudeStreamChat.jsx`
- `src/front/providers/pi/backendAdapter.jsx`
- a new shared helper under `src/front/components/chat/`

Required changes:

- Extract the tool-name to renderer mapping out of `ClaudeStreamChat.jsx` into a shared helper.
- Use that shared helper from both `ClaudeStreamChat` and `PiBackendAdapter`.
- Handle `exec_bash` as the backend PI name for the same visual treatment as the existing bash renderer.

This is important: the backend PI path should not grow its own second renderer registry. The codebase already has the correct UI vocabulary for bash, read, write, edit, glob, and grep.

#### 3. Upgrade `PiBackendAdapter` From Plain Text To Structured Assistant Parts

Primary file:

- `src/front/providers/pi/backendAdapter.jsx`

Required changes:

- Replace the current `{ role, text }`-only assistant model with a parts-based representation.
- Preserve a plain-text fallback for events that really only contain text.
- Track in-progress tool state during streaming so the user can see a live tool card while PI is still running.
- Preserve structured content in history reloads so reconnecting to a session does not collapse everything back to a plain bubble.

Acceptance:

- A PI `exec_bash` call renders as a tool card while it is in progress.
- stdout and stderr appear in the existing bash renderer instead of disappearing into the final assistant text.
- Reloading or switching back to a session keeps the tool cards visible.

### Suggested Validation

- Add a focused frontend test for `PiBackendAdapter`, likely `src/front/providers/pi/backendAdapter.test.jsx`.
- Add shared helper tests for the extracted tool renderer mapping.
- Add or extend PI service tests so structured history and stream payloads are covered.

## Execution Order

1. Land the post-signup state-machine fix first. That is the main hosted blocker.
2. Land the PI workspace-root fix second. It is functionally broken but isolated to the PI path.
3. Land tool usage rendering third, after the PI stream shape is stable.

## Final Smoke Pass

After all three workstreams land, the hosted regression pass should prove this exact sequence:

1. Sign up in hosted mode.
2. Complete the auth callback and land directly in the created workspace flow.
3. Observe that only one default workspace exists.
4. Wait for setup to finish without refreshing the browser.
5. Create a file from PI via `exec_bash` and confirm it appears in the file tree.
6. Create or edit a file in the file tree and confirm PI can read it from the same relative path.
7. Run another PI tool action and confirm the chat shows the tool card and output, not just the final assistant text.
