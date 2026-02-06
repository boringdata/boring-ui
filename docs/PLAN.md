# Front/Back Restructure + Modular API + Cleanup Plan

## Summary
- Move frontend code into `src/front/` and backend code into `src/back/boring_ui/`.
- Modularize backend API into files, git, pty, and chat-claude-code.
- Keep a clean frontend public API surface aligned with the extension guide.
- Preserve existing behavior while improving composability, layout persistence, and styling tokens.
- Remove non-essential planning/report docs.

## Background and Motivation
This repo has grown organically, and both the frontend UI and backend API are now interleaved in a way that makes extension points harder to understand, test, and evolve. The main pain points this plan addresses are:
- Blurry boundaries between UI and API make it difficult to reason about responsibilities and change impact.
- Build/test tooling references are scattered and depend on legacy paths.
- Layout persistence and styling tokens are partially ad-hoc, which increases regressions when UI structure changes.
- Backend API functionality is too concentrated, limiting modularity and the ability to independently validate feature sets.

The goal is not to redesign the product. The goal is to de-risk future changes and make the current behavior easier to maintain by putting the code into a clear structure with well-defined interfaces.

## Goals
- Clear separation between frontend UI and backend API with explicit boundaries.
- Stable public interfaces for extensions and external users.
- Improved reliability of layout persistence and theming, with predictable recovery behavior.
- Strong regression testing coverage across front and back.

### Success Criteria (Concrete)
- All code in the repo compiles/builds with new paths and no import errors.
- Existing UI behavior is preserved (panes, layouts, chat, git, file tree) with no product-level changes.
- Layouts persist across reloads with versioned migrations and fallback to defaults on invalid data.
- `/api/capabilities` provides correct and consistent feature/routers info, used for essential pane gating.
- CI passes: `npm run test`, `npm run test:e2e`, and `python -m pytest`.

## Non-Goals
- No new product features beyond modularity, cleanup, and robustness.
- No API breaking changes beyond path updates implied by restructuring.
- No UI visual redesign beyond token normalization and necessary CSS variable mappings.

## Guiding Principles
- Preserve behavior: refactors should be behavior-neutral unless explicitly scoped.
- Minimize coupling: frontend and backend should communicate only through HTTP/WS.
- Make contracts explicit: each module and pane should declare its dependencies.
- Fail safe: layout recovery and capability gating should prevent blank screens or crashes.

## Target Structure
```text
/home/ubuntu/projects/boring-ui
├── src
│   ├── front
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   ├── index.js
│   │   ├── components/
│   │   ├── panels/
│   │   ├── layout/
│   │   ├── registry/
│   │   ├── hooks/
│   │   ├── utils/
│   │   ├── config/
│   │   ├── styles.css
│   │   └── __tests__/
│   └── back
│       └── boring_ui
│           ├── __init__.py
│           └── api/
│               ├── __init__.py
│               ├── app.py
│               ├── capabilities.py
│               ├── config.py
│               ├── registry.py
│               └── modules/
│                   ├── files/
│                   │   ├── router.py
│                   │   ├── service.py
│                   │   └── schemas.py
│                   ├── git/
│                   │   ├── router.py
│                   │   ├── service.py
│                   │   └── schemas.py
│                   ├── pty/
│                   │   ├── router.py
│                   │   └── service.py
│                   └── chat_claude_code/
│                       ├── router.py
│                       ├── service.py
│                       ├── schemas.py
│                       └── approval.py
├── docs
│   ├── EXTENSION_GUIDE.md
│   └── PLAN.md
├── examples/
├── public/
├── tests/
└── README.md
```

## Modularity Diagram (ASCII)
```text
Frontend (src/front)                             Backend (src/back/boring_ui)
┌────────────────────────────────────────┐      ┌───────────────────────────────┐
│ Entry: main.jsx                         │      │ API: api/ (FastAPI app)       │
│   └─> App.jsx                            │      │   ├─ registry.py              │
│        ├─> registry/ (pane registry)     │      │   ├─ capabilities.py          │
│        ├─> layout/ (layout manager)      │      │   └─ modules/                 │
│        ├─> config/ (app config)          │      │       ├─ files/               │
│        │    ├─ EditorPanel.jsx           │      │       │   ├─ router.py          │
│        │    ├─ FileTreePanel.jsx         │      │       │   ├─ service.py         │
│        │    ├─ TerminalPanel.jsx         │      │       │   └─ schemas.py         │
│        │    ├─ ShellTerminalPanel.jsx    │      │       ├─ git/                 │
│        │    ├─ ReviewPanel.jsx           │      │       │   ├─ router.py          │
│        │    ├─ EmptyPanel.jsx            │      │       │   ├─ service.py         │
│        │    └─ components/ (shared UI)   │      │       │   └─ schemas.py         │
│        │         ├─> hooks/              │      │       ├─ pty/                 │
│        │         └─> utils/              │      │       │   ├─ router.py          │
│        └─> styles.css                    │      │       │   └─ service.py         │
│                                            │      │       └─ chat_claude_code/    │
│                                            │      │           ├─ router.py        │
│                                            │      │           ├─ service.py       │
│                                            │      │           ├─ schemas.py       │
│                                            │      │           └─ approval.py      │
│                                            Frontend uses API via HTTP + WS
│ Public API: index.js re-exports            ───────────────────────────────────>
│   - registry/                              (No direct code coupling)
│   - layout/
│   - config/
│   - panels/
└────────────────────────────────────────┘
```

## Frontend Specification
- Entry: `src/front/main.jsx` renders `App.jsx`.
- Global styles: `src/front/styles.css`.
- Public API: `src/front/index.js` re-exports registry, layout, config, and selected panes/components.
- Panel placement: TipTap document viewer in `src/front/panels/EditorPanel.jsx` with UI in `src/front/components/Editor.jsx` or `components/DocumentViewer.jsx`.

### Frontend Folder Intent
- `components/`: shared view components that are pane-agnostic.
- `panels/`: high-level dock panes; these are the UI feature surface.
- `layout/`: layout manager, persistence, migrations, and validation.
- `registry/`: pane registry and metadata that powers layout + capability decisions.
- `hooks/`: shared React hooks for app-level cross-cutting behaviors.
- `utils/`: low-level helpers (e.g., debounce, formatting, caching).
- `config/`: app configuration defaults and overrides.

### Frontend Rationale
Separating panes, registry, layout, and config keeps composability predictable and testable. Panels and registry entries should be the only coupling between the UI surface and the rest of the app. All other components should be treated as internal implementation details.

## Registry, Layout, and Config Relationship
```text
Registry (panes.js)          Layout Manager (LayoutManager.js)       App Config (appConfig.js)
┌────────────────────────┐   ┌───────────────────────────────────┐  ┌──────────────────────────┐
│ Pane ID -> Component    │   │ Persists Dockview layout JSON     │  │ Defaults + constraints    │
│ Default placement       │   │ Uses pane IDs to place panes      │  │ Essential panes list      │
│ Size constraints        │   │ Loads/saves per storage prefix    │  │ Default/min/collapsed sz  │
└───────────┬────────────┘   └───────────────┬───────────────────┘  └─────────────┬────────────┘
            │                               │                                  │
            └──────── Pane IDs in layout ───┴────────────── uses defaults ──────┘
```

### Rationale and Considerations
- The registry is the source of truth for pane identity and requirements.
- The layout manager should never render panes that are not registered.
- Config should be the only place to change defaults for layout sizing and essential panes.
- The registry and layout manager should be designed so new panes can be added with minimal boilerplate.

## Composability Rules
- Panes render by default; missing capabilities show a clear error state.
- Optional: gate only essential panes using `/api/capabilities` to avoid blank screens.
- Optional pane metadata: `requiresFeatures` and `requiresRouters`.
- Conventions for new features: backend module, frontend pane, registry entry.

### Error-First UI Behavior
When a pane is missing its required backend feature or router, the UI should render a clear, actionable message rather than silently failing or hiding the pane. This makes environment configuration issues visible and easy to diagnose.

## Styling Contract
- `styles.light` and `styles.dark` drive CSS variables via `ConfigProvider`.
- Map accent tokens to config variables.
- Mapping: `--color-accent: var(--config-accent)`.
- Mapping: `--color-accent-hover: var(--config-accentHover)`.
- Mapping: `--color-accent-light: var(--config-accentLight)`.
- Add token coverage for typography, radius, and surface colors.
- Mapping: `--font-sans`, `--font-mono`, `--radius-md`, `--color-bg-*`, `--color-text-*`.
- Replace inline styles in chat components with CSS classes or CSS variables.

### Styling Rationale
Aligning all styling to variables makes the UI predictable across themes and minimizes regressions when styles are updated. It also simplifies integration for extensions that want to rely on the same tokens.

## Layout Persistence and Recovery
- Persistence uses `storage.prefix` and `storage.layoutVersion`.
- Persisted data includes layout JSON, collapsed state, and panel sizes.
- Layout restoration validates against registered pane IDs.
- Add migration support when `layoutVersion` changes.
- On validation failure, fall back to defaults and record the error.
- Store a `lastKnownGoodLayout` for recovery.

### Layout Recovery Rationale
Layout corruption or outdated data should never block application usability. The system should prefer recovery and default layouts, while keeping enough history for diagnostics.

## Backend Specification
- `api/app.py` wires routers via `registry.py` and exposes `/api/capabilities`.
- Each module exposes a `router.py` factory with `APIConfig` and dependencies.
- Modules: `files`, `git`, `pty`, `chat_claude_code`.
- Approval lives under chat-claude-code.

### Backend Rationale
A modular API structure keeps feature boundaries clear, allows focused tests, and reduces the chance of cross-feature regressions.

## API Contracts
- Files API: `GET /api/tree`, `GET /api/file`, `PUT /api/file`, `DELETE /api/file`, `POST /api/file/rename`, `POST /api/file/move`, `GET /api/search`.
- Git API: `GET /api/git/status`, `GET /api/git/diff`, `GET /api/git/show`.
- PTY API: `WS /ws/pty?session_id=<id>&provider=<name>`.
- Chat-Claude-Code API: `WS /ws/claude-stream` plus `GET /api/sessions` and `POST /api/sessions`.
- Approval API: `/api/approval/request`, `/api/approval/pending`, `/api/approval/decision`, `/api/approval/status/{request_id}`, `/api/approval/{request_id}`.
- Capabilities: `GET /api/capabilities` returns `{ version, features, routers }`.
- Backward compatibility: `stream` remains an alias for `chat_claude_code` until clients migrate.

### Contract Considerations
- Keep response formats consistent with existing clients.
- Prefer additive fields over breaking changes.
- Ensure WS paths remain stable; only module names change under the hood.

## Public API and Tooling Changes
- `index.html` loads `/src/front/main.jsx`.
- Vite alias `@` points to `src/front`.
- Vite library entry points to `src/front/index.js`.
- `tsconfig.json` includes `src/front` only.
- `vitest.config.ts` paths updated to `src/front`.
- `playwright.config.js` `testDir` updated to `src/front/__tests__/e2e`.
- `package.json` lint targets `src/front/`.
- `pyproject.toml` uses src-layout with `packages = ["src/back/boring_ui"]`.
- Pytest adds `src/back` to `sys.path` in `tests/conftest.py`.

### Tooling Rationale
A consistent source layout improves build clarity, makes aliasing explicit, and eliminates implicit path assumptions.

## Documentation Updates
- Update `docs/EXTENSION_GUIDE.md` paths to `src/front/...`.
- Update backend examples in `docs/EXTENSION_GUIDE.md` to `modules/chat_claude_code`.

### Documentation Rationale
Extensions and third-party integrations are sensitive to path changes. Documentation updates ensure compatibility and reduce confusion for external users.

## Testing Strategy (No Regression)
- Backend unit tests for files, git, pty, chat, approval routers.
- Backend integration tests with `create_app()` and temp workspace.
- Backend contract tests for `/api/capabilities` output.
- Frontend unit tests for panes, layout, registry, config wiring.
- Frontend integration tests for layout persistence and pane registration.
- Agent-browser tests via Playwright E2E.
- Agent-browser flow: launch app, open chat, send message, verify response renders.
- Agent-browser flow: create a file on disk, wait/refresh, verify file appears in tree.
- Agent-browser flow: resize panes, reload, verify sizes and open panes persist.
- CI runs `npm run test`, `npm run test:e2e`, and `python -m pytest`.

### Testing Rationale
The refactor touches core infrastructure. A wide testing net prevents subtle regressions and provides confidence during incremental migration.

## Migration Phases
1. Move frontend and backend folders to `src/front` and `src/back/boring_ui`.
2. Update build and test tooling paths.
3. Update Python packaging and pytest path shim.
4. Update docs and examples.
5. Implement composability behavior (error-first, optional gating for essentials).
6. Add layout recovery and styling token expansion.

### Phase Acceptance Criteria
- Phase 1: Code moved and imports updated; app runs without path errors.
- Phase 2: Build/test configs pass on new paths.
- Phase 3: Python packaging resolves and pytest imports work.
- Phase 4: Docs reflect new paths and modules.
- Phase 5: Capabilities and pane gating behave predictably.
- Phase 6: Layout recovery works and styling tokens are consistent.

## Markdown Cleanup (Strict)
- Remove: `EPIC-UI-UX-EXCELLENCE.md`.
- Remove: `EPIC-CHAT-UI-PHASE2-REPORT.md`.
- Remove: `EPIC-CHAT-UI-PLAN.md`.
- Remove: `EPIC-UI-UX-REVIEW.md`.
- Remove: `EPIC-CLAUDE-CODE-CHAT-UI.md`.
- Remove: `EPIC-COMPLETION-REPORT.md`.
- Remove: `EXTENSIBILITY_PLAN.md`.
- Remove: `INTEGRATION-TEST-REPORT.md`.
- Remove: `MIGRATION_PLAN.md`.
- Remove: `RESTART_PLAN.md`.
- Remove: `REVIEW_REQUEST.md`.
- Remove: `reame.md`.
- Remove: `test.md`.
- Keep: `README.md`.
- Keep: `AGENTS.md`.
- Keep: `ACCESSIBILITY.md`.
- Keep: `docs/EXTENSION_GUIDE.md`.
- Keep: `examples/**/README.md`.

### Cleanup Rationale
These documents were intermediate planning artifacts or legacy reports. Removing them reduces noise and keeps current docs focused.

## Assumptions and Defaults
- Front/back composability means a clean public API and clear backend modules.
- Backend import path remains `boring_ui` after moving files.
- Error-first pane behavior is preferred; capability gating only for essentials.
- Chat API is Claude-Code-scoped and owns approval workflow.
- Existing endpoints remain stable unless explicitly called out.

## Risks and Mitigations
- Risk: accidental import path breakages. Mitigation: incremental moves and fast lint/test checks.
- Risk: layout persistence regression. Mitigation: explicit validation and fallback behavior.
- Risk: capabilities gating hides panes incorrectly. Mitigation: error-first default and limited gating to essentials.
- Risk: documentation drift. Mitigation: doc updates included in migration phases and tracked as tasks.

## Rollback Plan
If regressions appear, prioritize reverting to the last known good layout and disabling capability gating. The refactor is structured to be revertible by reversing file moves and restoring prior build/test paths.

## Decision Log
- Decision: Use `src/front` and `src/back/boring_ui` to align with a clean src-layout and avoid name conflicts.
- Decision: Keep `stream` as an alias for `chat_claude_code` to maintain backward compatibility.
- Decision: Gate only essential panes by default to prevent blank screens.
- Decision: Use CSS variables as the source of truth for styling tokens.

---

# Appendix: Code Quality Improvement Ideas

## Summary
Additional improvement ideas identified through codebase analysis. These are independent of the restructuring plan and can be implemented before, during, or after the refactor.

## Selected Improvements (Ranked by Confidence x Impact)

### 1. Add File Type Icons (Confidence: 90%, Impact: Low)
- Add lucide icons per extension in `src/front/components/FileTree.jsx`.
- Update render logic to use `getFileIcon()` helper.

### 2. Use Config Values for Panel Constraints (Confidence: 90%, Impact: Medium)
- Replace hardcoded sizes in `src/front/App.jsx` with `config.panels.*` values.

### 3. Debounce Layout Saves (Confidence: 85%, Impact: Medium)
- Add `src/front/utils/debounce.js` and debounce layout saves in `App.jsx`.

### 4. Add Keyboard Shortcuts (Confidence: 80%, Impact: Medium)
- Create `src/front/hooks/useKeyboardShortcuts.js` and wire to common actions.

### 5. Split App.jsx into Modules (Confidence: 85%, Impact: High)
- Extract layout, approval, and panel operations into dedicated modules under `src/front/layout/` and `src/front/hooks/`.
