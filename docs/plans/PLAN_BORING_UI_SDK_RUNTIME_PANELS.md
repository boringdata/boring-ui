# Plan: `@boring/ui` SDK + Runtime Panel Pipeline

## Status

Draft implementation plan for three linked deliverables:

1. Adopt shadcn/ui as the host app's component vocabulary.
2. Expose those primitives as `@boring/ui` for child apps and agent-authored panels.
3. Replace the current Vite-only workspace panel loader with a backend-bundled runtime panel pipeline.

This plan complements [docs/plans/PLAN_SHADCN_MIGRATION.md](/home/ubuntu/projects/boring-ui/docs/plans/PLAN_SHADCN_MIGRATION.md). That document is useful migration context, but this one is the execution plan for the full SDK + runtime-panel architecture.

---

## Why This Work Exists

The current app already has:

- a large hand-written CSS surface in [src/front/styles.css](/home/ubuntu/projects/boring-ui/src/front/styles.css)
- a library entrypoint in [src/front/index.js](/home/ubuntu/projects/boring-ui/src/front/index.js)
- workspace panel discovery in [src/back/boring_ui/api/workspace_plugins.py](/home/ubuntu/projects/boring-ui/src/back/boring_ui/api/workspace_plugins.py)
- frontend workspace panel registration in [src/front/App.jsx](/home/ubuntu/projects/boring-ui/src/front/App.jsx)
- a dev-only dynamic import path in [src/front/workspace/loader.js](/home/ubuntu/projects/boring-ui/src/front/workspace/loader.js)
- a Vite alias for `@workspace` in [vite.config.ts](/home/ubuntu/projects/boring-ui/vite.config.ts)

What it does not have is a stable component SDK that agents already understand, or a production-safe way to load agent-authored JSX panels without depending on the frontend build tool's filesystem alias.

---

## Target End State

By the end of this project:

- common primitives such as buttons, menus, dialogs, inputs, badges, tabs, avatars, and tooltips come from `@boring/ui`
- the host app uses those primitives instead of ad hoc class bundles
- child apps can import `@boring/ui` directly
- a workspace panel author can write `kurt/panels/<name>/Panel.jsx`
- the backend compiles that JSX to ESM within seconds
- the frontend hot-loads the compiled panel into DockView
- the panel can import `react`, `react/jsx-runtime`, `react-dom`, and `@boring/ui`
- compile failures surface as visible panel errors instead of silent load failures

---

## Non-Goals

- Re-skin DockView tab chrome. Keep DockView-specific CSS custom.
- Replace xterm, TipTap, or chat transcript rendering with shadcn primitives.
- Generalize runtime panels to arbitrary npm imports in the first version.
- Introduce a second design language. This is a component-system migration, not a visual redesign.

---

## Decisions To Lock Up Front

### 1. Package strategy

Recommendation:

- keep the current repo package structure
- add `@boring/ui` as the canonical published/imported name
- keep `boring-ui` as a compatibility alias during migration

Reason:

- child apps and existing consumers are less likely to break
- runtime panels get the desired import path immediately
- the repo already has a library build path in [package.json](/home/ubuntu/projects/boring-ui/package.json) and [vite.config.ts](/home/ubuntu/projects/boring-ui/vite.config.ts)

### 2. Runtime import contract

Version 1 should allow only:

- `react`
- `react/jsx-runtime`
- `react-dom`
- `@boring/ui`

Reason:

- this keeps bundling deterministic
- capability reporting stays simple
- agent-authored panels stay portable across child apps

### 3. Host-module mapping

Do not rely on browser import maps as the first implementation.

Recommendation:

- the host app exposes stable globals or stable runtime shim modules for React and `@boring/ui`
- backend-compiled panel bundles import those stable host shims, not internal Vite chunk names

Concrete shape:

- add host runtime shims such as `/__bui/runtime/react.js`, `/__bui/runtime/react-dom.js`, `/__bui/runtime/jsx-runtime.js`, `/__bui/runtime/boring-ui.js`
- each shim re-exports from `window.__boringRuntimeModules`
- the main app sets `window.__boringRuntimeModules = { React, ReactDOM, jsxRuntime, BoringUI }` during boot

This avoids coupling runtime panels to hashed frontend build artifacts.

---

## Architecture Changes

### Current path

1. backend reports `workspace_panes` with relative source paths
2. frontend receives them from `/api/capabilities`
3. frontend imports `@workspace/<path>` in [src/front/workspace/loader.js](/home/ubuntu/projects/boring-ui/src/front/workspace/loader.js)
4. this only works when Vite can see the workspace filesystem

### Target path

1. backend discovers `kurt/panels/*/Panel.jsx`
2. backend builds each panel to an ESM artifact and stores manifest metadata
3. backend reports `workspace_panes` with `module_url`, `hash`, `status`, and optional `error`
4. frontend dynamically imports `module_url`
5. websocket invalidation triggers manifest refresh and panel reload

---

## Work Plan

## Phase 0: Baseline And Contract Lock

Goal:

- inventory the current generic primitive usage
- lock the package/runtime contract before code churn

Tasks:

- audit repeated button, menu, dialog, input, badge, tabs, avatar, and tooltip patterns in:
  - [src/front/App.jsx](/home/ubuntu/projects/boring-ui/src/front/App.jsx)
  - [src/front/components/UserMenu.jsx](/home/ubuntu/projects/boring-ui/src/front/components/UserMenu.jsx)
  - [src/front/components/Tooltip.jsx](/home/ubuntu/projects/boring-ui/src/front/components/Tooltip.jsx)
  - [src/front/panels/TerminalPanel.jsx](/home/ubuntu/projects/boring-ui/src/front/panels/TerminalPanel.jsx)
  - [src/front/panels/EditorPanel.jsx](/home/ubuntu/projects/boring-ui/src/front/panels/EditorPanel.jsx)
  - settings and auth pages
- identify components that remain custom:
  - DockView shell
  - xterm shell
  - TipTap content surface
  - chat transcript/tool rendering
- define the supported runtime panel API:
  - default export is a React component
  - optional named export `meta`
  - no host-private imports

Exit criteria:

- documented inventory of migration targets
- approved runtime import contract
- approved package naming strategy

## Phase 1: Build The `@boring/ui` Foundation

Goal:

- create the shared component SDK and wire shadcn primitives into the repo's token system

Primary files:

- [package.json](/home/ubuntu/projects/boring-ui/package.json)
- [vite.config.ts](/home/ubuntu/projects/boring-ui/vite.config.ts)
- [src/front/styles.css](/home/ubuntu/projects/boring-ui/src/front/styles.css)
- new `src/front/lib/utils.js`
- new `src/front/components/ui/*`
- [src/front/index.js](/home/ubuntu/projects/boring-ui/src/front/index.js)

Tasks:

- add the shadcn utility layer with `cn()`
- install the first component set:
  - `button`
  - `badge`
  - `input`
  - `textarea`
  - `dialog`
  - `dropdown-menu`
  - `tooltip`
  - `avatar`
  - `tabs`
  - `separator`
- bridge shadcn semantic tokens onto existing boring-ui CSS variables instead of introducing a separate palette
- export those primitives from the public library entrypoint
- add package exports for the library CSS entrypoint and UI modules

Exit criteria:

- the app still builds
- `@boring/ui` can be imported by local consumers
- the SDK primitives inherit the existing theme tokens

## Phase 2: Migrate The Host App To The Shared Vocabulary

Goal:

- replace hand-written generic class bundles with `@boring/ui` components

Migration order:

1. buttons and badges
2. dialogs and dropdowns
3. inputs and textareas
4. avatars, tabs, tooltips, separators

Primary targets:

- [src/front/components/UserMenu.jsx](/home/ubuntu/projects/boring-ui/src/front/components/UserMenu.jsx)
- [src/front/components/Tooltip.jsx](/home/ubuntu/projects/boring-ui/src/front/components/Tooltip.jsx)
- [src/front/components/SidebarSectionHeader.jsx](/home/ubuntu/projects/boring-ui/src/front/components/SidebarSectionHeader.jsx)
- [src/front/panels/TerminalPanel.jsx](/home/ubuntu/projects/boring-ui/src/front/panels/TerminalPanel.jsx)
- [src/front/panels/FileTreePanel.jsx](/home/ubuntu/projects/boring-ui/src/front/panels/FileTreePanel.jsx)
- [src/front/panels/ReviewPanel.jsx](/home/ubuntu/projects/boring-ui/src/front/panels/ReviewPanel.jsx)
- [src/front/panels/EditorPanel.jsx](/home/ubuntu/projects/boring-ui/src/front/panels/EditorPanel.jsx)

Rules:

- preserve existing behaviors, shortcuts, aria labels, and panel flow
- keep layout-specific classes when they are about DockView geometry, not generic primitives
- if a primitive needs boring-specific behavior, add a wrapper in `@boring/ui` instead of recreating one-off CSS locally

Exit criteria:

- the host app no longer depends on local generic button/menu/dialog/input implementations
- remaining large CSS blocks are mostly layout, DockView, editor, terminal, or chat specific

## Phase 3: Publish `@boring/ui` For Child Apps

Goal:

- make the shared UI SDK consumable by downstream apps and runtime panels

Primary files:

- [package.json](/home/ubuntu/projects/boring-ui/package.json)
- [src/front/index.js](/home/ubuntu/projects/boring-ui/src/front/index.js)
- [README.md](/home/ubuntu/projects/boring-ui/README.md)
- [docs/EXTENSION_GUIDE.md](/home/ubuntu/projects/boring-ui/docs/EXTENSION_GUIDE.md)

Tasks:

- finalize package exports
- document import examples for child apps
- document CSS import expectations
- verify one child app can consume `@boring/ui` without importing from internal source paths

Exit criteria:

- child apps have a stable import path
- workspace-panel authors have documented allowed imports

## Phase 4: Add Backend Runtime Panel Bundling

Goal:

- compile workspace `Panel.jsx` files to browser-loadable ESM on the backend

Primary files:

- [src/back/boring_ui/api/workspace_plugins.py](/home/ubuntu/projects/boring-ui/src/back/boring_ui/api/workspace_plugins.py)
- [src/back/boring_ui/api/capabilities.py](/home/ubuntu/projects/boring-ui/src/back/boring_ui/api/capabilities.py)
- [src/back/boring_ui/api/app.py](/home/ubuntu/projects/boring-ui/src/back/boring_ui/api/app.py)
- new backend module for panel compilation and manifest state

Tasks:

- add a panel compiler service that:
  - watches `kurt/panels/*/Panel.jsx`
  - invokes `esbuild` via a stable local binary
  - emits ESM with source maps
  - externalizes or rewrites imports for:
    - `react`
    - `react/jsx-runtime`
    - `react-dom`
    - `@boring/ui`
- add manifest state per panel:
  - `id`
  - `name`
  - `source_path`
  - `module_url`
  - `hash`
  - `status`
  - `error`
  - `updated_at`
- add backend routes to serve:
  - panel bundle ESM
  - source maps
  - host runtime shims
- update capabilities so `workspace_panes` includes runtime bundle metadata instead of only relative source paths

Recommended implementation detail:

- use content-hash URLs or query params for cache busting
- keep compile artifacts outside tracked source paths
- preserve source path safety checks already present in [src/back/boring_ui/api/workspace_plugins.py](/home/ubuntu/projects/boring-ui/src/back/boring_ui/api/workspace_plugins.py)

Exit criteria:

- saving a valid `Panel.jsx` causes backend compilation
- capabilities expose a loadable `module_url`
- invalid JSX records a compile error instead of breaking discovery globally

## Phase 5: Replace The Frontend Loader

Goal:

- remove the Vite workspace alias from the runtime-panel path

Primary files:

- [src/front/workspace/loader.js](/home/ubuntu/projects/boring-ui/src/front/workspace/loader.js)
- [src/front/App.jsx](/home/ubuntu/projects/boring-ui/src/front/App.jsx)
- [src/front/hooks/useWorkspacePlugins.js](/home/ubuntu/projects/boring-ui/src/front/hooks/useWorkspacePlugins.js)
- [vite.config.ts](/home/ubuntu/projects/boring-ui/vite.config.ts)

Tasks:

- change `loadWorkspacePanes()` to import backend-served `module_url` values
- handle panel statuses:
  - `ready`
  - `building`
  - `error`
- render a visible error panel when compilation fails
- preserve websocket-based refresh on `plugin_changed`
- after the runtime path is stable, remove `@workspace` from the production panel-loading path

Exit criteria:

- runtime panels load without the `@workspace` alias
- the same flow works in development and production
- a broken panel fails locally and visibly without taking down the rest of DockView

## Phase 6: Rollout, Tests, And Docs

Goal:

- prove the new architecture is stable before removing old paths

Tests:

- frontend unit tests for shared wrappers and loader status handling
- backend tests for:
  - discovery
  - path validation
  - compile success
  - compile failure
  - manifest generation
  - cache invalidation
- integration test for:
  - write `Panel.jsx`
  - backend compiles
  - websocket fires
  - DockView renders panel
- regression tests for host app primitives after migration

Docs:

- update [docs/EXTENSION_GUIDE.md](/home/ubuntu/projects/boring-ui/docs/EXTENSION_GUIDE.md) with runtime panel authoring rules
- document the `@boring/ui` public surface
- document compile errors and debugging flow

Rollout order:

1. host app consumes `@boring/ui`
2. one child app consumes `@boring/ui`
3. one example runtime panel imports `@boring/ui`
4. remove dead CSS classes and old loader behavior

Exit criteria:

- one child app uses the SDK
- one runtime panel imports `@boring/ui` and appears in DockView within seconds
- the old Vite-only runtime path is no longer required

---

## Risks And Mitigations

### Risk: visual churn during migration

Mitigation:

- migrate by primitive category
- keep boring-ui design tokens as the visual source of truth
- do not mix redesign work into this project

### Risk: runtime bundles accidentally depend on internal frontend chunks

Mitigation:

- use stable host shim modules or globals
- do not import runtime panels directly from hashed app bundle artifacts

### Risk: compile failures create blank or missing panels

Mitigation:

- expose panel build status in capabilities
- add explicit error-state panels for failed runtime modules

### Risk: package rename breaks existing consumers

Mitigation:

- dual-publish or maintain a compatibility alias during the transition

---

## Definition Of Done

This project is done when all of the following are true:

- boring-ui's common primitive surface is implemented through `@boring/ui`
- child apps can import `@boring/ui` without reaching into internal source paths
- runtime workspace panels load from backend-compiled ESM, not the Vite filesystem alias
- runtime panels can import `react` and `@boring/ui` through stable host mappings
- DockView hot-loads a changed `Panel.jsx` within seconds
- compile failures are visible and diagnosable in the UI
