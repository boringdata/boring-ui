# External APIs & Integrations

## Claude AI Integration (Stream Router)

### Overview
The boring-ui backend integrates with Claude through a stream-based WebSocket interface. The `stream_bridge.py` spawns Claude CLI subprocesses and bridges their output to connected WebSocket clients.

### Implementation
- **Module**: `src/back/boring_ui/api/modules/stream/`
- **Entry Point**: `/ws/stream` WebSocket endpoint (router alias: chat_claude_code)
- **Protocol**: JSON-lines format from Claude CLI with stream-json flag
- **Process Model**: Subprocess (Claude CLI) with async pipe-based I/O

### Command Invocation
```bash
claude --stream-json  # Spawned by stream_bridge.py
```

### Message Protocol
**Input (Client → Server)**
```json
{"type": "user", "message": "..."}
```

**Output (Server → Client)**
- Direct forwarding of Claude CLI's JSON-lines output
- Structured streaming events from Claude

### Slash Commands
Default slash commands broadcast to frontend on connect (match frontend DEFAULT_SLASH_COMMANDS):
- `clear` - Clear session
- `model` - Switch model
- `thinking` - Toggle extended thinking
- `memory` - Manage memory
- `permissions` - Check/manage permissions
- `mcp` - MCP (Model Context Protocol) management
- `hooks` - Configure hooks
- `agents` - Agent management
- `help` - Help documentation
- `compact` - Compact mode toggle
- `cost` - Show token cost
- `init` - Initialize session
- `terminal` - Terminal control
- `restart` - Restart session

### Permission Suggestions
The stream module handles permission suggestions from Claude CLI by:
1. Receiving permission suggestion objects with type, destination, and content
2. Normalizing rules (tool names, patterns, parenthesized formats)
3. Persisting to settings files:
   - User settings: ~/.claude/config.json
   - Project settings: .claude/config.json
   - Local settings: .beads/config.json
   - Session-only: in-memory only

**Permission Types:**
- `addRules` - Add approval rules
- `setMode` - Set approval mode (always, prompt, deny)
- `addDirectories` - Add approved directories

**Destinations:**
- `userSettings` - User-wide settings
- `projectSettings` - Project-level settings
- `localSettings` - Repository-level settings
- `session` - Current session only

### Session Management
- **Storage**: In-memory session registry (_SESSION_REGISTRY)
- **History**: Deque-based (configurable via KURT_STREAM_HISTORY_LINES)
- **Idle TTL**: Configurable via KURT_STREAM_IDLE_TTL
- **Max Sessions**: Limited by KURT_STREAM_MAX_SESSIONS
- **Clients per Session**: Multiple WebSocket clients can connect to same session

---

## Git Integration

### Overview
The boring-ui backend provides Git operations through a service-based architecture.

### Implementation
- **Module**: `src/back/boring_ui/api/modules/git/`
- **Service**: GitService in service.py
- **Router**: `src/back/boring_ui/api/modules/git/router.py`
- **Endpoint Prefix**: `/api/git`

### Git Operations
- `git status` - Repository status with file tracking
- `git diff` - Show file changes
- `git show` - Display commit or file contents
- **Security**: All paths validated against workspace_root to prevent traversal

### Process Execution
Uses Python `subprocess` module to run git commands in the workspace directory:
```python
subprocess.run(['git', ...], cwd=workspace_root, capture_output=True)
```

### Frontend Integration
- **FileTree Panel**: Git status polling (gitPollInterval: 5000ms default)
- **Diff Viewer**: Uses git diff for side-by-side comparisons
- **Git Status Colors**: Semantic colors for modified, added, deleted files

---

## Terminal Integration (PTY)

### Overview
Full pseudo-terminal support for running arbitrary shell commands within the workspace.

### Implementation
- **Module**: `src/back/boring_ui/api/modules/pty/`
- **Service**: PTYSession in service.py
- **Router**: `src/back/boring_ui/api/modules/pty/router.py`
- **Endpoint**: `/ws/pty` WebSocket endpoint
- **Process Library**: ptyprocess (wraps PTY system calls)

### Terminal Setup
- **TERM Environment**: xterm-256color (256 color support)
- **Command**: Configurable shell (default: $SHELL or /bin/bash)
- **Working Directory**: Workspace root or specified directory
- **History**: Byte-based rolling buffer (PTY_HISTORY_BYTES: 200KB default)

### Session Features
- **Window Resizing**: SIGWINCH signals for terminal resizing
- **Multi-Client Support**: Multiple WebSocket clients share session
- **History Persistence**: Messages buffered in deque during session lifetime
- **Idle Cleanup**: Automatic session cleanup after TTL expiry

### Channels
- **Output**: Terminal stdout/stderr unified stream
- **Input**: Client input forwarded to PTY stdin
- **Control**: Window size changes, signal delivery

---

## File System Integration

### Overview
Abstract file system operations with pluggable storage backends.

### Storage Backends

#### LocalStorage (Default)
- **Implementation**: src/back/boring_ui/api/storage.py
- **Root**: Configurable workspace_root
- **Operations**: list, read, write, delete, rename, move, exists
- **Security**: Path validation prevents directory traversal
- **File Sorting**: Directories first, then alphabetical (case-insensitive)

#### S3Storage (Optional)
- **Implementation**: src/back/boring_ui/api/storage.py
- **Dependency**: boto3 (requires `pip install boring-ui[s3]`)
- **Authentication**: Uses AWS credentials (IAM roles or ~/.aws/credentials)
- **Key Prefix**: Optional per-bucket prefix for namespacing
- **Operations**: Full storage interface (list, read, write, delete, rename, move, exists)

#### Custom Backends
- Implement Storage ABC interface
- Inject via create_app(storage=CustomStorage(...))

### File Router Endpoints
- `GET /api/files?path=...` - List directory or read file
- `POST /api/files` - Write file
- `DELETE /api/files?path=...` - Delete file/directory
- `PUT /api/files` - Rename file
- `PATCH /api/files` - Move file

---

## Frontend API Communication

### API Base Resolution
- **Priority Order**:
  1. `VITE_API_URL` environment variable
  2. Auto-detect: if running on dev port (3000-5176), assume backend on :8000
  3. Same origin as frontend
  4. Default: http://localhost:8000

### Frontend Service Locations
- **Utility**: src/front/utils/apiBase.js
  - `getApiBase()` - Resolve API base URL
  - `buildApiUrl(path)` - Build full API URL
  - `getWsBase()` - Get WebSocket base (ws:// or wss://)

### API Communication Patterns
- **REST Endpoints**: Fetch API for /api/* endpoints
- **WebSocket Streams**: For /ws/pty (terminals) and /ws/stream (Claude chat)
- **CORS**: Enabled by default (configurable via APIConfig)
- **Proxying**: Vite dev server proxies /api and /ws to backend

---

## Approval Workflow Integration

### Overview
Optional approval system for managed access control.

### Implementation
- **Module**: `src/back/boring_ui/api/approval.py`
- **Router Endpoint**: `/api/approval/*`
- **Store**: In-memory by default (InMemoryApprovalStore)
- **Custom Stores**: Implement ApprovalStore ABC interface

### Workflow
1. Frontend can request approval for actions
2. Backend stores approval requests with expiry
3. Authorized users approve/deny requests
4. Frontend polls or receives approval status
5. Actions execute after approval granted

### Configuration
- **Include by Default**: Yes (include_approval=True in create_app)
- **Optional**: Can be excluded via routers=['files', 'git', ...]

---

## Capabilities Discovery

### Overview
Dynamic feature discovery allows frontend to gracefully degrade when backend features unavailable.

### Endpoint
- **URL**: `/api/capabilities`
- **Response Format**:
```json
{
  "version": "0.1.0",
  "features": {
    "files": true,
    "git": true,
    "pty": true,
    "chat_claude_code": true,
    "stream": true,
    "approval": false
  },
  "routers": [
    {
      "name": "files",
      "prefix": "/api",
      "description": "File system operations...",
      "tags": ["files"],
      "enabled": true
    },
    ...
  ]
}
```

### Frontend Usage
- **Hook**: `useCapabilities()` - Fetches and caches capabilities
- **Gate Component**: CapabilityGate wraps components requiring specific features
- **Pane Registration**: Each pane declares requiresRouters/requiresFeatures
- **Graceful Degradation**: Missing features show error state instead of crashing

---

## Configuration & Environment

### Backend Configuration
- **Class**: APIConfig (src/back/boring_ui/api/config.py)
- **workspace_root**: Directory for file operations (Path object)
- **cors_origins**: Allowed CORS origins (list of strings)
- **pty_providers**: Terminal providers (dict, defaults to shell)
- **validate_path(path)**: Security check for path traversal

### Frontend Configuration
- **File**: src/front/config/appConfig.js
- **Provider**: ConfigProvider component
- **Merging**: Deep merge of user config with defaults
- **Storage**: localStorage with configurable prefix
- **CSS Variables**: Theme customization via design tokens

### Environment Variable Interpolation
**Backend:**
- Session environment variables: All os.environ copied + TERM override
- Workspace environment: Inherited from backend process

**Frontend:**
- VITE_* variables: Compiled at build time via Vite
- Runtime detection: Browser origin, port inspection

---

## Cross-Module Integration Points

### Router Registry Pattern
- Central registry allows dynamic router composition
- Core routers: files, git (always included)
- Optional routers: pty, chat_claude_code/stream, approval
- Each router declares prefix, description, required capabilities

### Session Management
- **PTY Sessions**: Long-lived, multiplexed across WebSocket clients
- **Stream Sessions**: Long-lived Claude chat sessions with history
- **Cleanup**: Idle TTL triggers automatic session termination
- **Endpoints**: /api/sessions (list) and /api/sessions (POST create)

### Error Handling
- **Path Validation**: HTTPException 400 for invalid paths
- **Missing Features**: CapabilityGate shows error state, no crashes
- **Process Failures**: WebSocket disconnect, reconnect capable
- **Permission Errors**: Settings persistence gracefully degrades

---

## Third-Party Service Dependencies

### Development-Time
- GitHub (repository hosting)
- npm registry (dependency hosting)

### Runtime
- Local file system (workspace)
- Local Git repository
- Local shell/bash
- AWS S3 (optional, if using S3Storage)
- Claude AI CLI (subprocess, if using stream router)

### No Runtime External API Dependencies (Core)
- No external SaaS APIs required
- All operations are local or subprocess-based
- S3 is optional cloud integration
- Claude is integrated via CLI subprocess, not REST API
