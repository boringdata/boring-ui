# Plan: Post-Signup Hosted Fixes + PI Workspace-Root Alignment + Tool Rendering Execution Plan

## Status

Draft, grounded to the current repo state on 2026-03-20.

This is intentionally a second plan file. `docs/plans/post-signup-fixes/PLAN.md` already exists, but parts of its root-cause analysis no longer match the current code. This file is the execution plan tied to the tree as it exists today, with implementation notes explicitly separated into "confirmed changes" vs "instrument-first verification" where the current code suggests ambiguity.

## Locked Observations

- `_eager_workspace_provision()` in `auth_router_neon.py` is **awaited** inside the token-exchange handler; the workspace row exists before the response returns, but Fly Machine provisioning runs as a background task.
- `create_workspace_for_user(..., is_default=True)` uses an `ON CONFLICT DO NOTHING` idempotency clause; the frontend POST endpoint calls it with `is_default=False`, bypassing that protection.
- `src/front/App.jsx` fetches capabilities with `useCapabilities({ rootScoped: true })`, and `src/front/pages/WorkspaceSetupPage.jsx` blocks on that root-scoped state even while the browser is already inside `/w/{workspace_id}/setup`.
- `src/back/boring_ui/api/agents/pi_harness.py` already forwards `x-boring-workspace-root`, but `src/pi_service/tools.mjs` ignores that header and falls back to `process.cwd()` / `BORING_UI_WORKSPACE_ROOT`.
- `src/front/providers/pi/backendAdapter.jsx` intentionally flattens messages down to plain text. The richer tool rendering logic already exists in `src/front/components/chat/ClaudeStreamChat.jsx` and the renderer components under `src/front/components/chat/`.
- The duplicate-workspace path is a confirmed frontend race: root redirect logic can treat the initial empty workspace list as authoritative before the first `/api/v1/workspaces` request resolves.
- The setup-page hang is real, but the exact cause of the capabilities stall is not fully proven yet. The current code suggests the hosted setup page is over-coupled to app-shell boot, but we should verify whether failures are due to root-scoped fetch timing, auth/cookie propagation, request scoping, or some combination of those.
- The PI workspace-root mismatch is definitely a correctness bug for per-session / per-workspace behavior even if single-workspace hosted environments sometimes "work by accident" because process-level env vars happen to align.
- The PI streaming/rendering gap is real, but the exact event shapes in `pi-agent-core` must be treated as source-of-truth during implementation. The transport should be designed around normalized structured content, not assumptions about ad hoc event names.

## Goals

- Eliminate the post-signup duplicate-workspace and setup-page deadlock path in hosted mode.
- Make backend PI and the file API operate on the same workspace root.
- Show PI tool calls and tool output in chat by reusing the existing tool renderers.
- Improve determinism, observability, and rollback safety of the hosted signup flow so regressions are diagnosable instead of surfacing as "stuck spinner" failures.

## Non-Goals

- No redesign of the auth UI beyond what is required to fix the broken hosted flow.
- No new PI tool surface. This work should preserve the current `exec_bash`-first model.
- No second chat rendering system. The backend PI path should reuse the existing chat tool-card vocabulary.
- No speculative transport rewrite that depends on undocumented `pi-agent-core` event names without first verifying the actual event contract in the installed package.
- No "papering over" the signup/setup flow with permanent manual escape hatches as the primary fix. Temporary fallback UI is acceptable only as a bounded safety valve.

## Workstream 1: Fix The Post-Signup State Machine

### Current Broken Flow

1. User signs up and reaches the Neon Auth callback.
2. `AuthCallbackPage` posts to `/auth/token-exchange`.
3. The exchange handler calls `_eager_workspace_provision()`, which creates a default workspace with `is_default=True` and fires off Fly Machine provisioning as a background task.
4. The response contains `redirect_uri` (defaults to `/`) but no workspace id.
5. The frontend navigates to `/`, mounts `App.jsx`, starts a capabilities fetch and a workspace list fetch, and runs the root redirect effect, which finds an empty workspace list and auto-creates another workspace with `is_default=False`.
6. If the user reaches `/w/{workspace_id}/setup`, `WorkspaceSetupPage` waits for runtime readiness and then waits again for root-scoped capabilities to become non-pending.
7. The result is the current hosted failure mode: duplicate workspaces, redirect churn, and a setup page that can sit forever on "Loading workspace capabilities..." until the user refreshes.

### Root-Cause Refinement

There are three separate issues here and they should not be conflated:

1. **Confirmed duplicate-create race**
   - This is already understood and should be fixed directly in the root redirect effect.
   - The first empty `workspaceOptions` value is not evidence that the user has zero workspaces.

2. **Confirmed redirect inefficiency**
   - Bouncing through `/` after `/auth/token-exchange` is avoidable because the backend already knows which workspace it selected/created.
   - Even if the `/` path can be made safe, it remains an unnecessary extra state transition for hosted signup.

3. **Partially understood setup capabilities stall**
   - The setup page currently depends on app-shell root-scoped capabilities state while the browser is already in a workspace-scoped route.
   - That coupling is architecturally wrong even if it is not the only cause of the spinner.
   - Before adding any second polling loop, confirm whether the failing condition is:
     - root-scoped fetch running too early,
     - cookie/session propagation after callback navigation,
     - missing `credentials` / auth inclusion,
     - scoping mismatch between root boot and workspace route,
     - or a genuine backend fetch failure.

### Implementation

#### 1. Make Workspace Auto-Create Wait For The First List Fetch

Primary file:

- `src/front/App.jsx`

Required changes:

- Add an explicit first-load state for workspace discovery, for example `workspaceListStatus: "idle" | "loading" | "success" | "error"` rather than inferring state from `workspaceOptions.length`.
- Update `fetchWorkspaceList()` to mark success and failure separately from the `workspaceOptions` array itself.
- Change the root redirect effect so it does nothing until the first workspace-list request has completed successfully or failed definitively.
- Never treat `[]` as "the user definitely has zero workspaces" before that first request resolves.
- Do not auto-create if the list request failed; surface the existing retry/error path instead.
- Keep the existing `autoCreateAttempted` guard, but make it a last-step guard after list resolution, not the main correctness mechanism.
- Add debug logging/telemetry around the root redirect decision path so hosted regressions can distinguish:
  - "list still loading,"
  - "list failed,"
  - "list resolved empty,"
  - "list resolved with one or more workspaces."

Acceptance:

- Hosted login/signup reaches exactly one default workspace for a new user.
- Refresh timing no longer changes whether a duplicate workspace is created.
- The frontend never issues a speculative create-workspace request before the first list fetch has conclusively resolved empty.

#### 2. Return The Eager-Provisioned Workspace From Token Exchange

Primary files:

- `src/back/boring_ui/api/modules/control_plane/auth_router_neon.py`
- `src/front/pages/AuthPage.jsx`

Required changes:

- Extend the `/auth/token-exchange` response payload to include the workspace id selected or created during eager provisioning.
- Include enough shape in the payload for deterministic client behavior, e.g. `workspace_id` and, if useful, a resolved post-auth route.
- Prefer a direct post-callback navigation target such as `/w/{workspace_id}/setup` instead of bouncing through `/`.
- Preserve the existing `redirect_uri` contract for callers that still need it, but let the hosted flow consume the explicit workspace id when present.
- Keep backwards compatibility:
  - if `workspace_id` is present, hosted callback should prefer it;
  - otherwise fall back to the existing redirect path.
- Add server-side logging to record whether token exchange returned an existing workspace or created a new default workspace, without changing user-visible behavior.

Acceptance:

- The verify-email callback no longer needs the `/` redirect dance to discover the target workspace.
- The callback path is deterministic for both first-login and returning-login flows.
- Hosted callback navigation is derived from backend-selected workspace identity, not from a race between app boot and workspace discovery.

#### 3. Decouple Setup Readiness From Root-Scoped App Boot, But Verify The Actual Capabilities Failure

Primary files:

- `src/front/pages/WorkspaceSetupPage.jsx`
- `src/front/hooks/useCapabilities.js`
- `src/front/App.jsx`

Required changes:

- Stop using the root-scoped `capabilitiesPending` prop as the only gate for leaving the setup page.
- The setup page should become self-sufficient at the workspace boundary:
  - it may reuse the existing capabilities hook or a shared helper,
  - but it should resolve capabilities in a workspace-aware way rather than waiting for the root app shell to finish booting.
- Do **not** add a second uncontrolled polling loop that duplicates the existing hook behavior. Prefer extracting a shared fetch/helper path or allowing the hook to run in a workspace-scoped mode.
- Instrument the capabilities fetch path before finalizing the exact control flow:
  - capture status/error class for failed requests,
  - confirm `credentials` behavior,
  - confirm the resolved request URL/origin,
  - confirm whether failures are auth/session, network, or scoping related.
- Add a bounded retry loop and a real error/retry state instead of an infinite spinner.
- If runtime is ready but capabilities are still unavailable after the bounded retry budget, show an actionable fallback state. This may include a temporary "Continue to workspace" escape hatch only if needed as a safety valve, but that fallback is not the primary success path.
- Keep `useCapabilities({ rootScoped: true })` for shell boot where needed, but do not make the hosted setup page depend on that global fetch completing first.

Design constraint:

- The enhanced plan should fix the architecture and improve debuggability, not just mask the symptom.
- The setup page must not remain permanently blocked on data owned by a different route scope.

Acceptance:

- `/w/{workspace_id}/setup` exits automatically once runtime is ready and workspace-scoped capabilities are available.
- Manual browser refresh is no longer required to enter the workspace after hosted signup.
- When capabilities fail, the UI transitions to a bounded failure/retry state with enough instrumentation to identify whether the problem is auth, network, or scoping related.

#### 4. Add Hosted Signup / Setup Observability

Primary files:

- `src/front/pages/WorkspaceSetupPage.jsx`
- `src/front/hooks/useCapabilities.js`
- `src/front/App.jsx`
- `src/front/pages/AuthPage.jsx`
- `src/back/boring_ui/api/modules/control_plane/auth_router_neon.py`

Required changes:

- Add lightweight structured logs / telemetry markers for:
  - token-exchange success,
  - whether eager provisioning selected vs created a workspace,
  - callback navigation target,
  - first workspace-list fetch start/success/error,
  - setup runtime-ready transition,
  - setup capabilities fetch success/error.
- Keep logs narrow and non-sensitive. The goal is to make hosted regressions diagnosable without adding noisy permanent console spam in normal use.

Acceptance:

- A hosted signup failure can be classified from logs without reproducing it under a debugger.
- Duplicate-workspace and stuck-setup reports can be distinguished quickly.

### Suggested Validation

- Extend `src/front/__tests__/AuthPage.test.jsx` with a token-exchange callback case that prefers a returned `workspace_id`.
- Add frontend coverage for the root redirect decision in a focused test, likely a new file alongside existing frontend tests.
- Add setup-page coverage for:
  - runtime ready + capabilities eventually resolve,
  - runtime ready + capabilities fail repeatedly into retry/error state,
  - root-scoped app capabilities still pending while workspace-scoped setup flow succeeds.
- Add hook/helper coverage for workspace-scoped capabilities resolution and bounded retries.
- Extend `tests/unit/test_auth_session_routes.py` for the hosted token-exchange payload shape.
- Extend `tests/smoke/smoke_neon_auth.py` so the hosted signup flow asserts direct workspace landing and no duplicate default workspace.
- Add an end-to-end hosted regression that specifically covers the "slow first workspace-list fetch" path.

## Workstream 2: Make PI And Files Use The Same Workspace Root

### Current Broken Flow

1. `PiHarness` spawns `server.mjs` with `cwd = self._repo_root()` and copies `os.environ`, which may or may not include `BORING_UI_WORKSPACE_ROOT`.
2. `tools.mjs` reads `WORKSPACE_ROOT` once at module load from the env var or falls back to `process.cwd()`.
3. `_proxy_headers()` in the harness sends `x-boring-workspace-root`, but `resolveSessionContext()` never reads it.
4. File API resolves workspace root per request via `resolve_workspace_context()`.
5. Result: PI executes in one root, files serve from another.

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
- Treat process-level `BORING_UI_WORKSPACE_ROOT` as a fallback for compatibility, not as the authoritative source for session correctness.
- Audit any module-level constant root resolution in `tools.mjs` so workspace-root selection is no longer frozen at import time for multi-session use.

Acceptance:

- `exec_bash` defaults to the same directory root that `files/router.py` and `git/router.py` use for the workspace.
- A file created by PI appears in the file tree without path mismatch.
- A file created or edited through the file API is visible to PI from the same relative path.
- Multi-workspace correctness holds even when a single PI sidecar process serves more than one workspace/session over time.

### Environment / Deployment Verification

The implementation above is required regardless of deployment mode, but we should also verify current hosted behavior so the bug is scoped correctly.

Validation tasks:

- Confirm whether Fly workspace machines already inherit `BORING_UI_WORKSPACE_ROOT` as expected.
- Confirm whether the currently observed user bug is:
  - a universal hosted mismatch,
  - a backend-mode/local-mode issue,
  - or a per-session / multi-workspace correctness bug that only surfaces under specific flows.
- Do not block the code fix on this verification. The code should still move to explicit per-session root selection.

### Suggested Validation

- Extend `src/pi_service/tools.test.mjs` to cover `workspaceRoot` resolution from headers and payloads.
- Extend `src/pi_service/tools.test.mjs` to cover precedence order:
  - explicit payload root,
  - header root,
  - env fallback,
  - `process.cwd()` fallback.
- Add a server-level test for session context updates proving that `workspaceRoot` survives across create/context/stream operations.
- Extend `tests/unit/test_pi_harness.py` to assert that the harness forwards `x-boring-workspace-root`.
- Extend `tests/unit/test_workspace_boundary_router_hosted.py` for local-workspace and workspace-scoped PI calls.
- Extend `tests/integration/test_bd_3g1g_6_3_agent_pi_runtime_surface.py` with a same-root file visibility regression case.
- Add one integration test that exercises two distinct workspace roots through the same PI service process/session lifecycle to prevent future regressions.

## Workstream 3: Show PI Tool Usage In Chat

### Current Broken Flow

1. `textFromMessage()` in `src/pi_service/server.mjs` strips assistant messages down to text blocks only.
2. The subscriber in `handleStream()` only sends `delta` SSE events with `{ text }`.
3. `PiBackendAdapter` stores `{ role, text }` messages and renders them as plain bubbles.
4. The tool-card rendering path in `ClaudeStreamChat` is walled off; `PiBackendAdapter` does not share the mapping.

### Implementation

#### 1. Enrich PI SSE Transport

Primary files:

- `src/pi_service/server.mjs`

Required changes:

- Keep plain-text extraction as a fallback, but stop treating it as the primary PI chat transport shape.
- Update the history endpoint so assistant messages can carry structured content blocks.
- Update the SSE stream to emit structured assistant content, including tool calls and tool results, rather than only a joined text string.
- Normalize the PI sidecar payload into a stable frontend shape so consumers do not depend directly on raw `pi-agent-core` internals.
- Verify the actual `pi-agent-core` event contract before finalizing event names and branching logic. In particular:
  - confirm assistant tool-call block type names,
  - confirm where tool-result messages arrive,
  - confirm whether incremental updates come through `message_update`, `message_end`, `turn_end`, or dedicated tool-execution events.
- The transport design should be resilient to those specifics by using a normalization layer in `server.mjs` rather than leaking library-native event shapes straight to the UI.

Design target:

- Server emits a consistent structured message/part vocabulary for the frontend.
- Text-only consumers remain possible through fallback fields, but structured consumers become the primary path.

#### 2. Reuse The Existing Tool Renderer Mapping Instead Of Rebuilding It

Primary files:

- `src/front/components/chat/ClaudeStreamChat.jsx`
- `src/front/providers/pi/backendAdapter.jsx`
- a new shared helper under `src/front/components/chat/`

Required changes:

- Extract the tool-name to renderer mapping out of `ClaudeStreamChat.jsx` into a shared helper.
- Use that shared helper from both `ClaudeStreamChat` and `PiBackendAdapter`.
- Handle `exec_bash` as the backend PI name for the same visual treatment as the existing bash renderer.
- Reuse the existing tool-card vocabulary and existing renderer components as-is wherever possible.
- Avoid creating a backend-PI-only renderer registry or bespoke card component set.

This is important: the backend PI path should not grow its own second renderer registry. The codebase already has the correct UI vocabulary for bash, read, write, edit, glob, and grep.

#### 3. Upgrade `PiBackendAdapter` From Plain Text To Structured Assistant Parts

Primary file:

- `src/front/providers/pi/backendAdapter.jsx`

Required changes:

- Replace the current `{ role, text }`-only assistant model with a parts-based representation.
- Preserve a plain-text fallback for events that really only contain text.
- Track in-progress tool state during streaming so the user can see a live tool card while PI is still running.
- Preserve structured content in history reloads so reconnecting to a session does not collapse everything back to a plain bubble.
- Support normalization from whatever server-side part schema we standardize on, rather than hard-coding raw `toolCall` / provider-native shapes directly into the final renderer.
- Ensure styling/theme variables used by the existing chat renderers are available in the backend PI chat container so the reused components render correctly.

#### 4. Persist Tool Results In History, Not Just The Live Stream

Primary files:

- `src/pi_service/server.mjs`
- `src/front/providers/pi/backendAdapter.jsx`

Required changes:

- Update history serialization so reloading a session preserves structured assistant content and associated tool-result data.
- Ensure completed tool cards still render after refresh or after switching away and back to a session.
- Avoid a design where tool cards are only reconstructible from ephemeral in-memory stream events.

Acceptance:

- A PI `exec_bash` call renders as a tool card while it is in progress.
- stdout and stderr appear in the existing bash renderer instead of disappearing into the final assistant text.
- Reloading or switching back to a session keeps the tool cards visible.
- The frontend renderer is driven by one shared mapping and one shared tool-card vocabulary, not divergent implementations for Claude vs PI.
- The server transport is structured enough that future tool surfaces can be added without reintroducing text flattening.

### Suggested Validation

- Add a focused frontend test for `PiBackendAdapter`, likely `src/front/providers/pi/backendAdapter.test.jsx`.
- Add shared helper tests for the extracted tool renderer mapping.
- Add or extend PI service tests so structured history and stream payloads are covered.
- Add tests that verify:
  - assistant text-only messages still render correctly,
  - an `exec_bash` in-progress state renders before completion,
  - completed tool output survives history reload,
  - unknown tool blocks degrade gracefully into a generic tool card instead of disappearing.

## Execution Order

1. Land the post-signup state-machine fix first. That is the main hosted blocker.
   - First remove the duplicate-create race.
   - In the same tranche, add deterministic token-exchange workspace targeting.
   - Instrument and decouple setup capabilities in a way that proves the remaining failure mode instead of guessing.
2. Land the PI workspace-root fix second.
   - This is functionally broken and should become explicitly per-session even if some hosted environments currently mask the problem.
3. Land tool usage rendering third, after the PI stream normalization layer is stable.
   - Do not wire frontend rendering to raw provider-native events until the server-side structured transport is settled.

## Rollout / Risk Management

Because this touches auth, signup, setup boot, and chat rendering, land behind small, reviewable commits:

1. Workspace list gating + token-exchange payload enhancement.
2. Setup-page scoping/instrumentation and bounded error state.
3. PI workspace-root session propagation.
4. PI stream normalization.
5. Shared renderer extraction + backend adapter structured rendering.

Where practical, keep compatibility shims for:

- old token-exchange responses with no `workspace_id`,
- old text-only PI stream consumers,
- env-based PI workspace root fallback.

## Final Smoke Pass

After all three workstreams land, the hosted regression pass should prove this exact sequence:

1. Sign up in hosted mode.
2. Complete the auth callback and land directly in the created workspace flow.
3. Observe that only one default workspace exists.
4. Wait for setup to finish without refreshing the browser.
5. Create a file from PI via `exec_bash` and confirm it appears in the file tree.
6. Create or edit a file in the file tree and confirm PI can read it from the same relative path.
7. Run another PI tool action and confirm the chat shows the tool card and output, not just the final assistant text.
8. Reload the PI session and confirm previous tool cards remain visible.
9. Repeat signup/setup under artificially delayed first workspace-list fetch and confirm no duplicate workspace is created.
10. Force a capabilities failure and confirm the setup page exits the infinite-spinner path into a bounded retry/error state with actionable diagnostics.
