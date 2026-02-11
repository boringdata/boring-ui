# Boring UI - Complete Architecture

## System Overview

Boring UI is a web-based IDE that combines file operations, terminal access, and AI chat agents in a single interface. The system is designed as three independent, composable layers:

### Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Browser / Frontend                        │
│              (React + Vite + DockView)                       │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐   │
│  │  FileTree    │  │  Editor      │  │  Chat/Terminal │   │
│  │  Panel       │  │  Shell       │  │  Panel         │   │
│  └──────┬───────┘  └──────┬───────┘  └────────┬───────┘   │
│         │                 │                    │            │
└─────────┼─────────────────┼────────────────────┼────────────┘
          │                 │                    │
          ↓                 ↓                    ↓
    ┌─────────────────────────────────────────────────┐
    │     Boring-UI Backend (FastAPI)                  │
    │     Port 8000 - CONTROL PLANE                    │
    │                                                  │
    │  ┌──────────────┐  ┌──────────────┐            │
    │  │ File API     │  │ Git API      │            │
    │  │ /api/files/* │  │ /api/git/*   │            │
    │  └──────────────┘  └──────────────┘            │
    │                                                  │
    │  ┌──────────────────────────────────────────┐  │
    │  │ Capabilities Router                      │  │
    │  │ /api/capabilities ← Token Distribution   │  │
    │  │ Returns: {services: {token, url, ...}}   │  │
    │  └──────────────────────────────────────────┘  │
    │                                                  │
    │  ┌──────────────────────────────────────────┐  │
    │  │ ServiceTokenIssuer (Auth)                │  │
    │  │ ├─ JWT tokens (HS256)                   │  │
    │  │ ├─ Bearer tokens (plain)                │  │
    │  │ └─ Signing key (in-memory, per-session) │  │
    │  └──────────────────────────────────────────┘  │
    │                                                  │
    │  ┌──────────────────────────────────────────┐  │
    │  │ Subprocess Managers (Lifespan)           │  │
    │  │ ├─ SandboxManager (sandbox-agent)       │  │
    │  │ └─ CompanionManager (Companion server)  │  │
    │  └──────────────────────────────────────────┘  │
    │                                                  │
    └─────────────────────────────────────────────────┘
          │                                    │
          ↓                                    ↓
    ┌──────────────────┐           ┌────────────────────┐
    │  LocalStorage    │           │  Sandbox-Agent     │
    │  Abstraction     │           │  Port 2468         │
    │                  │           │                    │
    │ ├─ Local FS      │           │ ├─ Chat API       │
    │ ├─ Mounted Path  │           │ ├─ Auth: Bearer   │
    │ ├─ Sprites.dev   │           │ └─ Tool Execution │
    │ └─ S3 Storage    │           │                    │
    │                  │           │ Auto-Started By:   │
    │ Impl: storage.py │           │ - SandboxManager  │
    │                  │           │ - Gets bearer token│
    └──────────────────┘           │ - Listens on 2468 │
          │                        │                    │
          ↓                        └────────────────────┘
    WORKSPACE_ROOT
    ├─ Local: /path/to/project
    ├─ Sprites.dev: /home/sprite/workspace
    ├─ Mounted: /mnt/remote
    └─ S3: s3://bucket/prefix
```

## Component Details

### 1. Frontend (Browser Layer)

**Technology Stack**:
- React + Vite for fast development
- DockView for panel layout management
- Zustand for state management
- Playwright for E2E testing

**Key Components**:
```
src/front/
├── App.jsx                          # Main app, layout orchestration
├── main.jsx                         # Entry point, provider config
├── providers/                       # Chat provider registry
│   ├── index.js                     # ChatProviderRegistry
│   ├── claude.js                    # Claude Code provider
│   ├── sandbox.js                   # Sandbox-agent provider
│   ├── companion.js                 # Companion provider
│   └── companion/upstream/          # Upstream Companion source
│       ├── api.ts                   # Modified: added token support
│       └── ws.ts                    # Modified: added auth headers
├── hooks/
│   ├── useServiceConnection.js      # Direct Connect auth + retry logic
│   └── ... (other hooks)
├── panels/
│   ├── FileTreePanel.jsx            # File browser
│   │   └── FilesystemIndicator.jsx  # Visual indicator: local/sandbox/sprites
│   ├── EditorPanel.jsx              # Code editor
│   ├── ShellPanel.jsx               # Shell terminal
│   └── TerminalPanel.jsx            # Chat agent panel
├── components/
│   ├── FilesystemIndicator.jsx      # Shows current filesystem source
│   └── ... (other components)
└── shared/
    ├── renderers/
    │   ├── NormalizedToolResult.js   # Shared tool data contract
    │   └── ToolRendererContext.jsx   # React context for tool rendering
    └── normalizers/                 # Per-provider converters
        ├── claude.js
        ├── sandbox.js
        └── companion.js
```

**Direct Connect Flow**:
```javascript
// 1. Get capabilities with tokens
const caps = await fetch('/api/capabilities')
const sandbox = caps.services.sandbox

// 2. Connect directly to agent
const ws = new WebSocket(sandbox.url, {
  headers: {
    'Authorization': `Bearer ${sandbox.token}`
  }
})

// 3. Agent communicates directly (no proxy)
ws.send(JSON.stringify({type: 'message', text: 'Hello'}))
```

### 2. Backend (Control Plane)

**Technology Stack**:
- FastAPI for REST/WebSocket APIs
- Uvicorn ASGI server
- PyJWT for token signing
- Python 3.9+

**Architecture**:
```
src/back/boring_ui/api/
├── app.py                    # Application factory
│   └─ create_app()          # Configures all routers and managers
├── config.py                 # APIConfig with workspace_root, cors_origins
├── auth.py                   # ServiceTokenIssuer (JWT + bearer tokens)
├── capabilities.py           # Capabilities router (token distribution)
├── storage.py                # Storage abstraction (Local, S3)
├── approval.py               # Approval workflow
├── modules/
│   ├── files/               # File operations router
│   ├── git/                 # Git operations router
│   ├── pty/                 # PTY/shell router
│   ├── stream/              # Claude stream router
│   ├── sandbox/             # Sandbox-agent manager & router
│   │   ├── local.py         # LocalProvider (starts sandbox-agent subprocess)
│   │   └── manager.py       # SandboxManager (lifecycle + token issuance)
│   └── companion/           # Companion server manager & router
│       ├── hono_server.js   # Companion server (Bun + Hono)
│       └── manager.py       # CompanionManager (lifecycle + jwt)
```

**Key Functions**:
```python
def create_app(
    config=None,                # APIConfig with workspace_root
    storage=None,               # Storage implementation (default: LocalStorage)
    include_sandbox=True,       # Enable sandbox-agent
    include_companion=True,     # Enable Companion server
) -> FastAPI:
    """Create configured FastAPI application"""
    # 1. Initialize TokenIssuer (generates signing key)
    token_issuer = ServiceTokenIssuer()

    # 2. Create managers for subprocesses
    sandbox_manager = SandboxManager(...)  # Starts sandbox-agent
    companion_manager = CompanionManager(...)  # Starts Companion

    # 3. Mount routers
    # - File API: /api/files/*
    # - Git API: /api/git/*
    # - Capabilities: /api/capabilities (tokens + service registry)

    # 4. Lifespan management
    # - Startup: Launch subprocesses
    # - Shutdown: Clean up subprocesses

    return app
```

### 3. Agent Layer (Independent Services)

#### Sandbox-Agent (Chat Agent)

**Purpose**: Execute Claude API calls and return AI-powered responses

**Communication**:
- REST API: `/api/v1/*`
- SSE: Server-sent events for streaming responses
- WebSocket: Real-time bidirectional communication
- Authentication: Bearer token (from capabilities endpoint)

**Lifecycle**:
```python
# Backend startup:
1. Generate random bearer token: sandbox_token = os.urandom(24).hex()
2. Start subprocess: subprocess.run(['sandbox-agent', '--token', sandbox_token])
3. Register in capabilities: {url: 'http://host:2468', token: sandbox_token}

# Browser:
1. Fetch /api/capabilities
2. Extract sandbox.token
3. Use in requests: headers={'Authorization': f'Bearer {token}'}

# Agent:
1. Receive request with Bearer token
2. Validate: if token == configured_token: authorize else: 401
```

#### Companion Server (Optional)

**Purpose**: Alternative chat provider using Hono framework

**Communication**:
- REST API: `/api/*`
- WebSocket: `/ws/*`
- Authentication: JWT tokens (from token_issuer)

**Lifecycle**:
```python
# Backend startup:
1. Get signing_key_hex from token_issuer
2. Start Companion: subprocess(['companion', '--signing-key', signing_key_hex])
3. Register in capabilities: {url: 'http://host:3456', token: ''}

# Browser (when connecting):
1. Fetch /api/capabilities (no token needed)
2. Request new JWT from backend
3. Connect to Companion with JWT

# Companion:
1. Receive JWT
2. Verify signature using signing_key
3. Check claims: svc='companion', exp > now
4. If valid: authorize, else: 401
```

### 4. Storage Layer

**Abstract Interface** (`Storage` ABC):
```python
class Storage(ABC):
    def list_dir(path) -> list[dict]
    def read_file(path) -> str
    def write_file(path, content) -> None
    def delete(path) -> None
    def rename(old_path, new_path) -> None
    def move(src_path, dest_dir) -> Path
    def exists(path) -> bool
```

**Implementations**:

1. **LocalStorage** (Most Common)
```python
# Works with ANY filesystem path
def __init__(self, root: Path):
    self.root = Path(root).resolve()
    # root can be:
    # - Local: /home/ubuntu/projects/boring-ui
    # - Sprites.dev: /home/sprite/workspace
    # - Mounted: /mnt/remote-storage
    # - S3: (via S3Storage)
```

2. **S3Storage** (Cloud)
```python
# AWS S3 backend
def __init__(self, bucket: str, prefix: str):
    # Requires: pip install boring-ui[s3]
    # Uses: s3fs for filesystem abstraction
```

**Configuration**:
```python
# Via environment variable
WORKSPACE_ROOT=/home/sprite/workspace  # Can be any path
storage = LocalStorage(Path(os.environ.get('WORKSPACE_ROOT')))

# Via config
config = APIConfig(workspace_root=Path('/my/project'))
```

## Data Flows

### File Operation Flow

```
Browser (FileTree Panel)
    ↓
GET /api/files?path=...
    ↓
Backend (files router)
    ↓
LocalStorage.list_dir(path)
    ↓
Filesystem Access (any source)
    ├─ Local: /home/ubuntu/projects
    ├─ Sprites.dev: /home/sprite/workspace
    ├─ Mounted: /mnt/remote
    └─ S3: s3://bucket/key
    ↓
JSON Response
    ↓
Browser (update FileTree)
```

### Chat Message Flow (Direct Connect)

```
Browser (Terminal Panel)
    │
    ├─ 1. Fetch /api/capabilities
    │      ↓
    │    Backend returns {sandbox: {url, token}}
    │
    ├─ 2. Send message to Sandbox-Agent
    │    POST http://sandbox:2468/api/v1/messages
    │    Headers: Authorization: Bearer <token>
    │      ↓
    │    Sandbox-Agent validates token
    │      ↓
    │    Calls Claude API with ANTHROPIC_API_KEY
    │      ↓
    │    Returns response
    │
    └─ 3. Browser renders agent response
         (No proxy - direct connection)
```

### Token Issuance Flow

```
┌─────────────────────────────────────────────────────────┐
│ Backend Startup                                          │
├─────────────────────────────────────────────────────────┤
│                                                          │
│ token_issuer = ServiceTokenIssuer()                     │
│   → Generates 256-bit random signing_key               │
│   → signing_key_hex = signing_key.hex()                │
│                                                          │
│ Start sandbox-agent subprocess:                         │
│   sandbox_token = os.urandom(24).hex()                 │
│   subprocess(['sandbox-agent', '--token', sandbox_token])
│   → Agent holds this token in memory                   │
│   → Validates all incoming requests                    │
│                                                          │
│ Start Companion subprocess:                             │
│   subprocess(['companion', '--signing-key', signing_key_hex])
│   → Server uses key to verify JWTs                     │
│   → Decodes and validates token claims                 │
│                                                          │
└─────────────────────────────────────────────────────────┘
         │
         │ Browser requests capabilities
         ↓
┌─────────────────────────────────────────────────────────┐
│ GET /api/capabilities                                   │
├─────────────────────────────────────────────────────────┤
│                                                          │
│ Response:                                               │
│ {                                                       │
│   "services": {                                         │
│     "sandbox": {                                        │
│       "url": "http://host:2468",                       │
│       "token": "a1b2c3d4...",  # Bearer token         │
│       "qpToken": "a1b2c3d4...", # Same (for query)    │
│       "protocol": "rest+sse"                           │
│     },                                                  │
│     "companion": {                                      │
│       "url": "http://host:3456",                       │
│       "token": "",  # JWT issued per-request          │
│       "protocol": "rest+sse"                           │
│     }                                                   │
│   }                                                     │
│ }                                                       │
│                                                          │
│ Note: Companion token is empty (browser requests JWT)  │
│       Or: Backend issues JWT via:                       │
│       token = token_issuer.issue_token('companion')    │
│                                                          │
└─────────────────────────────────────────────────────────┘
         │
         │ Browser uses tokens in requests
         ↓
┌─────────────────────────────────────────────────────────┐
│ Direct Agent Requests                                   │
├─────────────────────────────────────────────────────────┤
│                                                          │
│ POST http://sandbox:2468/api/v1/messages               │
│ Headers: Authorization: Bearer a1b2c3d4...            │
│ Body: {message: 'Hello'}                               │
│                                                          │
│ Sandbox-Agent validation:                              │
│ if (request_token == agent_token) {                    │
│   process_message()                                    │
│ } else {                                               │
│   return 401 Unauthorized                             │
│ }                                                      │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## Deployment Scenarios

### Scenario 1: Local Development

```
Your Machine
├─ Frontend: http://localhost:5173 (Vite)
├─ Backend: http://localhost:8000 (FastAPI)
├─ Sandbox-Agent: http://localhost:2468 (Auto-started)
├─ Workspace: /home/ubuntu/projects/boring-ui (Local FS)
└─ ANTHROPIC_API_KEY: Set from environment
```

**Setup**:
```bash
# Terminal 1: Backend
export ANTHROPIC_API_KEY=sk-...
python3 -c "from boring_ui.api.app import create_app; ..."

# Terminal 2: Frontend
npx vite --host 0.0.0.0 --port 5173
```

### Scenario 2: Sprites.dev Remote (Recommended for Production)

```
Sprites.dev VM
├─ Backend: http://0.0.0.0:8000 (FastAPI)
├─ Sandbox-Agent: http://0.0.0.0:2468 (Auto-started)
├─ Workspace: /home/sprite/workspace (Local FS on VM)
└─ ANTHROPIC_API_KEY: Set from Vault

Your Machine
├─ SSH Tunnel: -L 8000:127.0.0.1:8000 -L 2468:127.0.0.1:2468
└─ Frontend: http://localhost:5173 (Vite on your machine)
```

**Benefits**:
- Zero network latency for file operations
- Both services access workspace locally
- Scalable: multiple instances with different workspaces
- Production-ready: no mounting complexity

**Setup**: See SPRITES_DEPLOYMENT_GUIDE.md

### Scenario 3: Mounted Remote Filesystem

```
Your Machine
├─ /mnt/sprites-share (Mounted via NFS/SSHFS)
│  └─ /home/sprite/workspace
├─ Backend: localhost:8000
├─ Sandbox-Agent: localhost:2468
└─ WORKSPACE_ROOT=/mnt/sprites-share/home/sprite/workspace
```

**Trade-off**: Network latency for file operations

**Not Recommended**: Use Scenario 2 instead (run on Sprites.dev directly)

## Key Architectural Principles

1. **Separation of Concerns**
   - File operations are independent of chat agents
   - Backend is control plane (tokens + lifecycle)
   - Agents are direct (no proxy overhead)

2. **Token-Based Security**
   - Services get tokens via capabilities endpoint
   - Browser connects directly with tokens
   - No shared secrets in code

3. **Flexible Storage**
   - Abstracted Storage interface
   - Works with local, Sprites.dev, NFS, S3
   - No special classes needed (LocalStorage + WORKSPACE_ROOT)

4. **Subprocess Lifecycle Management**
   - Managers auto-start services on backend startup
   - Graceful shutdown on app termination
   - Tokens regenerated each startup (fail-safe)

5. **Direct Connect Architecture**
   - Browser connects directly to services
   - Backend only issues tokens and manages lifecycle
   - No request proxying (better performance)

## Testing & Validation

**Unit Tests**:
```bash
pytest src/back/tests/  # Backend tests
npm test  # Frontend tests (if configured)
```

**E2E Tests**:
```bash
node tests/e2e/test_direct_connect.js  # 11 tests for Direct Connect
```

**Manual Testing**:
1. Start backend (see backend startup commands)
2. Start frontend (npx vite)
3. Test FileTree: create/read/delete files
4. Test Chat: send message, verify agent responds
5. Test integration: file operations + chat together

## Summary Table

| Component | Technology | Port | Role |
|-----------|-----------|------|------|
| **Frontend** | React + Vite | 5173 | UI, Layout, Chat UI |
| **Backend** | FastAPI | 8000 | File API, Token Distribution, Lifecycle |
| **Sandbox-Agent** | Rust | 2468 | Chat API, Tool Execution, Claude Interface |
| **Companion** | Bun + Hono | 3456 | Alternative Chat Provider (optional) |
| **Storage** | LocalStorage/S3 | — | File I/O Abstraction |
| **Auth** | PyJWT | — | Token Signing & Verification |

## Next Steps

For implementation details, see:
- **Authentication**: `SPRITES_AUTHENTICATION.md`
- **Deployment**: `SPRITES_DEPLOYMENT_GUIDE.md`
- **Configuration**: `WORKSPACE_CONFIGURATION.md`
- **Remote Setup**: `REMOTE_SANDBOX_SETUP.md`
