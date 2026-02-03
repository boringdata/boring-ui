# Feature Migration: Kurt-Core → Boring UI

## Executive Summary

Extract generic components from `kurt-core/web` into `boring-ui` as a **composition-based** web IDE framework. Projects import and compose components - no plugin system.

### Design Principle: Composition Over Configuration
- **Frontend**: Export reusable React components. Projects compose their own `App.jsx`.
- **Backend**: Export reusable FastAPI routers. Projects compose their own `server.py`.
- **All panes optional**: Left, middle, right, bottom - projects choose what they need.

### Packaging Strategy
- **NPM Package**: Rename from `kurt-web` to `boring-ui`, add library build via Vite
- **Python Package**: Create `boring_ui/` package with `pyproject.toml` for pip install
- **Monorepo**: Single repo with both JS and Python packages

---

## What Boring UI Already Has (Frontend)

| Component | Location | Export For Composition |
|-----------|----------|------------------------|
| **DockLayout** | `src/components/DockLayout.jsx` | Layout wrapper with panel management |
| **FileTree** | `src/components/FileTree.jsx` | File browser with git status |
| **FileTreePanel** | `src/panels/FileTreePanel.jsx` | Panel wrapper for FileTree |
| **Editor** | `src/components/Editor.jsx` | Tiptap editor with diff modes |
| **EditorPanel** | `src/panels/EditorPanel.jsx` | Panel wrapper for Editor |
| **Terminal** | `src/components/Terminal.jsx` | xterm.js terminal |
| **ShellTerminal** | `src/components/ShellTerminal.jsx` | Shell terminal |
| **TerminalPanel** | `src/panels/TerminalPanel.jsx` | Panel wrapper (Claude chat) |
| **ShellTerminalPanel** | `src/panels/ShellTerminalPanel.jsx` | Panel wrapper (shell) |
| **Chat Components** | `src/components/Chat/` | Message, CodeBlock, ToolCard, VoiceInput, etc. |
| **ReviewPanel** | `src/panels/ReviewPanel.jsx` | Approval workflow |
| **ApprovalPanel** | `src/components/ApprovalPanel.jsx` | Approval UI |
| **ConfigProvider** | `src/config/ConfigProvider.jsx` | Config context |
| **Primitives** | `src/components/primitives/` | Alert, Badge, Button, Card, etc. |
| **Hooks** | `src/hooks/` | useTheme, useApi, useGitStatus, useResponsive, etc. |

## What Needs to be Added (Backend)

Create `boring_ui/` Python package with composable FastAPI routers:

| Module | Source | Purpose |
|--------|--------|---------|
| `boring_ui/__init__.py` | New | Package exports |
| `boring_ui/api/__init__.py` | New | API module exports |
| `boring_ui/api/storage.py` | kurt-core `storage.py` | Storage abstraction (Local, S3) |
| `boring_ui/api/file_routes.py` | kurt-core `server.py` `get_tree()`, `get_file()`, etc. | File CRUD + search endpoints |
| `boring_ui/api/git_routes.py` | kurt-core `server.py` `get_git_status()`, `get_git_diff()` | Git operations |
| `boring_ui/api/pty_bridge.py` | kurt-core `pty_bridge.py` | Terminal WebSocket router |
| `boring_ui/api/stream_bridge.py` | kurt-core `stream_bridge.py` | Claude chat WebSocket router |
| `boring_ui/api/approval.py` | kurt-core `server.py` approval endpoints | Approval workflow (pluggable store) |
| `boring_ui/api/app.py` | New | `create_app()` factory for pre-wired FastAPI |
| `pyproject.toml` | New | Python package config |

**Key Design Decisions:**
- Use `create_*_router(config)` factories for all routers (no module-level `router` exports)
- Use FastAPI `Depends()` for dependency injection (storage, auth, workspace root)
- WebSocket routes via `APIRouter().websocket()` - consistent pattern, no `add_websocket_route()`
- All endpoints validate paths against `config.workspace_root` (path traversal protection)
- `create_app()` accepts optional `storage` and `approval_store` for full customization
- Provider names: `shell`, `claude` (mapped internally to actual commands)

---

## Composition Architecture

### How Projects Use Boring UI

**Frontend Example** - Project composes its own App.jsx:
```jsx
// my-project/src/App.jsx
import { DockLayout, FileTreePanel, EditorPanel, TerminalPanel } from 'boring-ui'
import { MyCustomPanel } from './panels/MyCustomPanel'

const components = {
  filetree: FileTreePanel,
  editor: EditorPanel,
  terminal: TerminalPanel,
  custom: MyCustomPanel,  // Add your own panels
}

export default function App() {
  const panels = [
    { id: 'filetree', component: 'filetree', position: 'left' },
    { id: 'editor', component: 'editor', position: 'center' },
    { id: 'terminal', component: 'terminal', position: 'right' },
    { id: 'bottom', component: 'custom', position: 'bottom' },  // Optional
  ]
  return <DockLayout components={components} panels={panels} />
}
```

**Backend Example** - Project composes its own server.py:
```python
# my-project/server.py
from pathlib import Path
from fastapi import FastAPI
from boring_ui.api import (
    APIConfig, LocalStorage,
    create_file_router, create_git_router,
    create_pty_router, create_stream_router,
)
from .my_routes import router as my_router  # Add your own routes

config = APIConfig(workspace_root=Path.cwd())
storage = LocalStorage(config.workspace_root)

app = FastAPI()

# Include generic routers from boring-ui (all use factory functions)
app.include_router(create_file_router(config, storage), prefix="/api")
app.include_router(create_git_router(config), prefix="/api/git")
app.include_router(create_pty_router(config), prefix="/ws")
app.include_router(create_stream_router(config), prefix="/ws")

# Include project-specific routes
app.include_router(my_router, prefix="/api/workflows")
```

---

## Final Directory Structure

```
boring-ui/
├── package.json                      # 🔄 Rename to "boring-ui", add exports field
├── vite.config.js                    # 🔄 Add library build mode
├── pyproject.toml                    # 🆕 Python package config
│
├── src/                              # Frontend (NPM package)
│   ├── index.js                      # 🆕 Public exports
│   ├── components/
│   │   ├── DockLayout.jsx
│   │   ├── FileTree.jsx
│   │   ├── Editor.jsx
│   │   ├── Terminal.jsx
│   │   ├── ShellTerminal.jsx
│   │   ├── Chat/                     # (capitalized)
│   │   └── primitives/
│   ├── panels/
│   ├── config/
│   └── hooks/
│
├── boring_ui/                        # 🆕 Python package
│   ├── __init__.py
│   └── api/
│       ├── __init__.py               # Exports routers + create_app
│       ├── storage.py                # Storage abstraction
│       ├── file_routes.py            # File CRUD + search router
│       ├── git_routes.py             # Git status/diff router
│       ├── pty_bridge.py             # Terminal WebSocket router
│       ├── stream_bridge.py          # Claude chat WebSocket router
│       ├── approval.py               # Approval workflow router
│       ├── app.py                    # create_app() factory
│       └── config.py                 # 🆕 Config dataclass + security defaults
│
└── examples/
    └── minimal/
        ├── src/App.jsx
        └── server.py                 # Uses boring_ui.api.create_app()
```

---

## Implementation Steps

### Step 1: Setup Package Structure

```bash
# Python package
mkdir -p boring_ui/api
touch boring_ui/__init__.py boring_ui/api/__init__.py

# Update package.json name from "kurt-web" to "boring-ui"
```

Create `pyproject.toml`:
```toml
[project]
name = "boring-ui"
version = "0.1.0"
dependencies = ["fastapi>=0.100", "ptyprocess", "websockets"]

[project.optional-dependencies]
s3 = ["boto3"]
```

### Step 2: Create `boring_ui/api/config.py`

Define config dataclass for dependency injection:
```python
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class APIConfig:
    workspace_root: Path
    cors_origins: list[str] = field(default_factory=lambda: ["http://localhost:5173"])

    # Provider names → actual commands (for PTY bridge)
    pty_providers: dict[str, list[str]] = field(default_factory=lambda: {
        "shell": ["bash"],
        "claude": ["claude", "--dangerously-skip-permissions"],
    })

    # Security: validate all file paths against workspace_root
    def validate_path(self, path: Path) -> Path:
        resolved = (self.workspace_root / path).resolve()
        if not resolved.is_relative_to(self.workspace_root):
            raise ValueError("Path traversal detected")
        return resolved
```

### Step 3: Create `boring_ui/api/storage.py`

**Source**: kurt-core `storage.py` - copy `Storage`, `LocalStorage`, `S3Storage` classes
**Change**: Add `workspace_root` validation to prevent path traversal

### Step 4: Create `boring_ui/api/file_routes.py`

**Extract from**: kurt-core `server.py` functions: `get_tree()`, `get_file()`, `put_file()`, `delete_file()`, `rename_file()`, `move_file()`, `search_files()`

```python
def create_file_router(config: APIConfig, storage: Storage) -> APIRouter:
    router = APIRouter()

    @router.get("/tree")
    async def get_tree(path: str = "."):
        # Validate path within workspace_root
        ...

    @router.get("/file")
    @router.put("/file")
    @router.delete("/file")
    @router.post("/file/rename")
    @router.post("/file/move")
    @router.get("/search")

    return router
```

### Step 5: Create `boring_ui/api/git_routes.py`

**Extract from**: kurt-core `server.py` functions: `get_git_status()`, `get_git_diff()`, `get_git_show()`

```python
def create_git_router(config: APIConfig) -> APIRouter:
    router = APIRouter()

    @router.get("/status")
    @router.get("/diff")
    @router.get("/show")

    return router
```

### Step 6: Create `boring_ui/api/pty_bridge.py`

**Source**: kurt-core `pty_bridge.py`

**Changes**:
- Remove `from kurt.db.tenant import ...`
- Remove Kurt CLI provider code (keep `shell`, `claude` providers)
- Use `APIRouter().websocket()` pattern consistently
- Accept config via dependency injection

```python
def create_pty_router(config: APIConfig) -> APIRouter:
    router = APIRouter()

    @router.websocket("/pty")
    async def pty_websocket(websocket: WebSocket, provider: str = "shell"):
        if provider not in config.pty_providers:
            await websocket.close(code=4003, reason=f"Unknown provider: {provider}")
            return

        command = config.pty_providers[provider]  # e.g., ["claude", "--dangerously-skip-permissions"]
        # ... spawn PTY with command, working dir = config.workspace_root
        ...

    return router
```

### Step 7: Create `boring_ui/api/stream_bridge.py`

**Source**: kurt-core `stream_bridge.py`

**Changes**:
- Remove Kurt-specific imports
- Remove `_persist_permission_suggestions()` or make it configurable
- Use `APIRouter().websocket("/stream")` pattern

```python
def create_stream_router(config: APIConfig) -> APIRouter:
    router = APIRouter()

    @router.websocket("/stream")
    async def stream_websocket(websocket: WebSocket):
        ...

    return router
```

### Step 8: Create `boring_ui/api/approval.py`

**Extract from**: kurt-core `server.py` approval-related functions

```python
class ApprovalStore(ABC):
    async def create(self, request_id: str, data: dict) -> None: ...
    async def get(self, request_id: str) -> dict | None: ...
    async def update(self, request_id: str, decision: str) -> None: ...

class InMemoryApprovalStore(ApprovalStore):
    # Default implementation - note: doesn't persist across restarts
    ...

def create_approval_router(store: ApprovalStore) -> APIRouter:
    router = APIRouter()

    @router.post("/approval/request")
    @router.get("/approval/pending")
    @router.post("/approval/decision")

    return router
```

### Step 9: Create `boring_ui/api/app.py`

Factory function for pre-wired FastAPI app (all dependencies injectable):

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

def create_app(
    config: APIConfig | None = None,
    storage: Storage | None = None,
    approval_store: ApprovalStore | None = None,
) -> FastAPI:
    config = config or APIConfig(workspace_root=Path.cwd())
    storage = storage or LocalStorage(config.workspace_root)
    approval_store = approval_store or InMemoryApprovalStore()

    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # All routers use factory functions (consistent pattern)
    app.include_router(create_file_router(config, storage), prefix="/api")
    app.include_router(create_git_router(config), prefix="/api/git")
    app.include_router(create_pty_router(config), prefix="/ws")
    app.include_router(create_stream_router(config), prefix="/ws")
    app.include_router(create_approval_router(approval_store), prefix="/api")

    return app
```

### Step 10: Create Frontend Exports (`src/index.js`)

```javascript
// Components
export { default as DockLayout } from './components/DockLayout'
export { default as FileTree } from './components/FileTree'
export { default as Editor } from './components/Editor'
export { default as Terminal } from './components/Terminal'
export { default as ShellTerminal } from './components/ShellTerminal'

// Panels
export { default as FileTreePanel } from './panels/FileTreePanel'
export { default as EditorPanel } from './panels/EditorPanel'
export { default as TerminalPanel } from './panels/TerminalPanel'
export { default as ShellTerminalPanel } from './panels/ShellTerminalPanel'
export { default as ReviewPanel } from './panels/ReviewPanel'
export { default as EmptyPanel } from './panels/EmptyPanel'

// Chat (note: capitalized directory)
export * from './components/Chat'

// Config
export { ConfigProvider, useConfig } from './config'

// Hooks
export { useTheme } from './hooks/useTheme'
export { useApi } from './hooks/useApi'
export { useGitStatus } from './hooks/useGitStatus'
```

### Step 11: Update `package.json` and `vite.config.js`

**package.json**:
```json
{
  "name": "boring-ui",
  "version": "0.1.0",
  "type": "module",
  "main": "./dist/boring-ui.cjs",
  "module": "./dist/boring-ui.js",
  "exports": {
    ".": {
      "import": "./dist/boring-ui.js",
      "require": "./dist/boring-ui.cjs"
    },
    "./style.css": "./dist/style.css"
  }
}
```

**vite.config.js** - add library build:
```javascript
build: {
  lib: {
    entry: 'src/index.js',
    name: 'BoringUI',
    formats: ['es', 'cjs'],
    fileName: (format) => `boring-ui.${format === 'es' ? 'js' : 'cjs'}`,  // Output: boring-ui.js, boring-ui.cjs
  },
  rollupOptions: {
    external: ['react', 'react-dom']
  },
  cssCodeSplit: false,  // Emit single style.css
}
```

**IMPORTANT**: `src/index.js` must import the CSS for Vite to emit it:
```javascript
import './styles/index.css'  // Required for style.css to be emitted
export { ... }
```

### Step 12: Create Minimal Example

**`examples/minimal/server.py`**:
```python
from boring_ui.api import create_app, APIConfig
from pathlib import Path

config = APIConfig(workspace_root=Path.cwd())
app = create_app(config)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

**`examples/minimal/src/App.jsx`**:
```jsx
import { DockLayout, FileTreePanel, EditorPanel, TerminalPanel } from 'boring-ui'

const components = { filetree: FileTreePanel, editor: EditorPanel, terminal: TerminalPanel }
const panels = [
  { id: 'files', component: 'filetree', position: 'left' },
  { id: 'editor', component: 'editor', position: 'center' },
  { id: 'chat', component: 'terminal', position: 'right' },
]

export default function App() {
  return <DockLayout components={components} panels={panels} />
}
```

---

## Files Summary

### Create New (Python package `boring_ui/`):
| File | Source |
|------|--------|
| `boring_ui/__init__.py` | New - package root |
| `boring_ui/api/__init__.py` | New - exports create_app + routers |
| `boring_ui/api/config.py` | New - APIConfig dataclass |
| `boring_ui/api/storage.py` | kurt-core `storage.py` (Storage, LocalStorage, S3Storage) |
| `boring_ui/api/file_routes.py` | kurt-core `server.py` file endpoints |
| `boring_ui/api/git_routes.py` | kurt-core `server.py` git endpoints |
| `boring_ui/api/pty_bridge.py` | kurt-core `pty_bridge.py` (adapted) |
| `boring_ui/api/stream_bridge.py` | kurt-core `stream_bridge.py` (adapted) |
| `boring_ui/api/approval.py` | kurt-core `server.py` approval endpoints |
| `boring_ui/api/app.py` | New - create_app() factory |
| `pyproject.toml` | New - Python package config |

### Create/Modify (JS package):
| File | Change |
|------|--------|
| `src/index.js` | Create - public exports |
| `package.json` | Rename to "boring-ui", add exports field |
| `vite.config.js` | Add library build mode |

### Create Example:
| File | Purpose |
|------|---------|
| `examples/minimal/server.py` | Backend using create_app() |
| `examples/minimal/src/App.jsx` | Frontend composition |

---

## Verification

1. **Python Package**:
   ```bash
   cd boring-ui
   pip install -e .
   python -c "from boring_ui.api import create_app; print(create_app)"
   ```

2. **Backend**:
   ```bash
   cd examples/minimal
   python server.py
   curl http://localhost:8000/api/tree?path=.
   curl http://localhost:8000/api/git/status
   ```

3. **Frontend**:
   ```bash
   cd boring-ui && npm run build  # Build library
   cd examples/minimal && npm run dev
   ```

4. **Integration Smoke Test** (add to `examples/minimal/test_integration.py`):
   ```python
   import pytest
   from httpx import AsyncClient
   from boring_ui.api import create_app

   @pytest.mark.asyncio
   async def test_api_tree():
       app = create_app()
       async with AsyncClient(app=app, base_url="http://test") as client:
           r = await client.get("/api/tree?path=.")
           assert r.status_code == 200
           assert "entries" in r.json()

   @pytest.mark.asyncio
   async def test_git_status():
       app = create_app()
       async with AsyncClient(app=app, base_url="http://test") as client:
           r = await client.get("/api/git/status")
           assert r.status_code in (200, 404)  # 404 if not a git repo
   ```

5. **E2E Test** (Playwright):
   - File tree loads and shows entries
   - Click file → Editor opens with content
   - WebSocket `/ws/pty` connects
   - WebSocket `/ws/stream` connects
