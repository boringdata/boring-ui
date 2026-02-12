# Boring UI - Architecture Guide

## Overview

Boring UI is a **composable, capability-gated web IDE framework** that decouples frontend UI composition from backend feature availability. It uses a **registry pattern** on both frontend and backend to enable selective feature composition with graceful degradation when capabilities are unavailable.

### Core Philosophy

- **Composition over configuration**: Panes and routers register themselves into registries
- **Capability gating**: UI components declare requirements; if unmet, error states render instead
- **Dependency injection**: All services receive configuration; no global state
- **Pluggable backends**: Storage, approval store, and PTY providers are interfaces

## Architecture Layers

### Entry Points

#### Frontend Entry Point: `src/front/main.jsx`
- Initializes React app with ConfigProvider wrapper
- Suppresses known xterm.js console errors during layout transitions
- Creates DOM root and renders App component

#### Backend Entry Point: `src/back/boring_ui/api/app.py`
- `create_app()` factory function creates pre-wired FastAPI application
- Accepts optional config, storage, approval store
- Supports selective router composition via `routers` parameter
- Always includes capabilities endpoint

### Data Flow

#### Initialization Sequence

```
1. Frontend: main.jsx
   ↓
2. ConfigProvider (loads app.config.js, merges with defaults)
   ↓
3. App.jsx initializes
   ↓
4. useCapabilities hook fetches /api/capabilities
   ↓
5. CapabilitiesContext updated
   ↓
6. CapabilityGate wraps panes, checks requirements
   ↓
7. Layout restored from localStorage, validated
   ↓
8. Components render with gating applied
```

#### Request Flow Example: File Read

```
Frontend: App.jsx (FileTreePanel)
  ↓
HTTP GET /api/file?path=src/index.js
  ↓
Backend: FastAPI (CORS middleware)
  ↓
files router → files/router.py
  ↓
FileService (src/back/boring_ui/api/modules/files/service.py)
  ↓
Storage abstraction (Storage interface)
  ↓
LocalStorage.read_file() → actual filesystem
  ↓
Response JSON
  ↓
Frontend: FileTree displays file
```

## Frontend Architecture

### Component Hierarchy

```
main.jsx
  └─ ConfigProvider (provides app configuration)
      └─ App.jsx (main shell)
          ├─ DockviewReact (layout container)
          │   ├─ FileTreePanel
          │   ├─ EditorPanel
          │   ├─ TerminalPanel (Claude chat)
          │   ├─ ShellTerminalPanel
          │   ├─ ReviewPanel
          │   └─ EmptyPanel
          │
          └─ System Components
              ├─ ThemeToggle
              ├─ UserMenu (when applicable)
              └─ Keyboard shortcut handlers
```

### Frontend Abstractions

#### 1. Pane Registry (`src/front/registry/panes.js`)

A **registry** that decouples pane component definitions from app logic:

```javascript
registry.register({
  id: 'shell',
  component: ShellTerminalPanel,
  title: 'Shell',
  placement: 'bottom',
  essential: true,
  locked: true,
  requiresRouters: ['pty'],  // Dependency declaration
})
```

**Key Concepts:**
- Each pane declares its backend dependencies via `requiresFeatures` and `requiresRouters`
- `essential` panes must exist in the layout (filetree, terminal, shell)
- `locked` panes can't be closed by the user
- Constraints control minimum/maximum sizes and collapsed state

#### 2. Capability Gating (`src/front/components/CapabilityGate.jsx`)

A **higher-order component** that wraps panes and enforces capability checks:

```javascript
export function createCapabilityGatedPane(paneId, Component) {
  return function CapabilityGatedPane(props) {
    const capabilities = useCapabilitiesContext()

    if (checkRequirements(paneId, capabilities)) {
      return <Component {...props} />
    } else {
      return <PaneErrorState paneId={paneId} missingFeatures={...} />
    }
  }
}
```

**Flow:**
1. `getGatedComponents()` in App.jsx wraps all panes with capability checks
2. CapabilitiesContext provides capabilities from `useCapabilities()` hook
3. For each pane, requirements are checked: `capabilities.features[requirement]`
4. If requirements unmet → PaneErrorState renders (explains what's missing)
5. If requirements met → actual component renders

#### 3. Configuration System (`src/front/config/appConfig.js`)

Provides **deep merge** of user config with defaults:

```javascript
// User's app.config.js (minimal)
export default {
  branding: { name: 'My IDE' },
  storage: { prefix: 'myide' },
}

// Result after merge with defaults
{
  branding: {
    name: 'My IDE',           // user override
    logo: 'B',                // default
    titleFormat: (ctx) => ... // default
  },
  storage: {
    prefix: 'myide',          // user override
    layoutVersion: 1,         // default
  },
  // ... all other defaults preserved
}
```

**Default Config Keys:**
- `branding`: App name, logo, title format
- `fileTree`: Sections, config files, poll intervals
- `storage`: LocalStorage prefix and version
- `panels`: Essential panes, default sizes, constraints
- `api`: Base URL for API calls
- `features`: Feature flags (gitStatus, search, etc.)
- `styles`: CSS variable overrides per theme

#### 4. Layout Management (`src/front/layout/LayoutManager.js`)

Handles **persistence and restoration** of Dockview layout state:

```javascript
// Save layout to localStorage (debounced 300ms)
saveLayout(dockApi.getLayout(), layoutVersion)

// Load layout with validation
const layout = loadLayout()
const valid = validateLayoutStructure(layout)

// Migrate layout if version changed
if (layout.version < LAYOUT_VERSION) {
  migrated = migrateLayout(layout, oldVersion)
}

// Fallback to lastKnownGoodLayout if current is corrupted
if (!valid) {
  layout = loadLastKnownGoodLayout()
}

// Ensure essential panes exist
ensureEssentialPanes(layout)
```

**Key Functions:**
- `saveLayout(layout, version)`: Serialize to localStorage
- `loadLayout()`: Deserialize from localStorage
- `validateLayoutStructure(layout)`: Check for required panes
- `migrateLayout(layout, oldVersion)`: Apply version-specific migrations
- `loadLastKnownGoodLayout()`: Fallback when corruption detected
- `hashProjectRoot(root)`: Generate stable hash for per-project storage

#### 5. Hooks

**`useCapabilities()`** (`src/front/hooks/useCapabilities.js`):
- Fetches `/api/capabilities` endpoint
- Returns `{ capabilities, loading, error, refetch }`
- Sets default empty capabilities on error to prevent blocking

**`useTheme()`** (`src/front/hooks/useTheme.jsx`):
- Manages dark/light theme toggle
- Persists to localStorage
- Sets CSS variables for theme colors

**`useKeyboardShortcuts()`** (`src/front/hooks/useKeyboardShortcuts.js`):
- Handles global keyboard events
- Supports Ctrl/Cmd + key combinations
- Used for panel collapse/expand, etc.

### Key Frontend Components

| Component | Purpose | Dependencies |
|-----------|---------|--------------|
| FileTreePanel | File browser with git status | `files` feature, git status integration |
| EditorPanel | TipTap markdown editor | `files` feature |
| TerminalPanel | Claude chat sessions | `chat_claude_code` router |
| ShellTerminalPanel | Shell terminal | `pty` router |
| ReviewPanel | Tool approval UI | `approval` router |
| EmptyPanel | Placeholder panel | None |

## Backend Architecture

### Application Factory (`src/back/boring_ui/api/app.py`)

The `create_app()` function is the **primary backend entry point**:

```python
def create_app(
    config: APIConfig | None = None,
    storage: Storage | None = None,
    approval_store: ApprovalStore | None = None,
    include_pty: bool = True,
    include_stream: bool = True,
    include_approval: bool = True,
    routers: list[str] | None = None,
    registry: RouterRegistry | None = None,
) -> FastAPI:
```

**Composition Strategy:**
1. Accept optional dependencies (DI pattern)
2. Apply defaults (LocalStorage, InMemoryApprovalStore)
3. Determine enabled routers (from `routers` list or `include_*` flags)
4. Create FastAPI app with CORS middleware
5. Mount enabled routers from registry
6. Add health check and config endpoints
7. Return fully-configured app

**Router Composition:**
```python
enabled_routers = {'files', 'git'}  # Always included

if include_pty:
    enabled_routers.add('pty')
if include_stream:
    enabled_routers.add('chat_claude_code')  # canonical name
if include_approval:
    enabled_routers.add('approval')

# Alternative: explicit list
app = create_app(routers=['files', 'git', 'pty'])
```

### Router Registry (`src/back/boring_ui/api/capabilities.py`)

The **RouterRegistry** enables dynamic router composition and capability discovery:

```python
class RouterRegistry:
    def register(self, name: str, prefix: str, factory: Callable,
                 description: str = "", tags: list[str] = None):
        """Register a router factory"""
        ...

registry = create_default_registry()
entry = registry.get('files')  # Returns (RouterInfo, factory)
```

**Default Registry:**
- `files`: /api - File CRUD operations
- `git`: /api/git - Git operations
- `pty`: /ws - Shell PTY WebSocket
- `chat_claude_code`: /ws - Claude chat WebSocket
- `stream`: /ws - Alias for chat_claude_code (backward compat)
- `approval`: /api - Approval workflow

**Capabilities Endpoint:**
```python
# GET /api/capabilities
{
  "version": "0.1.0",
  "features": {
    "files": true,
    "git": true,
    "pty": true,
    "chat_claude_code": true,
    "approval": false
  },
  "routers": [
    {"name": "files", "prefix": "/api", "description": "...", "enabled": true},
    ...
  ]
}
```

### Configuration (`src/back/boring_ui/api/config.py`)

**APIConfig** dataclass provides **dependency injection** for all routers:

```python
@dataclass
class APIConfig:
    workspace_root: Path
    cors_origins: list[str] = field(default_factory=_default_cors_origins)
    pty_providers: dict[str, list[str]] = field(default_factory=lambda: {
        'shell': ['bash'],
        'claude': ['claude', '--dangerously-skip-permissions'],
    })

    def validate_path(self, path: Path | str) -> Path:
        """CRITICAL: Prevent path traversal attacks"""
        resolved = (self.workspace_root / path).resolve()
        if not resolved.is_relative_to(self.workspace_root.resolve()):
            raise ValueError(f'Path traversal detected: {path}')
        return resolved
```

**Key Concept:** All path operations must call `config.validate_path()` before accessing filesystem.

### Module Architecture

#### Files Module (`src/back/boring_ui/api/modules/files/`)

```
files/
├── router.py       # FastAPI endpoints (/api/tree, /api/file, /api/file/rename, etc.)
├── service.py      # FileService (business logic, path validation)
└── schemas.py      # Pydantic models for request/response bodies
```

**Endpoints:**
- `GET /api/tree` - List directory tree
- `GET /api/file` - Read file
- `PUT /api/file` - Write file
- `DELETE /api/file` - Delete file/directory
- `POST /api/file/rename` - Rename file
- `POST /api/file/move` - Move file

**FileService Pattern:**
1. Router receives request, extracts parameters
2. Calls FileService method (e.g., `service.read_file(path)`)
3. FileService validates path using `config.validate_path()`
4. FileService delegates to Storage interface
5. Router formats response and returns

#### Git Module (`src/back/boring_ui/api/modules/git/`)

```
git/
├── router.py       # FastAPI endpoints (/api/git/status, /api/git/diff, etc.)
├── service.py      # GitService (git command execution)
└── schemas.py      # Response models
```

**Endpoints:**
- `GET /api/git/status` - Git repository status
- `GET /api/git/diff` - Diff between versions
- `GET /api/git/show` - Show file at revision

**GitService Pattern:**
1. Validates workspace is a git repository
2. Runs git commands via subprocess in workspace_root
3. Parses git output (porcelain format for stability)
4. Returns normalized response (e.g., file status → M/A/D/U/C)

#### PTY Module (`src/back/boring_ui/api/modules/pty/`)

```
pty/
├── router.py       # WebSocket endpoint (/ws/pty)
└── service.py      # PTYService (session management, ptyprocess wrapper)
```

**WebSocket Flow:**
1. Client connects to `/ws/pty?session_id=<id>&provider=<name>`
2. Router calls `get_or_create_session()` → PTYService
3. PTYService launches ptyprocess with configured command
4. SharedSession manages concurrent clients sharing same PTY
5. Messages:
   - Client → Server: `{"type": "input", "data": "..."}` or `{"type": "resize", "rows": 24, "cols": 80}`
   - Server → Client: Raw PTY output

**Session Management:**
- Session ID → reuses existing PTY if available
- Multiple clients can connect to same session
- Automatic cleanup of inactive sessions (configurable interval)

#### Stream Module (`src/back/boring_ui/api/modules/stream/`)

```
stream/
├── router.py       # WebSocket endpoint (/ws/stream)
└── service.py      # StreamSession (Claude CLI bridging)
```

**WebSocket Flow:**
1. Client connects to `/ws/stream/{session}?mode=<mode>`
2. Router spawns Claude CLI process with args (built from query params)
3. Reads Claude's JSON stream output
4. Forwards directly to client (transparent bridging)
5. Client messages forwarded to Claude's stdin

**Query Parameters:**
- `session_id`: Session ID (auto-generated if not provided)
- `resume`: Resume existing session
- `force_new`: Terminate existing, start new
- `mode`: UI mode (ask, act, plan) → maps to --permission-mode
- `permissions`: CSV of allowed tool names

### Storage Abstraction (`src/back/boring_ui/api/storage.py`)

**Storage Interface** enables pluggable backends:

```python
class Storage(ABC):
    @abstractmethod
    def list_dir(self, path: Path) -> list[dict]: ...
    @abstractmethod
    def read_file(self, path: Path) -> str: ...
    @abstractmethod
    def write_file(self, path: Path, content: str) -> None: ...
    @abstractmethod
    def delete(self, path: Path) -> None: ...
    @abstractmethod
    def rename(self, old_path: Path, new_path: Path) -> None: ...
    @abstractmethod
    def move(self, src_path: Path, dest_dir: Path) -> Path: ...
    @abstractmethod
    def exists(self, path: Path) -> bool: ...
```

**LocalStorage Implementation:**
- All paths are relative to workspace_root
- `_abs()` method validates paths stay within root
- Raises ValueError for path traversal attempts

### Approval System (`src/back/boring_ui/api/approval.py`)

**ApprovalStore Interface** for pluggable approval backends:

```python
class ApprovalStore(ABC):
    @abstractmethod
    async def create(self, request_id: str, data: dict) -> None: ...
    @abstractmethod
    async def get(self, request_id: str) -> dict | None: ...
    @abstractmethod
    async def update(self, request_id: str, decision: str, reason: str | None) -> None: ...
    @abstractmethod
    async def list_pending(self) -> list[dict]: ...
    @abstractmethod
    async def delete(self, request_id: str) -> bool: ...
```

**Default: InMemoryApprovalStore**
- Stores requests in dict (volatile)
- Suitable for single-process dev
- Does not persist across restarts

**Approval Router Endpoints:**
- `POST /api/approval` - Create approval request
- `GET /api/approval` - List pending requests
- `PUT /api/approval/{id}` - Submit decision (approve/deny)

## Design Patterns

### 1. Registry Pattern

Both frontend and backend use registries for dynamic composition:

**Frontend:**
```javascript
registry.register({id: 'shell', component: ..., requiresRouters: ['pty']})
const components = getGatedComponents(createCapabilityGatedPane)
```

**Backend:**
```python
registry = create_default_registry()
registry.register('files', '/api', create_file_router, ...)
entry = registry.get('files')  # Returns (info, factory)
```

**Benefits:**
- New panes/routers added without touching core app
- Feature discovery via registry
- Selective composition

### 2. Capability Gating

Panes declare requirements; UI checks at render time:

```javascript
// Pane declares needs
requiresFeatures: ['files']
requiresRouters: ['pty']

// Frontend checks
if (capabilities.features['files'] && capabilities.features['pty']) {
  return <ActualComponent />
} else {
  return <PaneErrorState missingFeatures={...} />
}

// Backend advertises
GET /api/capabilities → {features: {files: true, pty: false, ...}}
```

**No Cascading Failures:**
- Frontend gracefully degrades when backend features unavailable
- Error states explain what's missing
- Other panels continue to work

### 3. Dependency Injection

All services receive configuration; no global state:

```python
def create_app(config=None, storage=None, approval_store=None, ...):
    config = config or APIConfig(workspace_root=Path.cwd())
    storage = storage or LocalStorage(config.workspace_root)

    # Routers receive dependencies
    file_router = create_file_router(config, storage)
    git_router = create_git_router(config)
    pty_router = create_pty_router(config)
```

**Benefits:**
- Easy to test (inject mocks)
- Easy to extend (provide custom implementations)
- Clear dependency graph

### 4. Service Layer Pattern

Business logic separated from request handling:

```
router.py (FastAPI endpoints)
  ↓ delegates to
service.py (business logic, validation)
  ↓ delegates to
storage.py or subprocess (actual I/O)
```

**Example Flow:**
```
GET /api/file?path=src/index.js
  → FileRouter.read_file(path)
    → FileService.read_file(path)
      → FileService.validate_and_relativize(path)
      → Storage.read_file(validated_path)
      → LocalStorage.read_file()
        → Path.read_text()
```

### 5. Context API for Capability Gating

Frontend uses React Context to thread capabilities through component tree:

```javascript
<CapabilitiesContext.Provider value={capabilities}>
  <App />
    <CapabilityGatedPane paneId="shell">
      <ShellTerminalPanel />
    </CapabilityGatedPane>
</CapabilitiesContext.Provider>
```

**Flow:**
1. App fetches capabilities via hook
2. Sets CapabilitiesContext value
3. Gated panes access via `useCapabilitiesContext()`
4. Check requirements, render accordingly

## Data Models

### Frontend: Capabilities Object

```javascript
{
  version: "0.1.0",
  features: {
    files: true,            // Feature flag
    git: true,              // Feature flag
    pty: true,              // Router exposed as feature
    chat_claude_code: true, // Router exposed as feature
    stream: true,           // Backward compat alias
    approval: false,        // Router/feature
  },
  routers: [
    {
      name: "files",
      prefix: "/api",
      description: "File system operations",
      enabled: true,
    },
    // ...
  ]
}
```

### Frontend: Pane Config

```javascript
{
  id: "shell",
  component: ShellTerminalPanel,
  title: "Shell",
  icon: "Terminal",
  placement: "bottom",
  essential: true,
  locked: true,
  hideHeader: false,
  constraints: {
    minWidth: 300,
    minHeight: 150,
    collapsedWidth: 48,
    collapsedHeight: 36,
  },
  requiresFeatures: [],
  requiresRouters: ["pty"],
}
```

### Backend: Error Response

```json
{
  "status_code": 400,
  "detail": "Path traversal detected: ../../../etc/passwd"
}
```

### Backend: Git Status Response

```json
{
  "is_repo": true,
  "files": [
    {
      "path": "src/index.js",
      "status": "M"  // M=Modified, A=Added, D=Deleted, U=Untracked, C=Conflict
    },
    {
      "path": "new-file.txt",
      "status": "U"
    }
  ]
}
```

## Extension Points

### 1. Add New Pane

```javascript
// src/front/panels/MyPanel.jsx
export default function MyPanel(props) {
  return <div>{/* ... */}</div>
}

// src/front/registry/panes.js
registry.register({
  id: 'my-pane',
  component: MyPanel,
  title: 'My Pane',
  requiresFeatures: ['files'],
  placement: 'right',
})
```

### 2. Add New Router

```python
# src/back/boring_ui/api/modules/my_feature/router.py
def create_my_router(config: APIConfig) -> APIRouter:
    router = APIRouter()

    @router.get('/my-feature')
    async def my_endpoint():
        return {'data': 'value'}

    return router

# src/back/boring_ui/api/app.py
app = create_app(
    routers=['files', 'git', 'my_feature'],
    registry=custom_registry
)
```

### 3. Add Custom Storage

```python
from src.back.boring_ui.api.storage import Storage

class S3Storage(Storage):
    def read_file(self, path: Path) -> str:
        # Read from S3
        ...

app = create_app(storage=S3Storage())
```

### 4. Custom Approval Store

```python
class RedisApprovalStore(ApprovalStore):
    async def create(self, request_id: str, data: dict) -> None:
        # Store in Redis
        ...

app = create_app(approval_store=RedisApprovalStore())
```

## Security Considerations

### Path Traversal Prevention

All paths must validate via `config.validate_path()`:

```python
def validate_path(self, path: Path | str) -> Path:
    resolved = (self.workspace_root / path).resolve()
    if not resolved.is_relative_to(self.workspace_root.resolve()):
        raise ValueError(f'Path traversal detected: {path}')
    return resolved
```

**Critical:** This check is **mandatory** in every file operation.

### CORS Configuration

Default CORS allows all origins in dev. Restrict in production:

```python
config = APIConfig(
    workspace_root=Path('/my/project'),
    cors_origins=['https://myapp.com', 'https://staging.myapp.com']
)
```

### PTY Provider Validation

Only configured providers can be used:

```python
if provider not in config.pty_providers:
    await websocket.close(code=4003, reason=f'Unknown provider: {provider}')
```

## Performance Considerations

### Layout Persistence

- Dockview layout changes debounced 300ms before saving to localStorage
- Validation checks structure to detect corruption
- `lastKnownGoodLayout` backup prevents cascading failures
- Layout version management enables safe migrations

### Git Operations

- Uses `git status --porcelain` for stable, fast parsing
- Status aggregation with priority: C > D > A > M > U
- Subprocess timeout: 30 seconds

### WebSocket Sessions

- PTY sessions are shared across multiple clients
- Automatic cleanup of inactive sessions
- Session registry prevents unbounded growth
- MAX_SESSIONS limit enforced

## Testing Architecture

### Frontend Tests
- Unit tests: Component rendering, hooks, utils
- Integration tests: Layout persistence, pane registry
- E2E tests: Full app workflows via Playwright

### Backend Tests
- Unit tests: Service layer, git operations
- Integration tests: Routers with mock storage
- E2E tests: Full API flows with real filesystem

## Summary

Boring UI achieves composability through:

1. **Registry Pattern**: Dynamic pane/router registration
2. **Capability Gating**: UI declares needs, backend advertises availability
3. **Dependency Injection**: All services receive configuration
4. **Pluggable Interfaces**: Storage, approval, PTY providers are abstract
5. **Graceful Degradation**: Missing features show error states, don't crash
6. **Clear Separation**: Frontend concerns separate from backend concerns

This architecture enables building minimal apps (files + git only) or full-featured apps with selective feature composition, all with a single codebase.
