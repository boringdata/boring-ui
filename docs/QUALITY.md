# Quality Grades

## Current State (as of Feb 2026)

### Frontend

| Area | Grade | Notes |
|---|---|---|
| Pane Registry | B+ | Well-abstracted, tested (`panes.test.js`). Capability gating works. |
| Layout Persistence | B | Versioned migration, validation, recovery chain. Tested (`LayoutManager.test.js`). |
| App.jsx | C+ | Large file (~82KB). Contains layout, approval, and panel ops that should be extracted. |
| Components | B | FileTree, Editor, Terminal are functional. Some inline styles remain in chat components. |
| Config System | B | Deep merge works. `ConfigProvider` wired. `app.config.js` is sparse but functional. |
| Hooks | B | `useCapabilities`, `useTheme`, `useKeyboardShortcuts` are clean. |
| Transport/Networking | B+ | Recently refactored: `apiBase.js`, `routes.js`, `transport.js`, `controlPlane.js`. |
| Test Coverage (unit) | B- | Registry, layout, keyboard shortcuts, transport tested. Components less covered. |
| Test Coverage (e2e) | C | Playwright tests exist for user-menu flows. More flows needed. |

### Backend

| Area | Grade | Notes |
|---|---|---|
| App Factory | A- | Clean DI, injectable config/storage/approval. Selective router mounting. |
| APIConfig | A- | Path validation, env-based config, security-first design. |
| Capabilities | A- | Registry pattern, backward compat aliases, workspace plugin awareness. |
| Files Module | B+ | Full CRUD, search. Path security enforced via `validate_path()`. |
| Git Module | B | Status, diff, show. Functional but minimal. |
| PTY Module | B | WebSocket PTY with provider selection. Lifecycle endpoints added. |
| Stream Module | B | Claude chat streaming. `stream_bridge.py` is large (~60KB). |
| Approval/Policy | B | In-memory store. Policy enforcement present. |
| Test Coverage | B- | Unit tests exist in `tests/unit/`. Integration coverage could grow. |

### Documentation

| Area | Grade | Notes |
|---|---|---|
| README | A- | Comprehensive: architecture diagrams, API reference, mermaid state diagrams. |
| Extension Guide | A- | Covers pane registry, layout, config, backend routers, capabilities API. |
| AGENTS.md | B+ | Session startup, commands, credentials. Recently restructured. |
| Architecture docs | C | Stubs being filled (this effort). |
| ADRs | D | No formal ADRs recorded yet. Decision log exists in PLAN.md. |

## Known Technical Debt

1. **App.jsx size**: 82KB monolith handles layout, approval, panel ops. Should extract into focused modules.
2. **stream_bridge.py size**: 60KB. Complex Claude streaming logic could be decomposed.
3. **Chat inline styles**: Chat components use inline styles instead of CSS variables/classes.
4. **Build path issue**: Pre-existing `main.jsx` path resolution issue in production build.
5. **Backward compat aliases**: `stream` alias for `chat_claude_code` adds complexity. Clients should migrate.
6. **No formal ADR process**: Decisions documented informally in plan files.
