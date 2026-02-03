# Extensibility Plan (boring-ui)

## Goals
1. Make the app truly composable: new panes, panels, and workflows can be added without touching core layout logic.
2. Make the backend pluggable: add/replace API modules (e.g., documents, workflows, search providers) with clear interfaces.
3. Make branding & theming configurable: app name, logo, colors, typography, layout presets.
4. Make integration simple: minimal config for embedding and for running standalone.

## Phase 0 — Baseline Inventory (short, confirm scope)
1. Enumerate current core panes: file tree, editor, terminal, shell, review, empty.
2. Enumerate existing backend routes in `boring_ui/api`.
3. Enumerate current config/env knobs: `VITE_API_URL`, `VITE_CONFIG_PATH`, etc.
4. Confirm which kurt-core features to keep: approval flow, file tree, git, shell, editor, Claude stream.

## Phase 1 — Core Extension Points (frontend)
1. Pane registry
   - Extract `components` / `KNOWN_COMPONENTS` / `ESSENTIAL_PANELS` into a registry module.
   - Registry API:
     - `registerPane({ id, title, component, icon, placement, defaultGroup })`
     - `getPane(id)`, `listPanes()`, `isEssential(id)`.
2. Layout presets
   - Define named presets (e.g., `default`, `coding`, `review`, `docs`) with JSON layout configs.
   - Add `VITE_LAYOUT_PRESET` or `app.config.json` selection.
3. Dockview abstraction
   - Encapsulate Dockview creation in a `LayoutManager` module.
   - Provide hooks: `onLayoutInit`, `onPanelAdded`, `onPanelRemoved`.
4. Panel factory
   - Create `openPanel({ type, params, position })` with type validation.
   - Support new panel types without editing `App.jsx`.

## Phase 2 — Pane Types (deferred)
1. No new panes in the initial extensibility pass.
2. Revisit once registry + layout + capability flags are stable.

## Phase 3 — Backend API Extensibility
1. Router registry
   - Introduce `create_app(..., routers=[...])` or a plugin list in config.
   - Each router advertises: name, prefix, tags, required capabilities.
2. Capability discovery endpoint
   - `GET /api/capabilities` returns features + router availability for UI.
3. Standard endpoints
   - `GET /api/health` (already exists)
   - `GET /api/config` (extend to include UI branding + features)
   - `GET /api/project` (already exists)
   - `GET /api/sessions` / `POST /api/sessions` (already exists)
4. Optional modules (pluggable)
   - `documents` CRUD
   - `workflow` queue + status
   - `indexing` + `search` providers
   - `settings` (per-user / per-project)

## Phase 4 — Branding & Theming
1. Branding config
   - Add `app.config.json` (or `app.config.ts`) with:
     - `appName`, `logo`, `favicon`, `colorTokens`, `typography`, `layoutPreset`.
2. Theming pipeline
   - CSS variables generated from config (light/dark).
   - Optional `theme.css` override per deployment.
3. Runtime theming
   - Allow theme switching via config or UI toggle.
   - Persist user preference in localStorage.

## Phase 5 — Embedding & Integration
1. Create a minimal embed mode
   - `?embed=1` hides header + sidebars optionally.
2. Multi-workspace support
   - Add query param `?root=/path` or `?workspace=id` (backend validates).
3. External extensions
   - Load extension manifests (local JSON or URL) with strict allowlist.

## Phase 6 — Quality & Observability
1. Add structured logging in backend (session spawn failures, CLI errors).
2. Add a `DiagnosticsPanel` with:
   - API status, WS status, session info, config.
3. Add tests for:
   - Pane registry
   - Layout preset loading
   - Capability discovery UI

## Proposed File/Module Changes
1. `src/registry/panes.ts` or `src/registry/panes.js` (pane registry)
2. `src/layout/LayoutManager.ts` (layout abstraction)
3. `src/config/appConfig.ts` (branding + features)
4. `src/components/panels/*` for new panel types
5. `boring_ui/api/capabilities.py` (capabilities router)
6. `boring_ui/api/app.py` to accept plugin router list

## Open Questions (need your preference)
1. Do you want **app config** as JSON (`app.config.json`) or TS (`app.config.ts`)?
2. Should **extension manifests** be local-only, or can they be fetched from a URL?
3. Are **documents** the next backend module to add, or do you want a **search** module first?

## Execution Order (recommended)
1. Pane registry + LayoutManager extraction.
2. Capabilities endpoint + app config for branding.
3. Skip new panels initially; focus on stability of registry/config/routers.
4. Add optional modules (documents/search/workflows) behind capability flags.
