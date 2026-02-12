# Boring UI - Directory Structure Guide

## Project Layout

```
boring-ui/
├── src/                              # Source code (frontend + backend)
│   ├── front/                        # React frontend application
│   │   ├── __tests__/                # Frontend test files
│   │   │   ├── components/           # Component unit tests
│   │   │   ├── fixtures/             # Test data and factories
│   │   │   ├── integration/          # Integration tests
│   │   │   ├── e2e/                  # End-to-end tests
│   │   │   ├── setup.ts              # Test environment setup
│   │   │   └── utils/                # Test utilities and mocks
│   │   ├── components/               # Reusable React components
│   │   │   ├── ApprovalPanel.jsx     # Tool approval UI
│   │   │   ├── CapabilityGate.jsx    # Capability-gating HOC
│   │   │   ├── CodeEditor.jsx        # Code editor wrapper
│   │   │   ├── Editor.jsx            # TipTap markdown editor
│   │   │   ├── FileTree.jsx          # File browser component
│   │   │   ├── FrontmatterEditor.jsx # YAML frontmatter editor
│   │   │   ├── GitChangesView.jsx    # Git changes display
│   │   │   ├── GitDiff.jsx           # Git diff viewer
│   │   │   ├── PaneErrorState.jsx    # Error state for gated panes
│   │   │   ├── Terminal.jsx          # xterm.js wrapper
│   │   │   ├── ThemeToggle.jsx       # Dark/light theme switcher
│   │   │   ├── UserMenu.jsx          # User menu dropdown
│   │   │   ├── chat/                 # Claude chat components
│   │   │   │   ├── ChatPanel.jsx     # Chat interface container
│   │   │   │   ├── ClaudeStreamChat.jsx # Stream message handler
│   │   │   │   ├── MessageList.jsx   # Chat message list
│   │   │   │   ├── SessionHeader.jsx # Chat session header
│   │   │   │   ├── TextBlock.jsx     # Markdown text rendering
│   │   │   │   ├── ToolUseBlock.jsx  # Tool call visualization
│   │   │   │   ├── BashToolRenderer.jsx  # Bash tool display
│   │   │   │   ├── EditToolRenderer.jsx  # Edit tool display
│   │   │   │   ├── GlobToolRenderer.jsx  # Glob tool display
│   │   │   │   ├── GrepToolRenderer.jsx  # Grep tool display
│   │   │   │   ├── ReadToolRenderer.jsx  # Read tool display
│   │   │   │   ├── WriteToolRenderer.jsx # Write tool display
│   │   │   │   ├── PermissionPanel.jsx   # Permission request UI
│   │   │   │   └── styles.css        # Chat component styles
│   │   ├── config/                   # Configuration system
│   │   │   ├── appConfig.js          # Default config + deep merge logic
│   │   │   ├── appConfig.test.js     # Config merging tests
│   │   │   ├── ConfigProvider.jsx    # Config context provider
│   │   │   └── index.js              # Config module exports
│   │   ├── hooks/                    # Custom React hooks
│   │   │   ├── index.js              # Hook exports
│   │   │   ├── useCapabilities.js    # Fetch /api/capabilities
│   │   │   ├── useKeyboardShortcuts.js   # Global keyboard handling
│   │   │   ├── useKeyboardShortcuts.test.js # Shortcut tests
│   │   │   └── useTheme.jsx          # Theme management (dark/light)
│   │   ├── layout/                   # Layout persistence and management
│   │   │   ├── index.js              # Layout module exports and helpers
│   │   │   ├── LayoutManager.js      # Dockview layout persistence
│   │   │   └── LayoutManager.test.js # Layout tests
│   │   ├── panels/                   # Dockview panel wrappers
│   │   │   ├── EditorPanel.jsx       # Editor panel wrapper
│   │   │   ├── EmptyPanel.jsx        # Placeholder panel
│   │   │   ├── FileTreePanel.jsx     # File browser panel
│   │   │   ├── ReviewPanel.jsx       # Approval review panel
│   │   │   ├── ShellTerminalPanel.jsx    # Shell terminal panel
│   │   │   └── TerminalPanel.jsx     # Claude chat panel
│   │   ├── registry/                 # Component registration system
│   │   │   ├── index.js              # Registry exports
│   │   │   ├── panes.js              # Pane registry and definitions
│   │   │   └── panes.test.js         # Pane registry tests
│   │   ├── utils/                    # Utility functions
│   │   │   ├── apiBase.js            # API base URL builder
│   │   │   └── fileIcons.jsx         # File type to icon mapping
│   │   ├── integration/              # Integration test files
│   │   │   └── layout.test.jsx       # Layout integration tests
│   │   ├── App.jsx                   # Main app component
│   │   ├── main.jsx                  # React entry point
│   │   ├── index.js                  # Module exports
│   │   └── styles.css                # Global styles
│   ├── back/                         # Python FastAPI backend
│   │   └── boring_ui/                # Main package
│   │       ├── __init__.py           # Package init
│   │       └── api/                  # API application
│   │           ├── __init__.py
│   │           ├── app.py            # create_app() factory
│   │           ├── approval.py       # Approval store interface + implementation
│   │           ├── capabilities.py   # RouterRegistry + /api/capabilities endpoint
│   │           ├── config.py         # APIConfig dataclass
│   │           ├── file_routes.py    # Legacy file endpoints (deprecated)
│   │           ├── git_routes.py     # Legacy git endpoints (deprecated)
│   │           ├── pty_bridge.py     # Legacy PTY bridge (deprecated)
│   │           ├── storage.py        # Storage interface + LocalStorage impl
│   │           ├── stream_bridge.py  # Legacy stream bridge (deprecated)
│   │           └── modules/          # Modular router implementations
│   │               ├── __init__.py
│   │               ├── files/        # File operations router
│   │               │   ├── __init__.py
│   │               │   ├── router.py     # FastAPI endpoints
│   │               │   ├── service.py    # FileService business logic
│   │               │   └── schemas.py    # Pydantic models
│   │               ├── git/          # Git operations router
│   │               │   ├── __init__.py
│   │               │   ├── router.py     # FastAPI endpoints
│   │               │   ├── service.py    # GitService business logic
│   │               │   └── schemas.py    # Pydantic models
│   │               ├── pty/          # PTY WebSocket router
│   │               │   ├── __init__.py
│   │               │   ├── router.py     # WebSocket endpoint
│   │               │   └── service.py    # PTYService, session management
│   │               └── stream/       # Claude stream WebSocket router
│   │                   ├── __init__.py
│   │                   ├── router.py     # WebSocket endpoint
│   │                   └── service.py    # StreamSession, Claude CLI bridging
│   └── test/                         # Shared test setup
│       └── setup.ts                  # Global test configuration
├── .planning/                        # Planning and documentation
│   ├── codebase/                     # This directory
│   │   ├── ARCHITECTURE.md           # Architecture guide (this file's subject)
│   │   └── STRUCTURE.md              # This file
│   └── ...
├── docs/                             # User documentation
│   ├── PLAN.md                       # Development plan
│   └── ...
├── examples/                         # Example applications
├── public/                           # Static assets
├── dist/                             # Build output
├── node_modules/                     # npm dependencies
├── .venv/                            # Python virtual environment
├── .github/                          # GitHub workflows and config
├── .storybook/                       # Storybook configuration
├── .pytest_cache/                    # pytest cache
├── .bead/                            # Bead task tracking
├── test-results/                     # Test output
├── poc/                              # Proof-of-concept experiments
├── README.md                         # Project readme
├── app.config.js                     # User app configuration (example)
├── app.config.test.js                # Test config
├── eslint.config.js                  # ESLint configuration
├── tsconfig.json                     # TypeScript configuration
├── tailwind.config.js                # Tailwind CSS configuration
├── vite.config.ts                    # Vite build configuration
├── vitest.config.ts                  # Vitest test configuration
├── playwright.config.js              # Playwright E2E test config
├── pyproject.toml                    # Python package configuration
├── package.json                      # npm package configuration
├── package-lock.json                 # npm lock file
├── uv.lock                           # UV package lock file
├── index.html                        # HTML entry point
├── validate-epic.js                  # Epic validation script
└── .gitignore                        # Git ignore rules
```

## Key Directories

### Frontend Structure (`src/front/`)

#### Entry Points
- **main.jsx**: React app initialization with ConfigProvider
- **App.jsx**: Main application shell with Dockview layout

#### Organization Principles

| Directory | Purpose | Naming Convention |
|-----------|---------|-------------------|
| `components/` | Reusable UI components | PascalCase.jsx, each ~150-300 lines |
| `panels/` | Dockview panel wrappers | PascalCase Panel.jsx |
| `hooks/` | Custom React hooks | useXxxx.js or useXxxx.jsx |
| `layout/` | Layout persistence logic | camelCase.js |
| `registry/` | Component/pane registry | camelCase.js |
| `config/` | Configuration system | camelCase.js or PascalCase.jsx |
| `utils/` | Utility functions | camelCase.js |
| `__tests__/` | Test files | filename.test.js/tsx |

#### Component Naming
- **Hooks**: `use{Feature}.js` (e.g., `useCapabilities.js`)
- **Components**: `{Name}.jsx` (e.g., `FileTree.jsx`)
- **Panels**: `{Name}Panel.jsx` (e.g., `FileTreePanel.jsx`)
- **Providers**: `{Name}Provider.jsx` (e.g., `ConfigProvider.jsx`)
- **HOCs**: `{Feature}{Pattern}` (e.g., `CapabilityGate.jsx`)

#### Critical Files
- **registry/panes.js**: Pane registry - ADD NEW PANES HERE
- **components/CapabilityGate.jsx**: Capability checking - DO NOT MODIFY
- **config/appConfig.js**: Default configuration - UPDATE DEFAULTS HERE
- **layout/LayoutManager.js**: Layout persistence - MIGRATION LOGIC HERE

### Backend Structure (`src/back/boring_ui/api/`)

#### Entry Points
- **app.py**: `create_app()` factory - PRIMARY ENTRY POINT
- **capabilities.py**: RouterRegistry and /api/capabilities endpoint

#### Organization Principles

| File | Purpose |
|------|---------|
| `app.py` | Application factory and health endpoints |
| `capabilities.py` | Router registry and capabilities endpoint |
| `config.py` | Configuration dataclass and validation |
| `storage.py` | Storage interface and implementations |
| `approval.py` | Approval store interface and implementations |
| `modules/{name}/` | Feature-specific routers and services |

#### Module Pattern

Each module follows:
```
modules/{feature}/
├── __init__.py
├── router.py       # FastAPI router definition
├── service.py      # Business logic
└── schemas.py      # Pydantic request/response models
```

**Example: Files Module**
```
modules/files/
├── router.py
│   - create_file_router() factory
│   - Endpoints: /api/tree, /api/file, /api/file/rename, etc.
│   - Delegates to FileService
├── service.py
│   - FileService class
│   - Methods: list_directory(), read_file(), write_file(), etc.
│   - Handles path validation and Storage delegation
└── schemas.py
    - FileEntry, DirectoryContents, WriteFileRequest, etc.
```

#### Module Dependencies
- Router receives config (and storage if needed)
- Service receives config and storage
- Service calls `config.validate_path()` before all filesystem ops
- Service delegates to Storage interface

#### Critical Files
- **app.py**: Application factory - DO NOT MODIFY CORE LOGIC
- **capabilities.py**: Feature discovery - UPDATE WHEN ADDING ROUTERS
- **config.py**: Security validation - DO NOT WEAKEN PATH CHECKS
- **storage.py**: Storage interface - IMPLEMENT FOR CUSTOM BACKENDS

### Configuration Files

#### Frontend Config
- **app.config.js**: User-provided configuration (project root)
  - Merged with defaults from `config/appConfig.js`
  - Example: `{branding, storage, panels, styles}`

#### Build Config
- **vite.config.ts**: Vite build configuration
- **tailwind.config.js**: Tailwind CSS configuration
- **tsconfig.json**: TypeScript configuration
- **eslint.config.js**: ESLint linting rules

#### Test Config
- **vitest.config.ts**: Frontend unit/integration test config
- **playwright.config.js**: End-to-end test config
- **app.config.test.js**: Test-specific app configuration

#### Backend Config
- **pyproject.toml**: Python package metadata and dependencies
- **src/back/boring_ui/api/config.py**: APIConfig dataclass

### Test Structure

#### Frontend Tests (`src/front/__tests__/`)
```
__tests__/
├── components/      # Component unit tests
├── fixtures/        # Test data factories
├── integration/     # Integration tests (cross-component)
├── e2e/            # End-to-end tests (Playwright)
├── utils/          # Test helpers and mocks
└── setup.ts        # Test environment setup
```

#### Backend Tests (sibling to code)
```
tests/
├── test_files_router.py     # Files router tests
├── test_git_service.py      # Git service tests
├── test_pty_service.py      # PTY service tests
└── ...
```

#### Test Naming
- Test files: `{module}.test.{ext}` or `test_{module}.{ext}`
- Test functions: `test_{feature}_{scenario}`
- Fixtures: factories in `__tests__/fixtures/`

## File Location Quick Reference

### "Where do I add a new pane?"
→ `src/front/registry/panes.js` (register) + `src/front/panels/{Name}Panel.jsx` (implement)

### "Where do I add a new backend router?"
→ Create `src/back/boring_ui/api/modules/{name}/` with router.py, service.py, schemas.py
→ Register in `create_default_registry()` in `capabilities.py`

### "Where is the main app entry point?"
- Frontend: `src/front/main.jsx` (React)
- Backend: `src/back/boring_ui/api/app.py` (create_app() factory)

### "Where is capability gating logic?"
→ `src/front/components/CapabilityGate.jsx` + `src/front/hooks/useCapabilities.js`

### "Where is layout persistence logic?"
→ `src/front/layout/LayoutManager.js`

### "Where is path validation?"
→ `src/back/boring_ui/api/config.py` (APIConfig.validate_path())

### "Where are defaults configured?"
- Frontend: `src/front/config/appConfig.js`
- Backend: `src/back/boring_ui/api/app.py` and specific routers

### "Where are tests?"
- Frontend: `src/front/__tests__/`
- Backend: `tests/` (in git root, or alongside code)

## Naming Conventions

### Frontend Files
- **Components**: PascalCase.jsx (e.g., `FileTree.jsx`, `TerminalPanel.jsx`)
- **Hooks**: camelCase with `use` prefix (e.g., `useCapabilities.js`, `useTheme.jsx`)
- **Utilities**: camelCase.js (e.g., `apiBase.js`, `fileIcons.jsx`)
- **Config**: camelCase.js (e.g., `appConfig.js`)
- **Tests**: same name + `.test.{ext}` suffix (e.g., `FileTree.test.tsx`)

### Backend Files
- **Modules**: snake_case directory (e.g., `files/`, `chat_claude_code/`)
- **Python files**: snake_case.py (e.g., `app.py`, `file_routes.py`)
- **Classes**: PascalCase (e.g., `FileService`, `Storage`, `APIConfig`)
- **Functions**: snake_case (e.g., `create_app()`, `create_file_router()`)
- **Tests**: test_*.py or *_test.py

### URL Paths
- **Core API**: `/api/{resource}/{action}` (e.g., `/api/file`, `/api/file/rename`)
- **Git API**: `/api/git/{action}` (e.g., `/api/git/status`, `/api/git/diff`)
- **WebSockets**: `/ws/{type}` (e.g., `/ws/pty`, `/ws/stream`)

### Configuration Keys
- Camelcase with dots: `branding.name`, `storage.prefix`, `panels.defaults.filetree`
- Underscores for multi-word: `chat_claude_code`, `file_tree`

## Module Dependencies

### Frontend Dependency Graph

```
main.jsx
  ↓
ConfigProvider (config/ConfigProvider.jsx)
  ↓
App.jsx
  ├─ useCapabilities hook (hooks/useCapabilities.js)
  ├─ useConfig hook (config/ConfigProvider.jsx)
  ├─ useTheme hook (hooks/useTheme.jsx)
  ├─ useKeyboardShortcuts hook (hooks/useKeyboardShortcuts.js)
  ├─ CapabilitiesContext provider
  ├─ Dockview layout manager (layout/LayoutManager.js)
  └─ Panel components (panels/*.jsx)
      └─ Wrapped with CapabilityGate (components/CapabilityGate.jsx)
          └─ References pane registry (registry/panes.js)
```

### Backend Dependency Graph

```
app.py create_app()
  ├─ APIConfig (config.py)
  ├─ Storage interface (storage.py)
  │   └─ LocalStorage implementation
  ├─ ApprovalStore interface (approval.py)
  │   └─ InMemoryApprovalStore implementation
  ├─ RouterRegistry (capabilities.py)
  │   ├─ create_file_router() → modules/files/router.py
  │   │   └─ FileService (modules/files/service.py)
  │   │       └─ Storage interface
  │   ├─ create_git_router() → modules/git/router.py
  │   │   └─ GitService (modules/git/service.py)
  │   ├─ create_pty_router() → modules/pty/router.py
  │   │   └─ PTYService (modules/pty/service.py)
  │   ├─ create_stream_router() → modules/stream/router.py
  │   │   └─ StreamSession (modules/stream/service.py)
  │   └─ create_approval_router() → approval.py
  │       └─ ApprovalStore interface
  └─ Capabilities router (capabilities.py)
      └─ RouterRegistry
```

## Code Size Guide

### Component Size
- **Panel components**: 100-300 lines
- **Feature components**: 50-200 lines
- **Utility components**: 20-80 lines
- **HOCs**: 30-100 lines

### Module Size
- **Service class**: 100-400 lines
- **Router file**: 50-200 lines
- **Schemas file**: 20-100 lines

### Config Size
- **appConfig.js**: ~200 lines with comments
- **APIConfig**: ~70 lines

## File Modification Checklist

When adding features, check these files in order:

### Adding a Pane
- [ ] Create component in `src/front/panels/{Name}Panel.jsx`
- [ ] Create components if needed in `src/front/components/`
- [ ] Register in `src/front/registry/panes.js`
- [ ] Add capability requirements to pane config
- [ ] Add tests in `src/front/__tests__/`

### Adding a Backend Feature
- [ ] Create `src/back/boring_ui/api/modules/{name}/` directory
- [ ] Create `router.py` with `create_{name}_router()` function
- [ ] Create `service.py` with business logic
- [ ] Create `schemas.py` with Pydantic models
- [ ] Register in `create_default_registry()` in `capabilities.py`
- [ ] Add tests in `tests/`

### Updating Configuration
- [ ] Modify `src/front/config/appConfig.js` for defaults
- [ ] Create example in `app.config.js`
- [ ] Add comments explaining new options
- [ ] Update README.md with examples

### Adding Storage/Approval Backend
- [ ] Implement Storage or ApprovalStore interface
- [ ] Add tests
- [ ] Document initialization in README
- [ ] Pass to `create_app()` when instantiating

## Summary

Boring UI's directory structure reflects its architecture:

1. **Frontend**: Organized by concern (components, hooks, layout, registry, config)
2. **Backend**: Organized by feature (modules/{name}/ pattern)
3. **Tests**: Colocated with code or in dedicated test directories
4. **Config**: Separate from code, user-configurable

Key principle: **New features added without modifying core app files** (via registry pattern on both frontend and backend).
