# Plan: Codex Chat-Centered Surface Redesign

## Status

Draft v1 - 2026-03-28

Requested location: `docs/plan/codex-chat-centered-surface-redesign.md`

Builds on:

- `docs/plans/chat-centered-surface-redesign.md` as the product and interaction brief
- the current shell implementation in `src/front/App.jsx` and related layout modules

This document is the implementation plan. The existing draft in `docs/plans/` remains the design brief and should not be treated as the execution checklist.

---

## Objective

Transform boring-ui from an IDE-first Dockview shell into a chat-first AI agent workspace with three stable regions:

1. a minimal nav rail on the left
2. a permanently visible chat stage in the center
3. a collapsible Surface on the right for artifacts, files, reviews, charts, and documents

The key product change is structural, not cosmetic: chat stops being one dockable pane among many and becomes the primary workspace surface.

---

## Current State Snapshot

The current implementation is still fundamentally Dockview-first:

- `src/front/App.jsx` constructs the workspace around Dockview and the "core panels" pattern: left sidebar panels, `empty-center`, and dockable agent/editor/review panels.
- `src/front/registry/panes.jsx` still models `filetree` as the only essential pane and places `agent` on the right.
- `src/front/hooks/useDockLayout.js` assumes the host shell is a left sidebar plus center content plus right rail collapsible group.
- `src/front/hooks/usePanelActions.js` routes `openFile`, `openPanel`, and similar actions into Dockview panels in the center area.
- `src/front/layout/LayoutManager.js` still persists legacy shell concepts such as `filetree`, `terminal`, and `shell` collapsed state and panel sizes.
- `src/front/panels/AgentPanel.jsx` mounts chat inside a dock panel container instead of as the primary page structure.
- `src/front/providers/pi/sessionBus.js` scopes session coordination by `panelId`, which only makes sense when chat is panel-based.
- `src/front/utils/frontendState.js` publishes generic `open_panels` and `active_panel_id`, but does not describe chat-stage or artifact-surface state explicitly.
- `src/front/providers/pi/chatPanelTools.js` filters out the `artifacts` tool, which is another signal that artifact handling is not first-class in the current shell.

There is already useful groundwork for the redesign:

- `chart-canvas` style center panels already exist as non-editor content, so the app can already open polymorphic "artifact-like" views.
- `open_panel` and `open_file` already exist as UI bridge tools and backend UI-state commands.
- `AgentPanel` already separates runtime choice from presentation, which makes it reusable in a non-Dockview chat stage.

---

## Product Decisions

These decisions keep the redesign tractable and prevent a broad rewrite from becoming directionless:

1. Chat becomes a first-class shell primitive and is always visible on desktop.
2. The Surface is the only place where files, diffs, charts, documents, and future artifacts open.
3. Split chat panes are removed from the primary UX. Session switching replaces multi-chat tiling.
4. Dockview is retained initially only as an implementation detail for Surface artifact tabs and splits, not as the top-level page layout manager.
5. The left file tree stops being a permanent pane and moves into the Surface explorer.
6. The redesign ships behind a feature flag first, with the old shell available until persistence and tests are stable.
7. This track does not change the agent runtime stack. PI native/backend behavior stays intact while the shell around it changes.

---

## Target UX Contract

### 1. Nav Rail

- 48px icon rail pinned to the left
- contains brand, new chat, session history toggle, settings/profile
- may open an adjacent drawer for session history and workspace actions
- does not host the file tree permanently

### 2. Chat Stage

- centered primary content area
- chat is always mounted and cannot be closed like a panel
- session switching changes the active conversation without moving or rebuilding the workspace shell
- message list supports artifact cards that open or focus items in the Surface
- the composer is the dominant action affordance

### 3. Surface

- hidden by default until an artifact is opened
- appears as a floating right-side island
- owns artifact tabs, artifact explorer, and the active viewer
- persists independently from the active chat session
- can render at minimum:
  - code/editor
  - review/approval surfaces
  - chart/table content
  - documents/images later

---

## Architecture Direction

### A. Separate shell concerns from artifact concerns

Today `App.jsx` mixes shell layout, panel orchestration, session behavior, and artifact opening in one Dockview-driven tree. The redesign should split those concerns:

- shell layout: nav rail, chat stage, surface container
- chat session state: active conversation, session list, session switching
- surface state: explorer visibility, width, open artifacts, active artifact
- artifact rendering: viewer selection and tab lifecycle

### B. Keep existing agent adapters, replace their host container

The fastest safe path is to keep:

- `PiNativeAdapter`
- `PiBackendAdapter`
- existing message rendering and tool rendering paths

and move them out of `AgentPanel`'s Dockview framing into a dedicated chat-stage container.

### C. Keep Dockview only where it still adds value

A full Dockview removal is not required for v1. The pragmatic shape is:

- top-level page layout becomes regular React layout and CSS grid/flex
- Dockview remains inside the Surface for artifact tabs and possible split viewers

This preserves existing editor/review/chart panel logic while removing Dockview from the part of the product where it causes the most UX distortion.

### D. Introduce a first-class artifact model

The redesign needs a shared artifact model rather than ad hoc panel IDs. Start with:

```ts
type SurfaceArtifact = {
  id: string
  kind: 'code' | 'review' | 'chart' | 'table' | 'document' | 'image' | 'custom'
  title: string
  source: 'user' | 'agent' | 'system'
  panelComponent?: string
  params?: Record<string, unknown>
  sessionScoped?: boolean
  createdAt: number
}
```

The initial implementation can derive these artifacts from existing panel-opening intents rather than requiring the agent protocol to change first.

### E. Treat session state as session-scoped, not panel-scoped

`sessionBus.js` currently keys everything by `panelId`. In the new shell the stable key should be the active chat workspace context, not a dock panel instance. The session selector, new-session action, and published session state need to move to chat-stage ownership.

---

## Execution Plan

### Phase 0: Baseline, Flag, And Safety Rails

Create a safe delivery envelope before any large shell edits.

Deliverables:

- add a feature flag such as `features.chatCenteredShell`
- add a query override for local development and visual diffing
- capture fresh UI baselines with the existing shell
- freeze a small acceptance matrix for desktop and tablet widths

Primary files:

- `src/front/App.jsx`
- `src/front/config/*`
- `docs/runbooks/UI_BASELINE_INVENTORY.md`

Success criteria:

- old and new shells can coexist behind a switch
- no forced layout reset for users outside the flag

### Phase 1: Extract A New Shell Host From `App.jsx`

Shrink `App.jsx` so it selects between shell implementations instead of owning every layout decision.

Deliverables:

- create a new shell entry such as `src/front/shell/ChatCenteredWorkspace.jsx`
- move nav rail, chat stage, and surface framing into shell-specific components
- keep auth, workspace routing, providers, capabilities loading, and workspace plugin loading in `App.jsx`

Recommended new modules:

- `src/front/shell/ChatCenteredWorkspace.jsx`
- `src/front/shell/NavRail.jsx`
- `src/front/shell/SessionDrawer.jsx`
- `src/front/shell/SurfaceShell.jsx`
- `src/front/shell/useChatSurfaceState.js`

Primary refactors:

- `App.jsx` stops directly rendering top-level `DockviewReact` in chat-centered mode
- `useDockLayout.js` is no longer the root shell controller in chat-centered mode

Success criteria:

- the app can render a static chat-first shell with placeholder content and no broken providers

### Phase 2: Make Chat The Permanent Center Stage

Move the agent experience out of the dock panel model.

Deliverables:

- replace `AgentPanel` framing with a dedicated chat-stage container
- reuse `PiNativeAdapter` and `PiBackendAdapter` inside the chat stage
- move session controls out of the Dockview panel header
- remove the primary "split chat panel" behavior from the new shell

Primary files:

- `src/front/panels/AgentPanel.jsx`
- `src/front/providers/pi/PiSessionToolbar.jsx`
- `src/front/providers/pi/sessionBus.js`
- `src/front/providers/pi/nativeAdapter.jsx`
- `src/front/providers/pi/backendAdapter.jsx`
- `src/front/components/chat/*`

Required behavior changes:

- session state is keyed by workspace plus active chat context, not `panelId`
- new chat creates or switches sessions without creating another dock panel
- chat remains visible even when the Surface is closed

Success criteria:

- there is exactly one visible chat stage in the new shell
- session switching works without any Dockview panel choreography

### Phase 3: Introduce The Surface Controller

Create a dedicated right-side artifact workspace.

Deliverables:

- a `SurfaceShell` state model:
  - open/closed
  - width
  - explorer expanded/collapsed
  - active artifact id
  - open artifact list
- a Surface top bar with tabs and close/toggle actions
- a viewer host that can mount existing artifact-capable panels

Initial artifact types for v1:

- `editor`
- `review`
- `chart-canvas`

Recommended approach:

- keep an internal Dockview instance inside the Surface for artifact tabbing
- map artifact open/focus events to that nested Dockview instance

Primary files:

- `src/front/hooks/usePanelActions.js`
- `src/front/utils/dockHelpers.js`
- `src/front/registry/panes.jsx`
- new `src/front/shell/SurfaceShell.jsx`
- new `src/front/shell/artifacts/*`

Success criteria:

- `openFile` opens code in the Surface instead of the center dock
- review and chart surfaces can also mount inside the Surface
- closing the Surface does not destroy chat state

### Phase 4: Move Filetree And Data Catalog Into The Surface Explorer

Remove the permanent IDE sidebar model.

Deliverables:

- replace the current left sidebar with nav rail plus optional history drawer
- move file browsing and data browsing into a Surface explorer region
- keep `FileTreePanel` and `DataCatalogPanel` logic initially, but render them as explorer sections instead of standalone host panels

Primary files:

- `src/front/panels/FileTreePanel.jsx`
- `src/front/panels/DataCatalogPanel.jsx`
- `src/front/registry/panes.jsx`
- `src/front/hooks/useDockLayout.js`

Structural changes:

- `filetree` is no longer the essential root pane
- the pane registry stops assuming "left/center/right" host placements for the whole application shell
- filetree collapse state is replaced by explorer visibility state

Success criteria:

- the left edge of the app is a nav rail, not a file browser
- files remain reachable through the Surface explorer without feature loss

### Phase 5: Rewire UI Bridge Commands And Artifact Surfacing

The backend and tool bridge must understand the new shell shape.

Deliverables:

- keep `open_panel` working, but route it through a surface-artifact adapter in chat-centered mode
- keep `open_file` working, but always target the Surface
- extend the frontend state snapshot to describe shell state explicitly
- extend UI-state tools so the agent can reason about chat stage vs Surface

Primary files:

- `src/front/utils/frontendState.js`
- `src/server/http/uiStateRoutes.ts`
- `src/server/services/aiSdkTools.ts`
- `src/shared/toolSchemas.ts`
- `src/pi_service/tools.mjs`

Contract additions to consider:

- `shell.mode = "chat-centered"`
- `surface.open`
- `surface.active_artifact_id`
- `surface.open_artifacts`
- `chat.active_session_id`

Backward-compatibility rule:

- continue publishing `open_panels` during the transition, even if new shell metadata is added

Success criteria:

- agent tool calls still work
- backend UI inspection becomes more truthful for the new shell

### Phase 6: Persistence And Migration Strategy

The redesign should not be forced through the old layout persistence model.

Deliverables:

- introduce a chat-centered shell persistence record separate from legacy Dockview host layout
- keep legacy layout storage only for Surface internals if Dockview remains there
- bump `LAYOUT_VERSION` only where legacy host layouts must be invalidated

Primary files:

- `src/front/layout/LayoutManager.js`
- `src/front/integration/layout.test.jsx`
- `src/front/layout/LayoutManager.test.js`

Recommended persistence split:

- shell state:
  - session drawer open/closed
  - surface open/closed
  - surface width
  - surface explorer open/closed
- surface artifact state:
  - artifact tab order
  - active artifact
  - optional nested Dockview snapshot

Migration rule:

- do not attempt a perfect migration from old host Dockview layouts to the new shell
- prefer a one-time reset into the new default shell, while attempting to recover open editor tabs into initial Surface artifacts

Success criteria:

- no legacy `terminal` or `shell` assumptions remain in new-shell persistence
- layout resets are deliberate and versioned

### Phase 7: Visual Language And Interaction Polish

Apply the design brief after structure is working.

Deliverables:

- nav rail sizing and icon treatment
- centered chat column with a stronger composer affordance
- floating Surface island styling
- backdrop blur, layered shadows, inner highlight, softer borders
- keyboard shortcuts for:
  - new chat
  - toggle Surface
  - focus composer
  - command palette

Primary files:

- `src/front/styles.css`
- chat component styles under `src/front/components/chat/*`
- new shell component styles

Important rule:

- do not spend time polishing Dockview chrome globally if Dockview is no longer the top-level shell
- scope Dockview skinning to Surface internals only

Success criteria:

- the product reads visually as a chat workspace, not an IDE with a chat sidebar

### Phase 8: Tests, Baselines, And Rollout

Lock the redesign down before making it the default.

Deliverables:

- update registry and layout tests that still assume `filetree` is the only essential host pane
- add unit tests for the new shell state hook and session drawer behavior
- add tests for artifact open/focus/close flows
- refresh Playwright baseline coverage for desktop and tablet

Tests likely affected:

- `src/front/integration/layout.test.jsx`
- `src/front/layout/LayoutManager.test.js`
- `src/front/__tests__/configLayout.test.js`
- `src/front/__tests__/hooks/useDockLayout.test.js`
- `src/front/__tests__/utils/dockHelpers.test.js`
- `src/front/__tests__/panes-functional.test.jsx`
- `src/front/__tests__/e2e/layout.spec.ts`

Rollout sequence:

1. land behind flag
2. run visual baselines and smoke flows
3. enable for local development by default
4. enable for hosted environments after persistence and tool-bridge validation
5. remove the legacy shell once no active blockers remain

---

## Touch Points Summary

The likely high-change files are:

- `src/front/App.jsx`
- `src/front/registry/panes.jsx`
- `src/front/hooks/useDockLayout.js`
- `src/front/hooks/usePanelActions.js`
- `src/front/layout/LayoutManager.js`
- `src/front/panels/AgentPanel.jsx`
- `src/front/providers/pi/PiSessionToolbar.jsx`
- `src/front/providers/pi/sessionBus.js`
- `src/front/providers/pi/chatPanelTools.js`
- `src/front/utils/frontendState.js`
- `src/server/http/uiStateRoutes.ts`
- `src/server/services/aiSdkTools.ts`
- `src/front/styles.css`

The likely new files are:

- `src/front/shell/ChatCenteredWorkspace.jsx`
- `src/front/shell/NavRail.jsx`
- `src/front/shell/SessionDrawer.jsx`
- `src/front/shell/SurfaceShell.jsx`
- `src/front/shell/useChatSurfaceState.js`
- `src/front/shell/artifacts/*`

---

## Non-Goals

- no agent runtime rewrite
- no attempt to preserve multi-chat split-panel UX in the new shell
- no full Dockview removal in v1 if Surface reuse is faster and safer
- no backend protocol redesign larger than what the UI-state bridge needs
- no big-bang migration of every possible artifact type before the basic Surface works

---

## Risks And Mitigations

#### Risk: `App.jsx` is already overloaded

Mitigation:

- make shell extraction the first real refactor
- avoid mixing shell redesign with unrelated auth or workspace-router changes

#### Risk: legacy layout persistence pollutes the new shell

Mitigation:

- separate shell-state persistence from legacy Dockview layout persistence
- allow a versioned reset rather than over-fitting migrations

#### Risk: agent tooling assumes "open panels" means editor tabs

Mitigation:

- preserve `open_panels` during the transition
- add shell metadata rather than breaking the current tool contract immediately

#### Risk: file browsing regresses when the filetree stops being permanent

Mitigation:

- keep existing file tree logic and move it into the Surface explorer first
- redesign explorer internals only after parity is restored

#### Risk: session switching remains panel-shaped under the hood

Mitigation:

- explicitly rewrite `sessionBus` and toolbar ownership in Phase 2
- do not leave panel identity as a hidden dependency in the new shell

---

## Recommended First Slice

The first implementation slice should be narrow:

1. add the feature flag
2. extract a new shell host from `App.jsx`
3. mount existing PI chat in a permanent center stage
4. create a closed-by-default Surface shell
5. route `open_file` into the Surface

That slice is enough to prove the product direction without yet moving the entire file explorer or finishing every viewer type.
